"""Tests du stockage SQLite : migrations, aller-retour, contraintes et réglages."""

from datetime import date, datetime, time
from pathlib import Path

import pytest

from planner.core.models import Constraint
from planner.storage import repositories as repos
from planner.storage.db import SCHEMA_VERSION, backup_database, connect

TODAY = date(2026, 9, 1)


@pytest.fixture()
def conn():
    c = connect(":memory:")
    yield c
    c.close()


def test_migrations_applied(conn):
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    tables = {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"courses", "sessions", "evaluations", "constraints",
            "study_blocks", "settings", "generations"} <= tables


def test_migrate_is_idempotent(tmp_path):
    path = tmp_path / "t.db"
    c1 = connect(path)
    c1.close()
    c2 = connect(path)  # ré-ouverture : aucune migration à refaire
    assert c2.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    c2.close()


def test_constraint_roundtrip(conn):
    constraint = Constraint(
        id=None, label="Travail", category="travail", weekday=2,
        specific_date=None, start=time(17, 0), end=time(21, 0),
    )
    cid = repos.insert_constraint(conn, constraint)
    loaded = repos.list_constraints(conn)
    assert len(loaded) == 1
    assert loaded[0].id == cid
    assert loaded[0].label == "Travail"
    assert loaded[0].weekday == 2
    assert loaded[0].start == time(17, 0)

    repos.delete_constraint(conn, cid)
    assert repos.list_constraints(conn) == []


def test_specific_date_constraint(conn):
    constraint = Constraint(
        id=None, label="Rendez-vous", category="personnel", weekday=None,
        specific_date=date(2026, 10, 3), start=time(9, 0), end=time(10, 0),
    )
    repos.insert_constraint(conn, constraint)
    loaded = repos.list_constraints(conn)[0]
    assert loaded.specific_date == date(2026, 10, 3)
    assert loaded.weekday is None


def test_settings_roundtrip(conn):
    assert repos.get_setting(conn, "inexistant") is None
    assert repos.get_setting(conn, "inexistant", default="x") == "x"
    repos.set_setting(conn, "h_jour_max_semaine", "4.0")
    assert repos.get_setting(conn, "h_jour_max_semaine") == "4.0"
    repos.set_setting(conn, "h_jour_max_semaine", "5.0")
    assert repos.get_setting(conn, "h_jour_max_semaine") == "5.0"


def test_study_block_status_update(conn):
    from planner.core.importer import import_course_file
    import_course_file(conn, Path(__file__).parent / "fixtures" / "mat1000_a26.json", today=TODAY)
    course = repos.list_courses(conn)[0]
    ev = repos.list_evaluations(conn, course_id=course.id)[0]
    bid = repos.insert_study_block(
        conn, ev.id, datetime(2026, 9, 10, 9, 0), datetime(2026, 9, 10, 10, 30)
    )
    repos.update_study_block_status(conn, bid, "done", actual_minutes=80, efficiency=0.9)
    block = repos.list_study_blocks(conn, evaluation_id=ev.id)[0]
    assert block.status == "done"
    assert block.actual_minutes == 80
    assert block.efficiency == 0.9
    assert block.planned_minutes == 90


def test_backup_database(tmp_path):
    path = tmp_path / "plan.db"
    c = connect(path)
    c.close()
    dest = backup_database(path)
    assert dest is not None
    assert dest.exists()
    assert dest.parent.name == "backups"
    assert backup_database(tmp_path / "absent.db") is None
