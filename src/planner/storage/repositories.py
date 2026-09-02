"""CRUD par entité (ARCHITECTURE §3). Conversion lignes SQLite <-> dataclasses du domaine."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time

from planner.core.models import Constraint, Course, Evaluation, Session, StudyBlock

# ------------------------------------------------------------------ conversions


def _iso(value: date | datetime | time | None) -> str | None:
    return None if value is None else value.isoformat()


def _to_date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def _to_datetime(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def _to_time(value: str) -> time:
    return time.fromisoformat(value)


def _to_bool(value: int | None) -> bool | None:
    return None if value is None else bool(value)


# ------------------------------------------------------------------ courses


def upsert_course(conn: sqlite3.Connection, course: Course) -> int:
    """Insère ou met à jour le cours identifié par (code, term).

    Les champs manuels (difficulty, effort_multiplier) ne sont pas écrasés à la
    mise à jour ; les sessions sont remplacées (elles viennent du plan de cours).
    """
    row = conn.execute(
        "SELECT id FROM courses WHERE code = ? AND term = ?", (course.code, course.term)
    ).fetchone()
    if row is None:
        cursor = conn.execute(
            """INSERT INTO courses (code, title, term, institution, credits, instructor,
                                    language, difficulty, effort_multiplier)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (course.code, course.title, course.term, course.institution, course.credits,
             course.instructor, course.language, course.difficulty, course.effort_multiplier),
        )
        course_id = cursor.lastrowid
    else:
        course_id = row[0]
        conn.execute(
            """UPDATE courses SET title = ?, institution = ?, credits = ?, instructor = ?,
                                  language = ?, archived = 0
               WHERE id = ?""",
            (course.title, course.institution, course.credits, course.instructor,
             course.language, course_id),
        )
        conn.execute("DELETE FROM sessions WHERE course_id = ?", (course_id,))
    for s in course.sessions:
        conn.execute(
            """INSERT INTO sessions (course_id, kind, weekday, start, end, room,
                                     start_date, end_date, except_dates)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (course_id, s.kind, s.weekday, _iso(s.start), _iso(s.end), s.room,
             _iso(s.start_date), _iso(s.end_date),
             json.dumps([d.isoformat() for d in s.except_dates])),
        )
    return course_id


def _course_from_row(conn: sqlite3.Connection, row: tuple) -> Course:
    (cid, code, title, term, institution, credits, instructor,
     language, difficulty, effort_multiplier, archived) = row
    sessions = [
        Session(
            id=sid, kind=kind, weekday=weekday, start=_to_time(start), end=_to_time(end),
            room=room, start_date=_to_date(sd), end_date=_to_date(ed),
            except_dates=[date.fromisoformat(d) for d in json.loads(excepts)],
        )
        for sid, kind, weekday, start, end, room, sd, ed, excepts in conn.execute(
            """SELECT id, kind, weekday, start, end, room, start_date, end_date, except_dates
               FROM sessions WHERE course_id = ? ORDER BY weekday, start""",
            (cid,),
        ).fetchall()
    ]
    return Course(
        id=cid, code=code, title=title, term=term, institution=institution, credits=credits,
        instructor=instructor, language=language, difficulty=difficulty,
        effort_multiplier=effort_multiplier, archived=bool(archived), sessions=sessions,
    )


_COURSE_COLUMNS = """id, code, title, term, institution, credits, instructor,
                     language, difficulty, effort_multiplier, archived"""


def list_courses(conn: sqlite3.Connection, include_archived: bool = False) -> list[Course]:
    where = "" if include_archived else "WHERE archived = 0"
    rows = conn.execute(
        f"SELECT {_COURSE_COLUMNS} FROM courses {where} ORDER BY code"
    ).fetchall()
    return [_course_from_row(conn, r) for r in rows]


def get_course(conn: sqlite3.Connection, course_id: int) -> Course | None:
    row = conn.execute(
        f"SELECT {_COURSE_COLUMNS} FROM courses WHERE id = ?", (course_id,)
    ).fetchone()
    return None if row is None else _course_from_row(conn, row)


def update_course_manual_fields(
    conn: sqlite3.Connection,
    course_id: int,
    difficulty: int | None = None,
    effort_multiplier: float | None = None,
) -> None:
    if difficulty is not None:
        conn.execute("UPDATE courses SET difficulty = ? WHERE id = ?", (difficulty, course_id))
    if effort_multiplier is not None:
        conn.execute(
            "UPDATE courses SET effort_multiplier = ? WHERE id = ?",
            (effort_multiplier, course_id),
        )
    conn.commit()


# ------------------------------------------------------------------ evaluations

_EVAL_COLUMNS = """id, course_id, external_id, title, type, weight, due_at, start_date,
                   duration_minutes, modality, location, cumulative, group_work,
                   content_scope, scope_units, deliverable, estimated_pages, resources,
                   notes, confidence, source_excerpt, manual_hours_override, status, archived"""


def _evaluation_from_row(row: tuple) -> Evaluation:
    (eid, course_id, external_id, title, type_, weight, due_at, start_date, duration,
     modality, location, cumulative, group_work, scope, scope_units, deliverable,
     pages, resources, notes, confidence, excerpt, override, status, archived) = row
    return Evaluation(
        id=eid, course_id=course_id, external_id=external_id, title=title, type=type_,
        weight=weight, due_at=_to_datetime(due_at), start_date=_to_date(start_date),
        duration_minutes=duration, modality=modality, location=location,
        cumulative=_to_bool(cumulative), group_work=_to_bool(group_work),
        content_scope=json.loads(scope), scope_units=scope_units, deliverable=deliverable,
        estimated_pages=pages, resources=json.loads(resources), notes=notes,
        confidence=confidence, source_excerpt=excerpt, manual_hours_override=override,
        status=status, archived=bool(archived),
    )


def insert_evaluation(conn: sqlite3.Connection, ev: Evaluation) -> int:
    cursor = conn.execute(
        f"""INSERT INTO evaluations ({_EVAL_COLUMNS.replace('id, ', '', 1)})
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ev.course_id, ev.external_id, ev.title, ev.type, ev.weight, _iso(ev.due_at),
         _iso(ev.start_date), ev.duration_minutes, ev.modality, ev.location,
         None if ev.cumulative is None else int(ev.cumulative),
         None if ev.group_work is None else int(ev.group_work),
         json.dumps(ev.content_scope, ensure_ascii=False), ev.scope_units, ev.deliverable,
         ev.estimated_pages, json.dumps(ev.resources, ensure_ascii=False), ev.notes,
         ev.confidence, ev.source_excerpt, ev.manual_hours_override, ev.status,
         int(ev.archived)),
    )
    return cursor.lastrowid


