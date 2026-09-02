"""Tests des convertisseurs purs de la grille peignable (§5.3 niveau 2)."""

from datetime import time

from planner.core.models import Constraint
from planner.ui.widgets.constraint_grid import (
    cells_from_constraints,
    constraints_from_cells,
    row_to_time,
    slots_in_window,
)

WAKE_START, WAKE_END = time(8, 0), time(22, 0)


def make_constraint(weekday, start, end, category="travail"):
    return Constraint(
        id=None, label=category, category=category, weekday=weekday,
        specific_date=None, start=start, end=end,
    )


def test_slots_in_window():
    assert slots_in_window(WAKE_START, WAKE_END) == 28


def test_row_to_time():
    assert row_to_time(0, WAKE_START) == time(8, 0)
    assert row_to_time(3, WAKE_START) == time(9, 30)


def test_cells_projection():
    cells = cells_from_constraints(
        [make_constraint(0, time(9, 0), time(11, 0))], WAKE_START, WAKE_END
    )
    assert cells == {(0, 2): "travail", (0, 3): "travail", (0, 4): "travail",
                     (0, 5): "travail"}


def test_merge_contiguous_cells():
    cells = {(2, 4): "sommeil", (2, 5): "sommeil", (2, 6): "sommeil",
             (2, 8): "travail"}
    constraints = constraints_from_cells(cells, WAKE_START)
    assert len(constraints) == 2
    sleep = next(c for c in constraints if c.category == "sommeil")
    assert (sleep.weekday, sleep.start, sleep.end) == (2, time(10, 0), time(11, 30))
    work = next(c for c in constraints if c.category == "travail")
    assert (work.start, work.end) == (time(12, 0), time(12, 30))


def test_roundtrip_is_stable():
    original = [
        make_constraint(0, time(9, 0), time(12, 0), "cours"),
        make_constraint(4, time(17, 30), time(20, 0), "entrainement"),
    ]
    cells = cells_from_constraints(original, WAKE_START, WAKE_END)
    rebuilt = constraints_from_cells(cells, WAKE_START)
    assert len(rebuilt) == 2
    by_day = {c.weekday: c for c in rebuilt}
    assert (by_day[0].start, by_day[0].end) == (time(9, 0), time(12, 0))
    assert (by_day[4].start, by_day[4].end) == (time(17, 30), time(20, 0))


def test_adjacent_different_categories_not_merged():
    cells = {(1, 0): "travail", (1, 1): "transport"}
    constraints = constraints_from_cells(cells, WAKE_START)
    assert len(constraints) == 2
