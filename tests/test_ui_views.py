"""Tests pytest-qt de fumée : ouverture des vues, import via l'interface, édition."""

from datetime import date
from pathlib import Path

import pytest

from planner.core.importer import import_course_file
from planner.storage import repositories as repos
from planner.storage.db import connect
from planner.ui.main_window import MainWindow
from planner.ui.models.course_tree import COL_DIFFICULTY, COL_OVERRIDE, CourseTreeModel
from planner.ui.views.constraints_view import ConstraintDialog

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 1)


@pytest.fixture()
def conn():
    c = connect(":memory:")
    yield c
    c.close()


@pytest.fixture()
def loaded_conn(conn):
    import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    return conn


def test_main_window_opens_and_navigates(qtbot, loaded_conn):
    window = MainWindow(loaded_conn)
    qtbot.addWidget(window)
    assert window.stack.count() == 6
    for row in range(window.nav.count()):
        window.nav.setCurrentRow(row)
        assert window.stack.currentIndex() == row
    assert "1 cours" in window.statusBar().currentMessage()


def test_import_view_loads_and_imports(qtbot, conn):
    window = MainWindow(conn)
    qtbot.addWidget(window)
    view = window.import_view
    view.load_file(FIXTURES / "mat1000_a26.json")
    assert view.import_button.isEnabled()
    assert view.preview.rowCount() == 4
    with qtbot.waitSignal(view.imported, timeout=2000):
        view.import_button.click()
    assert {c.code for c in repos.list_courses(conn)} == {"MAT1000"}
    assert "4 évaluations" in window.statusBar().currentMessage()


def test_import_view_imports_ics_schedule(qtbot, loaded_conn):
    # MAT1720 est en base sans séance ; l'horaire .ics doit les créer.
    window = MainWindow(loaded_conn)
    qtbot.addWidget(window)
    view = window.import_view
    with qtbot.waitSignal(view.imported, timeout=2000):
        view.import_ics(FIXTURES / "horaire_a26.ics")
    assert "séance(s) créée(s)" in view.status.text()
    course = next(c for c in repos.list_courses(loaded_conn) if c.code == "MAT1720")
    assert len(course.sessions) == 1


def test_import_view_rejects_bad_file(qtbot, conn, tmp_path):
    window = MainWindow(conn)
    qtbot.addWidget(window)
    bad = tmp_path / "bad.json"
    bad.write_text("{ pas du json", encoding="utf-8")
    window.import_view.load_file(bad)
    assert not window.import_view.import_button.isEnabled()


def test_course_tree_edit_difficulty_persists(qtbot, loaded_conn):
    model = CourseTreeModel(loaded_conn)
    course_index = model.index(0, COL_DIFFICULTY)
    assert model.setData(course_index, 5)
    assert repos.list_courses(loaded_conn)[0].difficulty == 5


def test_course_tree_edit_override_persists(qtbot, loaded_conn):
    model = CourseTreeModel(loaded_conn)
    parent = model.index(0, 0)
    eval_index = model.index(0, COL_OVERRIDE, parent)
    assert model.setData(eval_index, "12")
    course = repos.list_courses(loaded_conn)[0]
    evals = repos.list_evaluations(loaded_conn, course_id=course.id)
    assert any(e.manual_hours_override == 12.0 for e in evals)
    # effacement -> retour au calcul automatique
    model2 = CourseTreeModel(loaded_conn)
    eval_index2 = model2.index(0, COL_OVERRIDE, model2.index(0, 0))
    assert model2.setData(eval_index2, "")
    evals = repos.list_evaluations(loaded_conn, course_id=course.id)
    assert all(e.manual_hours_override is None for e in evals)


def test_constraint_dialog_roundtrip(qtbot, conn):
    dialog = ConstraintDialog(weekly=True)
    qtbot.addWidget(dialog)
    dialog.label_edit.setText("Travail")
    dialog.category.setCurrentText("travail")
    dialog.weekday.setCurrentIndex(2)
    constraint = dialog.to_constraint()
    assert constraint.weekday == 2
    assert constraint.category == "travail"
    cid = repos.insert_constraint(conn, constraint)
    assert repos.list_constraints(conn)[0].id == cid


def test_constraints_view_lists_and_free_time(qtbot, loaded_conn):
    window = MainWindow(loaded_conn)
    qtbot.addWidget(window)
    view = window.constraints_view
    from datetime import time

    from planner.core.models import Constraint
    repos.insert_constraint(loaded_conn, Constraint(
        id=None, label="Gym", category="entrainement", weekday=1,
        specific_date=None, start=time(18, 0), end=time(20, 0),
    ))
    view.refresh()
    assert view.weekly_table.table.rowCount() == 1
    assert "Temps libre" in view.free_label.text()