def update_evaluation_from_import(conn: sqlite3.Connection, eval_id: int, ev: Evaluation) -> None:
    """Met à jour les champs importés ; préserve manual_hours_override et status ; désarchive."""
    conn.execute(
        """UPDATE evaluations SET
             title = ?, type = ?, weight = ?, due_at = ?, start_date = ?,
             duration_minutes = ?, modality = ?, location = ?, cumulative = ?, group_work = ?,
             content_scope = ?, scope_units = ?, deliverable = ?, estimated_pages = ?,
             resources = ?, notes = ?, confidence = ?, source_excerpt = ?, archived = 0
           WHERE id = ?""",
        (ev.title, ev.type, ev.weight, _iso(ev.due_at), _iso(ev.start_date),
         ev.duration_minutes, ev.modality, ev.location,
         None if ev.cumulative is None else int(ev.cumulative),
         None if ev.group_work is None else int(ev.group_work),
         json.dumps(ev.content_scope, ensure_ascii=False), ev.scope_units, ev.deliverable,
         ev.estimated_pages, json.dumps(ev.resources, ensure_ascii=False), ev.notes,
         ev.confidence, ev.source_excerpt, eval_id),
    )


def archive_evaluation(conn: sqlite3.Connection, eval_id: int) -> None:
    conn.execute("UPDATE evaluations SET archived = 1 WHERE id = ?", (eval_id,))


def list_evaluations(
    conn: sqlite3.Connection,
    course_id: int | None = None,
    include_archived: bool = False,
) -> list[Evaluation]:
    clauses, params = [], []
    if course_id is not None:
        clauses.append("course_id = ?")
        params.append(course_id)
    if not include_archived:
        clauses.append("archived = 0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""SELECT {_EVAL_COLUMNS} FROM evaluations {where}
            ORDER BY due_at IS NULL, due_at, external_id""",
        params,
    ).fetchall()
    return [_evaluation_from_row(r) for r in rows]


def set_manual_hours_override(
    conn: sqlite3.Connection, eval_id: int, hours: float | None
) -> None:
    conn.execute(
        "UPDATE evaluations SET manual_hours_override = ? WHERE id = ?", (hours, eval_id)
    )
    conn.commit()


# ------------------------------------------------------------------ constraints


def insert_constraint(conn: sqlite3.Connection, c: Constraint) -> int:
    cursor = conn.execute(
        """INSERT INTO constraints (label, category, weekday, specific_date, start, end,
                                    rrule, priority, color)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (c.label, c.category, c.weekday, _iso(c.specific_date), _iso(c.start), _iso(c.end),
         c.rrule, c.priority, c.color),
    )
    conn.commit()
    return cursor.lastrowid


