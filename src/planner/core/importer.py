"""Lecture, validation et réconciliation d'un fichier JSON de cours (ARCHITECTURE §2).

L'upsert se fait par (course.code, course.term) pour le cours et par external_id pour
chaque évaluation (§2.5). Les champs réglés à la main (difficulty, effort_multiplier,
manual_hours_override) ne sont jamais écrasés par un import.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path

from planner.core.errors import ImportBlockedError
from planner.core.models import EXAM_TYPES, WEEKDAYS, Course, Evaluation, Session
from planner.core.validation import validate_document
from planner.storage import repositories as repos

DEFAULT_EXAM_TIME = time(8, 0)
DEFAULT_SUBMISSION_TIME = time(23, 59)


@dataclass
class ImportReport:
    course_code: str
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    archived: int = 0
    warnings: list[str] = field(default_factory=list)


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _due_at(ev: dict) -> datetime | None:
    if ev["due_date"] is None:
        return None
    due_date = date.fromisoformat(ev["due_date"])
    if ev.get("due_time"):
        due_time = _parse_time(ev["due_time"])
    elif ev["type"] in EXAM_TYPES:
        due_time = DEFAULT_EXAM_TIME
    else:
        due_time = DEFAULT_SUBMISSION_TIME
    return datetime.combine(due_date, due_time)


def _map_course(data: dict) -> Course:
    c = data["course"]
    sessions = [
        Session(
            id=None,
            kind=s["kind"],
            weekday=WEEKDAYS.index(s["weekday"]),
            start=_parse_time(s["start"]),
            end=_parse_time(s["end"]),
            room=s.get("room"),
            start_date=date.fromisoformat(s["start_date"]) if s.get("start_date") else None,
            end_date=date.fromisoformat(s["end_date"]) if s.get("end_date") else None,
            except_dates=[date.fromisoformat(d) for d in s.get("except_dates", [])],
        )
        for s in c.get("sessions", [])
    ]
    return Course(
        id=None,
        code=c["code"],
        title=c["title"],
        term=c["term"],
        institution=c.get("institution"),
        credits=c.get("credits"),
        instructor=c.get("instructor"),
        language=c.get("language", "fr"),
        difficulty=c.get("difficulty", 3),
        effort_multiplier=c.get("effort_multiplier", 1.0),
        sessions=sessions,
    )


def _map_evaluation(ev: dict) -> Evaluation:
    return Evaluation(
        id=None,
        course_id=None,
        external_id=ev["id"],
        title=ev["title"],
        type=ev["type"],
        weight=float(ev["weight"]),
        due_at=_due_at(ev),
        start_date=date.fromisoformat(ev["start_date"]) if ev.get("start_date") else None,
        duration_minutes=ev.get("duration_minutes"),
        modality=ev.get("modality"),
        location=ev.get("location"),
        cumulative=ev.get("cumulative"),
        group_work=ev.get("group_work"),
        content_scope=list(ev.get("content_scope", [])),
        scope_units=ev.get("scope_units"),
        deliverable=ev.get("deliverable"),
        estimated_pages=ev.get("estimated_pages"),
        resources=list(ev.get("resources", [])),
        notes=ev.get("notes"),
        confidence=ev["confidence"],
        source_excerpt=ev.get("source_excerpt"),
    )


# Champs comparés pour décider si une évaluation importée diffère de celle en base.
_COMPARED_FIELDS = (
    "title", "type", "weight", "due_at", "start_date", "duration_minutes", "modality",
    "location", "cumulative", "group_work", "content_scope", "scope_units", "deliverable",
    "estimated_pages", "resources", "notes", "confidence", "source_excerpt",
)

# Sous-ensemble dont le changement invalide les blocs d'étude déjà planifiés (§2.5).
_REPLAN_FIELDS = ("due_at", "weight", "scope_units", "cumulative", "type")


def import_course_data(conn, data: object, today: date) -> ImportReport:
    """Valide puis importe un document JSON déjà décodé. Lève ImportBlockedError si refusé."""
    errors, warnings = validate_document(data)
    if errors:
        raise ImportBlockedError(errors)
    assert isinstance(data, dict)

    course = _map_course(data)
    evaluations = [_map_evaluation(ev) for ev in data["evaluations"]]
    report = ImportReport(course_code=course.code, warnings=list(warnings))

    with conn:  # transaction unique : tout ou rien
        course_id = repos.upsert_course(conn, course)
        existing = {
            e.external_id: e
            for e in repos.list_evaluations(conn, course_id=course_id, include_archived=True)
        }
        seen: set[str] = set()
        for ev in evaluations:
            ev.course_id = course_id
            seen.add(ev.external_id)
            current = existing.get(ev.external_id)
            if current is None:
                repos.insert_evaluation(conn, ev)
                report.created += 1
                continue
            changed = [
                f for f in _COMPARED_FIELDS if getattr(current, f) != getattr(ev, f)
            ]
            if not changed and not current.archived:
                report.unchanged += 1
                continue
            repos.update_evaluation_from_import(conn, current.id, ev)
            report.updated += 1
            if any(f in _REPLAN_FIELDS for f in changed):
                dropped = repos.delete_planned_blocks(conn, current.id)
                if dropped:
                    report.warnings.append(
                        f"{ev.external_id} : {dropped} bloc(s) planifié(s) invalidé(s) "
                        "(échéance ou charge modifiée), à replanifier."
                    )
        # Évaluations absentes du nouveau fichier -> archivées, jamais supprimées.
        for external_id, current in existing.items():
            if external_id not in seen and not current.archived:
                repos.archive_evaluation(conn, current.id)
                report.archived += 1

    return report


def import_course_file(conn, path: str | Path, today: date) -> ImportReport:
    """Lit un fichier JSON et l'importe. Lève ImportBlockedError si refusé."""
    raw = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImportBlockedError([f"JSON illisible : {exc}"]) from exc
    return import_course_data(conn, data, today=today)
