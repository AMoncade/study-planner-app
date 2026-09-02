"""Tests pytest-qt Phase 5 : tableau de bord, vue paramètres, grille peignable."""

from datetime import date, datetime
from pathlib import Path

import pytest

from planner.config import load_engine_settings
from planner.core.importer import import_course_file
from planner.storage import repositories as repos
from planner.storage.db import connect
from planner.ui.views.dashboard_view import DashboardView
from planner.ui.views.settings_view import SettingsView
from planner.ui.widgets.constraint_grid import ConstraintGrid

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 1)


@pytest.fixture()
def loaded_conn():
    conn = connect(":memory:")
    import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    yield conn
    conn.close()


def test_dashboard_shows_alerts_and_upcoming(qtbot, loaded_conn):
    view = DashboardView(loaded_conn)
    qtbot.addWidget(view)
    view.refresh(today=date(2026, 10, 20))  # 8 jours avant l'intra du 28
    assert "MAT1720" in view.upcoming.text()
    assert "J−8" in view.upcoming.text()


def test_dashboard_progress_counts_done_hours(qtbot, loaded_conn):
    course = repos.list_courses(loaded_conn)[0]
    ev = repos.list_evaluations(loaded_conn, course_id=course.id)[0]
    bid = repos.insert_study_block(
        loaded_conn, ev.id, datetime(2026, 9, 2, 9, 0), datetime(2026, 9, 2, 11, 0)
    )
    repos.update_study_block_status(loaded_conn, bid, "done")
    view = DashboardView(loaded_conn)
    qtbot.addWidget(view)
    view.refresh(today=TODAY)
    assert view.history_chart.rows, "l'historique hebdomadaire doit apparaître"
    assert view.course_chart.rows, "la charge par cours doit apparaître"


def test_settings_view_save_persists(qtbot, loaded_conn):
    view = SettingsView(loaded_conn)
    qtbot.addWidget(view)
    view.alpha.setValue(0.8)
    view.h_week.setValue(5.0)
    view._save()
    loaded = load_engine_settings(loaded_conn)
    assert loaded.alpha == 0.8
    assert loaded.h_jour_max_week == 5.0


def test_settings_reset_restores_defaults(qtbot, loaded_conn):
    view = SettingsView(loaded_conn)
    qtbot.addWidget(view)
    view.alpha.setValue(0.9)
    view._reset()
    assert view.alpha.value() == 0.6


def test_grid_paint_and_save(qtbot, loaded_conn):
    grid = ConstraintGrid(loaded_conn)
    qtbot.addWidget(grid)
    # peindre lundi 09:00-10:00 (rangées 2-3) en 'travail'
    grid.category.setCurrentText("travail")
    grid.table.setRangeSelected(
        __import__("PySide6.QtWidgets", fromlist=["QTableWidgetSelectionRange"])
        .QTableWidgetSelectionRange(2, 0, 3, 0), True
    )
    grid._paint()
    grid._save()
    weekly = [c for c in repos.list_constraints(loaded_conn) if c.weekday is not None]
    assert len(weekly) == 1
    assert weekly[0].category == "travail"
    assert weekly[0].start.strftime("%H:%M") == "09:00"
    assert weekly[0].end.strftime("%H:%M") == "10:00"


def test_grid_undo(qtbot, loaded_conn):
    grid = ConstraintGrid(loaded_conn)
    qtbot.addWidget(grid)
    from PySide6.QtWidgets import QTableWidgetSelectionRange

    grid.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, 0), True)
    grid._paint()
    assert grid.cells
    grid._undo()
    assert not grid.cells
