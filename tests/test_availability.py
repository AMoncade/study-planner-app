"""Tests de l'étape D : grille de disponibilité et capacité journalière."""

from datetime import date, time

from planner.config import EngineSettings
from planner.core.models import Constraint, Course, Session
from planner.scheduler.availability import build_grid, day_capacity, free_hours, slot_index

S = EngineSettings()
MONDAY = date(2026, 9, 14)  # lundi
SATURDAY = date(2026, 9, 19)


def constraint(weekday=None, specific_date=None, start=time(9), end=time(12),
               category="personnel", label="c") -> Constraint:
    return Constraint(
        id=None, label=label, category=category, weekday=weekday,
        specific_date=specific_date, start=start, end=end,
    )


def test_wake_window_bounds():
    grid = build_grid(MONDAY, MONDAY, [], [], S)
    day = grid[MONDAY]
    assert not day[slot_index(time(7, 30))]   # avant l'éveil
    assert day[slot_index(time(8, 0))]
    assert day[slot_index(time(21, 30))]
    assert not day[slot_index(time(22, 0))]   # après l'éveil


def test_weekly_constraint_blocks_slots():
    grid = build_grid(MONDAY, MONDAY, [constraint(weekday=0, category="sommeil")], [], S)
    day = grid[MONDAY]
    assert not day[slot_index(time(9, 0))]
    assert not day[slot_index(time(11, 30))]
    assert day[slot_index(time(12, 0))]


def test_specific_date_constraint_only_that_day():
    c = constraint(specific_date=date(2026, 9, 15), category="sommeil")
    grid = build_grid(MONDAY, date(2026, 9, 16), [c], [], S)
    assert grid[MONDAY][slot_index(time(9, 0))]
    assert not grid[date(2026, 9, 15)][slot_index(time(9, 0))]
    assert grid[date(2026, 9, 16)][slot_index(time(9, 0))]


def test_transport_buffer_around_out_of_home_constraint():
    c = constraint(weekday=0, start=time(9), end=time(12), category="travail")
    grid = build_grid(MONDAY, MONDAY, [c], [], S)
    day = grid[MONDAY]
    assert not day[slot_index(time(8, 30))]  # tampon avant
    assert not day[slot_index(time(12, 0))]  # tampon après
    assert day[slot_index(time(12, 30))]


def test_session_blocks_slots_with_bounds_and_exceptions():
    course = Course(
        id=1, code="MAT1400", title="Calcul 1", term="A26",
        sessions=[Session(
            id=None, kind="tp", weekday=0, start=time(15, 30), end=time(17, 30),
            start_date=date(2026, 8, 31), end_date=date(2026, 12, 23),
            except_dates=[date(2026, 9, 14)],
        )],
    )
    grid = build_grid(MONDAY, date(2026, 9, 21), [], [course], S)
    # 14/09 est une exception -> libre malgré la séance (mais tampon transport sinon)
    assert grid[MONDAY][slot_index(time(16, 0))]
    assert not grid[date(2026, 9, 21)][slot_index(time(16, 0))]
    # tampon transport autour d'une séance de cours
    assert not grid[date(2026, 9, 21)][slot_index(time(15, 0))]


def test_session_outside_date_bounds_does_not_block():
    course = Course(
        id=1, code="X", title="X", term="A26",
        sessions=[Session(
            id=None, kind="cours", weekday=0, start=time(9), end=time(11),
            start_date=date(2026, 10, 1), end_date=date(2026, 12, 1),
        )],
    )
    grid = build_grid(MONDAY, MONDAY, [], [course], S)
    assert grid[MONDAY][slot_index(time(9, 30))]  # séance pas encore commencée


def test_day_capacity_capped():
    grid = build_grid(MONDAY, SATURDAY, [], [], S)
    # journée entièrement libre : 14 h d'éveil, mais plafond 4 h semaine / 6 h week-end
    assert free_hours(grid[MONDAY]) == 14.0
    assert day_capacity(grid[MONDAY], MONDAY, S) == 4.0
    assert day_capacity(grid[SATURDAY], SATURDAY, S) == 6.0


def test_day_capacity_limited_by_free_slots():
    blocker = constraint(weekday=0, start=time(8), end=time(19), category="travail")
    grid = build_grid(MONDAY, MONDAY, [blocker], [], S)
    # libre : 19h30 (après tampon) à 22h -> 2,5 h < plafond 4 h
    assert day_capacity(grid[MONDAY], MONDAY, S) == 2.5
