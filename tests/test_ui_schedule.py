"""Tests pytest-qt de la vue Planning : recalcul, statuts, déplacement, verrouillage."""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from planner.core.importer import import_course_file
from planner.storage import repositories as repos
from planner.storage.db import connect
from planner.ui.views.schedule_view import ScheduleView

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 1)
NOW = datetime(2026, 9, 1, 8, 0)


@pytest.fixture()
def loaded_conn():
    conn = connect(":memory:")
    import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    yield conn
    conn.close()


def _eval_ids(conn):
    course = repos.list_courses(conn)[0]
    return [e.id for e in repos.list_evaluations(conn, course_id=course.id)]


def test_recalculate_generates_blocks(qtbot, loaded_conn):
    view = ScheduleView(loaded_conn)
    qtbot.addWidget(view)
    view.recalculate(now=NOW, interactive=False)
    blocks = repos.list_study_blocks(loaded_conn)
    assert blocks, "le recalcul doit produire des blocs"
    assert all(b.status == "planned" for b in blocks)


def test_mark_done_then_recalculate_keeps_history(qtbot, loaded_conn):
    view = ScheduleView(loaded_conn)
    qtbot.addWidget(view)
    view.recalculate(now=NOW, interactive=False)
    first = repos.list_study_blocks(loaded_conn)[0]
    view.set_block_status(first.id, "done")
    view.recalculate(now=NOW, interactive=False)
    blocks = repos.list_study_blocks(loaded_conn)
    done = [b for b in blocks if b.status == "done"]
    assert len(done) == 1 and done[0].id == first.id  # l'historique survit au recalcul


def test_move_block_locks_it(qtbot, loaded_conn):
    view = ScheduleView(loaded_conn)
    qtbot.addWidget(view)
    view.recalculate(now=NOW, interactive=False)
    block = repos.list_study_blocks(loaded_conn)[0]
    new_start = block.start_at + timedelta(hours=2)
    view._move_block(block.id, new_start)
    moved = next(b for b in repos.list_study_blocks(loaded_conn) if b.id == block.id)
    assert moved.start_at == new_start
    assert moved.locked is True
    assert moved.status == "moved"
    # le bloc verrouillé survit à un recalcul
    view.recalculate(now=NOW, interactive=False)
    kept = [b for b in repos.list_study_blocks(loaded_conn) if b.id == block.id]
    assert kept and kept[0].start_at == new_start


def test_toggle_lock_and_delete(qtbot, loaded_conn):
    view = ScheduleView(loaded_conn)
    qtbot.addWidget(view)
    view.recalculate(now=NOW, interactive=False)
    block = repos.list_study_blocks(loaded_conn)[0]
    view.toggle_lock(block.id)
    assert repos.list_study_blocks(loaded_conn)[0].locked is True
    view.toggle_lock(block.id)
    assert repos.list_study_blocks(loaded_conn)[0].locked is False
    count = len(repos.list_study_blocks(loaded_conn))
    view.delete_block(block.id)
    assert len(repos.list_study_blocks(loaded_conn)) == count - 1


def test_banner_counts_week_hours(qtbot, loaded_conn):
    view = ScheduleView(loaded_conn)
    qtbot.addWidget(view)
    view.recalculate(now=NOW, interactive=False)
    view.monday = date(2026, 10, 19)  # semaine de pointe avant l'intra du 28
    view.refresh()
    assert "h planifiées" in view.banner.text()


def test_stability_after_marking_one_done(qtbot, loaded_conn):
    """Marquer un bloc fait puis recalculer ne doit pas chambouler tout le planning."""
    view = ScheduleView(loaded_conn)
    qtbot.addWidget(view)
    view.recalculate(now=NOW, interactive=False)
    before = {
        (b.evaluation_id, b.start_at)
        for b in repos.list_study_blocks(loaded_conn) if b.status == "planned"
    }
    first = min(repos.list_study_blocks(loaded_conn), key=lambda b: b.start_at)
    view.set_block_status(first.id, "done")
    view.recalculate(now=NOW, interactive=False)
    after = {
        (b.evaluation_id, b.start_at)
        for b in repos.list_study_blocks(loaded_conn) if b.status == "planned"
    }
    if before and after:
        overlap = len(before & after) / min(len(before), len(after))
        assert overlap >= 0.5, "P_stabilité doit limiter les déplacements"