def update_constraint(conn: sqlite3.Connection, c: Constraint) -> None:
    conn.execute(
        """UPDATE constraints SET label = ?, category = ?, weekday = ?, specific_date = ?,
                                  start = ?, end = ?, rrule = ?, priority = ?, color = ?
           WHERE id = ?""",
        (c.label, c.category, c.weekday, _iso(c.specific_date), _iso(c.start), _iso(c.end),
         c.rrule, c.priority, c.color, c.id),
    )
    conn.commit()


def delete_constraint(conn: sqlite3.Connection, constraint_id: int) -> None:
    conn.execute("DELETE FROM constraints WHERE id = ?", (constraint_id,))
    conn.commit()


def list_constraints(conn: sqlite3.Connection) -> list[Constraint]:
    rows = conn.execute(
        """SELECT id, label, category, weekday, specific_date, start, end, rrule,
                  priority, color
           FROM constraints ORDER BY weekday IS NULL, weekday, start"""
    ).fetchall()
    return [
        Constraint(
            id=cid, label=label, category=category, weekday=weekday,
            specific_date=_to_date(specific), start=_to_time(start), end=_to_time(end),
            rrule=rrule, priority=priority, color=color,
        )
        for cid, label, category, weekday, specific, start, end, rrule, priority, color in rows
    ]


# ------------------------------------------------------------------ study blocks

_BLOCK_COLUMNS = """id, evaluation_id, start_at, end_at, planned_minutes, status, locked,
                    generation_id, actual_minutes, efficiency, note"""


def _block_from_row(row: tuple) -> StudyBlock:
    (bid, eval_id, start_at, end_at, planned, status, locked, gen_id,
     actual, efficiency, note) = row
    return StudyBlock(
        id=bid, evaluation_id=eval_id, start_at=_to_datetime(start_at),
        end_at=_to_datetime(end_at), planned_minutes=planned, status=status,
        locked=bool(locked), generation_id=gen_id, actual_minutes=actual,
        efficiency=efficiency, note=note,
    )


def insert_study_block(
    conn: sqlite3.Connection,
    evaluation_id: int,
    start_at: datetime,
    end_at: datetime,
    status: str = "planned",
    locked: bool = False,
    generation_id: int | None = None,
) -> int:
    planned = int((end_at - start_at).total_seconds() // 60)
    cursor = conn.execute(
        """INSERT INTO study_blocks (evaluation_id, start_at, end_at, planned_minutes,
                                     status, locked, generation_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (evaluation_id, _iso(start_at), _iso(end_at), planned, status, int(locked),
         generation_id),
    )
    conn.commit()
    return cursor.lastrowid


def update_study_block_status(
    conn: sqlite3.Connection,
    block_id: int,
    status: str,
    actual_minutes: int | None = None,
    efficiency: float | None = None,
) -> None:
    conn.execute(
        """UPDATE study_blocks SET status = ?, actual_minutes = ?, efficiency = ?
           WHERE id = ?""",
        (status, actual_minutes, efficiency, block_id),
    )
    conn.commit()


def delete_planned_blocks(conn: sqlite3.Connection, evaluation_id: int) -> int:
    """Supprime les blocs futurs non verrouillés encore à l'état planned. Retourne le nombre."""
    cursor = conn.execute(
        "DELETE FROM study_blocks WHERE evaluation_id = ? AND status = 'planned' AND locked = 0",
        (evaluation_id,),
    )
    return cursor.rowcount


def list_study_blocks(
    conn: sqlite3.Connection, evaluation_id: int | None = None
) -> list[StudyBlock]:
    if evaluation_id is None:
        rows = conn.execute(
            f"SELECT {_BLOCK_COLUMNS} FROM study_blocks ORDER BY start_at"
        ).fetchall()
    else:
        rows = conn.execute(
            f"""SELECT {_BLOCK_COLUMNS} FROM study_blocks
                WHERE evaluation_id = ? ORDER BY start_at""",
            (evaluation_id,),
        ).fetchall()
    return [_block_from_row(r) for r in rows]


# ------------------------------------------------------------------ settings


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return default if row is None else row[0]


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (key, value),
    )
    conn.commit()
