"""Export .ics des blocs d'étude et des échéances (ARCHITECTURE Phase 6).

Fichier local à importer soi-même dans un calendrier — aucune connexion réseau.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from icalendar import Calendar, Event

from planner.core.models import Course, Evaluation, StudyBlock

PRODID = "-//Plan-Études//planner//FR"


def build_calendar(
    courses: list[Course],
    evaluations: list[Evaluation],
    blocks: list[StudyBlock],
) -> Calendar:
    calendar = Calendar()
    calendar.add("prodid", PRODID)
    calendar.add("version", "2.0")
    course_by_id = {c.id: c for c in courses}
    eval_by_id = {e.id: e for e in evaluations}

    for block in blocks:
        if block.status == "skipped":
            continue
        ev = eval_by_id.get(block.evaluation_id)
        if ev is None:
            continue
        course = course_by_id.get(ev.course_id)
        code = course.code if course else "?"
        event = Event()
        event.add("uid", f"block-{block.id}@plan-etudes")
        event.add("summary", f"Étude : {code} — {ev.title}")
        event.add("dtstart", block.start_at)
        event.add("dtend", block.end_at)
        event.add("description",
                  f"Bloc d'étude ({block.planned_minutes} min) pour {ev.external_id}.")
        calendar.add_component(event)

    for ev in evaluations:
        if ev.due_at is None or ev.archived:
            continue
        course = course_by_id.get(ev.course_id)
        code = course.code if course else "?"
        event = Event()
        event.add("uid", f"due-{ev.external_id}@plan-etudes")
        event.add("summary", f"⚑ {code} — {ev.title} ({ev.weight:g} %)")
        event.add("dtstart", ev.due_at)
        duration = ev.duration_minutes or 60
        event.add("dtend", ev.due_at + timedelta(minutes=duration))
        if ev.location:
            event.add("location", ev.location)
        calendar.add_component(event)

    return calendar


def export_ics(conn, path: str | Path) -> int:
    """Écrit le fichier .ics ; retourne le nombre d'événements."""
    from planner.storage import repositories as repos

    courses = repos.list_courses(conn)
    evaluations = [
        e for c in courses for e in repos.list_evaluations(conn, course_id=c.id)
    ]
    blocks = repos.list_study_blocks(conn)
    calendar = build_calendar(courses, evaluations, blocks)
    Path(path).write_bytes(calendar.to_ical())
    return len(calendar.subcomponents)
