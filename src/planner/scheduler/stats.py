"""Agrégats de la vue Statistiques (ARCHITECTURE §5.8) — module pur et déterministe.

Aucun accès aux données ni à l'horloge : `now` est toujours un paramètre.
Conventions partagées :
- un bloc « échu » a son `end_at <= now` ;
- les heures faites d'un bloc fait/partiel valent `actual_minutes`, avec repli sur
  `planned_minutes` quand les minutes réelles n'ont pas été saisies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from planner.core.models import Course, Evaluation, StudyBlock

# Statuts comptant comme du travail effectué.
DONE_STATUSES = ("done", "partial")


def _done_minutes(block: StudyBlock) -> int:
    """Minutes réellement travaillées d'un bloc fait ou partiel."""
    if block.status not in DONE_STATUSES:
        return 0
    return block.actual_minutes if block.actual_minutes is not None else block.planned_minutes


def _is_due(block: StudyBlock, now: datetime) -> bool:
    return block.end_at <= now


# ------------------------------------------------------------------ vue d'ensemble

@dataclass(frozen=True)
class OverviewStats:
    """Tuiles de la vue : totaux de session et écart au plan."""

    done_hours: float               # heures faites (blocs done/partial, toute la session)
    due_blocks: int                 # blocs échus (end_at <= now), tous statuts
    completed_due_blocks: int       # blocs échus faits ou partiels
    completion_rate: float | None   # completed_due / due, None sans bloc échu
    avg_efficiency: float | None    # moyenne des efficacités des blocs faits qui en ont une
    planned_due_hours: float        # heures planifiées échues (tous statuts)
    plan_delta_hours: float         # done_hours - planned_due_hours (signé)


def compute_overview(blocks: list[StudyBlock], now: datetime) -> OverviewStats:
    done_hours = sum(_done_minutes(b) for b in blocks) / 60
    due = [b for b in blocks if _is_due(b, now)]
    completed_due = sum(1 for b in due if b.status in DONE_STATUSES)
    planned_due_hours = sum(b.planned_minutes for b in due) / 60
    efficiencies = [b.efficiency for b in blocks
                    if b.status == "done" and b.efficiency is not None]
    return OverviewStats(
        done_hours=done_hours,
        due_blocks=len(due),
        completed_due_blocks=completed_due,
        completion_rate=completed_due / len(due) if due else None,
        avg_efficiency=sum(efficiencies) / len(efficiencies) if efficiencies else None,
        planned_due_hours=planned_due_hours,
        plan_delta_hours=done_hours - planned_due_hours,
    )


# ------------------------------------------------------------------ heures par semaine

@dataclass(frozen=True)
class WeekStat:
    """Une semaine ISO de la session : heures planifiées (piste) et faites (barre)."""

    year: int
    week: int
    label: str            # libellé court « s36 »
    planned_hours: float
    done_hours: float
    is_current: bool


def weekly_hours(blocks: list[StudyBlock], now: datetime) -> list[WeekStat]:
    """Toutes les semaines ISO du premier au dernier bloc, semaines vides incluses."""
    if not blocks:
        return []
    planned: dict[tuple[int, int], float] = {}
    done: dict[tuple[int, int], float] = {}
    for b in blocks:
        year, week, _ = b.start_at.isocalendar()
        planned[(year, week)] = planned.get((year, week), 0.0) + b.planned_minutes / 60
        done[(year, week)] = done.get((year, week), 0.0) + _done_minutes(b) / 60

    current = tuple(now.isocalendar()[:2])
    first = min(planned)
    last = max(planned)
    weeks: list[WeekStat] = []
    monday = datetime.fromisocalendar(first[0], first[1], 1).date()
    while True:
        year, week, _ = monday.isocalendar()
        key = (year, week)
        weeks.append(WeekStat(
            year=year, week=week, label=f"s{week}",
            planned_hours=planned.get(key, 0.0),
            done_hours=done.get(key, 0.0),
            is_current=key == current,
        ))
        if key == last:
            return weeks
        monday += timedelta(days=7)


# ------------------------------------------------------------------ heures par cours

@dataclass(frozen=True)
class CourseStat:
    """Heures faites / planifiées d'un cours.

    `color_index` est le rang du cours dans la liste des cours : la couleur suit le
    cours (theme.COURSE_COLORS[color_index]), jamais sa position dans un tri.
    """

    course_id: int
    code: str
    color_index: int
    done_hours: float
    planned_hours: float


def hours_by_course(
    blocks: list[StudyBlock],
    evaluations: list[Evaluation],
    courses: list[Course],
) -> list[CourseStat]:
    """Une ligne par cours, dans l'ordre (stable) de la liste des cours."""
    course_of_eval = {e.id: e.course_id for e in evaluations}
    planned: dict[int, float] = {}
    done: dict[int, float] = {}
    for b in blocks:
        course_id = course_of_eval.get(b.evaluation_id)
        if course_id is None:
            continue
        planned[course_id] = planned.get(course_id, 0.0) + b.planned_minutes / 60
        done[course_id] = done.get(course_id, 0.0) + _done_minutes(b) / 60
    return [
        CourseStat(
            course_id=c.id, code=c.code, color_index=i,
            done_hours=done.get(c.id, 0.0),
            planned_hours=planned.get(c.id, 0.0),
        )
        for i, c in enumerate(courses)
    ]


# ------------------------------------------------------------------ assiduité

@dataclass(frozen=True)
class AttendanceStats:
    """Répartition des blocs échus par statut (les futurs sont exclus)."""

    done: int
    partial: int
    skipped: int
    pending: int  # échus mais encore planned/moved : pas encore renseignés

    @property
    def total(self) -> int:
        return self.done + self.partial + self.skipped + self.pending


def attendance(blocks: list[StudyBlock], now: datetime) -> AttendanceStats:
    due = [b for b in blocks if _is_due(b, now)]
    done = sum(1 for b in due if b.status == "done")
    partial = sum(1 for b in due if b.status == "partial")
    skipped = sum(1 for b in due if b.status == "skipped")
    return AttendanceStats(
        done=done, partial=partial, skipped=skipped,
        pending=len(due) - done - partial - skipped,
    )
