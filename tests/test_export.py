"""Tests de l'export .ics et PDF (Phase 6)."""

from datetime import date, datetime
from pathlib import Path

import pytest
from icalendar import Calendar

from planner.core.importer import import_course_file
from planner.export import export_ics
from planner.storage import repositories as repos
from planner.storage.db import backup_database, connect, restore_database

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 1)


@pytest.fixture()
def loaded_conn():
    conn = connect(":memory:")
    import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    yield conn
    conn.close()


def test_export_ics_contains_deadlines_and_blocks(loaded_conn, tmp_path):
    course = repos.list_courses(loaded_conn)[0]
    ev = repos.list_evaluations(loaded_conn, course_id=course.id)[0]
    repos.insert_study_block(
        loaded_conn, ev.id, datetime(2026, 10, 20, 9, 0), datetime(2026, 10, 20, 11, 0)
    )
    skipped = repos.insert_study_block(
        loaded_conn, ev.id, datetime(2026, 10, 21, 9, 0), datetime(2026, 10, 21, 11, 0)
    )
    repos.update_study_block_status(loaded_conn, skipped, "skipped")

    out = tmp_path / "plan.ics"
    count = export_ics(loaded_conn, out)
    assert count == 3  # 2 échéances + 1 bloc (le bloc manqué est exclu)

    calendar = Calendar.from_ical(out.read_bytes())
    summaries = [str(e.get("summary")) for e in calendar.walk("VEVENT")]
    assert any("Étude" in s for s in summaries)
    assert any("Intra" in s for s in summaries)
    deadline = next(e for e in calendar.walk("VEVENT")
                    if str(e.get("uid")).startswith("due-MAT1720-INTRA"))
    assert deadline.decoded("dtstart") == datetime(2026, 10, 28, 15, 30)


def test_export_pdf_of_week(qtbot, loaded_conn, tmp_path):
    from planner.ui.views.schedule_view import ScheduleView

    view = ScheduleView(loaded_conn)
    qtbot.addWidget(view)
    view.resize(1000, 600)
    out = tmp_path / "semaine.pdf"
    view.export_pdf(str(out))
    assert out.exists() and out.stat().st_size > 1000
    assert out.read_bytes()[:5] == b"%PDF-"


def test_restore_database(tmp_path):
    db = tmp_path / "plan.db"
    conn = connect(db)
    repos.set_setting(conn, "marqueur", "avant")
    conn.close()
    saved = backup_database(db)

    conn = connect(db)
    repos.set_setting(conn, "marqueur", "après")
    conn.close()

    restore_database(db, saved)
    conn = connect(db)
    assert repos.get_setting(conn, "marqueur") == "avant"
    conn.close()
