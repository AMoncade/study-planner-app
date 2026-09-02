"""Étape D — grille de disponibilité en créneaux de 30 minutes (ARCHITECTURE §4).

Un jour = 48 booléens (créneau libre ou non). Libre ⟺ dans la plage d'éveil, hors
contraintes fixes, hors séances de cours, hors tampon transport.
"""

from __future__ import annotations

from datetime import date, time, timedelta

from planner.config import BUFFERED_CATEGORIES, EngineSettings
from planner.core.models import Constraint, Course

SLOTS_PER_DAY = 48  # 24 h / 30 min

DayGrid = list[bool]


def slot_index(t: time) -> int:
    return t.hour * 2 + (1 if t.minute >= 30 else 0)


def _end_slot(t: time) -> int:
    """Index de fin exclusif : 12:00 -> 24 ; 12:15 occupe le créneau 12:00-12:30."""
    index = t.hour * 2
    if t.minute == 0:
        return index
    return index + (1 if t.minute <= 30 else 2)


def _mark(day: DayGrid, start: time, end: time, buffered: bool, s: EngineSettings) -> None:
    lo, hi = slot_index(start), _end_slot(end)
    if buffered:
        pad = s.transport_buffer_minutes // s.slot_minutes
        lo, hi = lo - pad, hi + pad
    for i in range(max(lo, 0), min(hi, SLOTS_PER_DAY)):
        day[i] = False


def build_grid(
    start_day: date,
    end_day: date,
    constraints: list[Constraint],
    courses: list[Course],
    s: EngineSettings,
) -> dict[date, DayGrid]:
    """Grille des créneaux libres pour chaque jour de [start_day, end_day]."""
    grid: dict[date, DayGrid] = {}
    wake_lo, wake_hi = slot_index(s.wake_start), _end_slot(s.wake_end)
    day = start_day
    while day <= end_day:
        slots = [wake_lo <= i < wake_hi for i in range(SLOTS_PER_DAY)]
        for c in constraints:
            applies = (
                c.specific_date == day
                if c.specific_date is not None
                else c.weekday == day.weekday()
            )
            if applies:
                _mark(slots, c.start, c.end, c.category in BUFFERED_CATEGORIES, s)
        for course in courses:
            for session in course.sessions:
                if session.weekday != day.weekday():
                    continue
                if session.start_date and day < session.start_date:
                    continue
                if session.end_date and day > session.end_date:
                    continue
                if day in session.except_dates:
                    continue
                _mark(slots, session.start, session.end, True, s)
        grid[day] = slots
        day += timedelta(days=1)
    return grid


def free_hours(day: DayGrid) -> float:
    return sum(day) * 0.5


def day_capacity(day: DayGrid, day_date: date, s: EngineSettings) -> float:
    """C(jour) = min(heures libres, plafond journalier)."""
    return min(free_hours(day), s.h_jour_max(day_date.weekday()))


def total_capacity(grid: dict[date, DayGrid], s: EngineSettings) -> float:
    """Capacité de l'horizon, pondérée par le taux d'utilisation cible υ."""
    return sum(day_capacity(slots, d, s) for d, slots in grid.items()) * s.upsilon
