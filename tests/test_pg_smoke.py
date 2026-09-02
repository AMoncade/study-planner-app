"""Test de fumée Postgres (Supabase, pooler transaction) — Phase 8a.

Sauté automatiquement si DATABASE_URL est absent (environnement ou .env du dépôt).
Ré-exécutable : les tables sont tronquées au début.
"""

import os
from datetime import date, datetime
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL absent : test Postgres sauté",
)

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 2)
TABLES = ("study_blocks", "generations", "constraints", "evaluations",
          "sessions", "courses", "settings")


@pytest.fixture(scope="module")
def pg_conn():
    from planner.storage.pg import connect_pg

    conn = connect_pg()
    with conn:
        conn.execute(
            f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"
        )
    yield conn
    conn.close()


def test_import_all_fixtures(pg_conn):
    from planner.core.importer import import_course_file
    from planner.storage import repositories as repos

    for name in ("mat1000_a26.json", "mat1400_a26.json",
                 "mat1600_a26.json", "mat1720_a26.json"):
        report = import_course_file(pg_conn, FIXTURES / name, today=TODAY)
        assert report.created > 0

    courses = repos.list_courses(pg_conn)
    assert len(courses) == 4
    evaluations = [
        e for c in courses for e in repos.list_evaluations(pg_conn, course_id=c.id)
    ]
    assert len(evaluations) == 28


def test_plan_from_postgres_data(pg_conn):
    from planner.config import EngineSettings
    from planner.scheduler.placer import plan
    from planner.storage import repositories as repos

    courses = repos.list_courses(pg_conn)
    evaluations = [
        e for c in courses for e in repos.list_evaluations(pg_conn, course_id=c.id)
    ]
    result = plan(courses, evaluations, [], EngineSettings(), TODAY)
    assert len(result.blocks) > 100


def test_study_block_roundtrip(pg_conn):
    from planner.storage import repositories as repos

    course = repos.list_courses(pg_conn)[0]
    ev = repos.list_evaluations(pg_conn, course_id=course.id)[0]
    bid = repos.insert_study_block(
        pg_conn, ev.id, datetime(2026, 9, 10, 9, 0), datetime(2026, 9, 10, 10, 30)
    )
    assert isinstance(bid, int)
    repos.update_study_block_status(pg_conn, bid, "done", actual_minutes=80,
                                    efficiency=0.9)
    block = next(b for b in repos.list_study_blocks(pg_conn, evaluation_id=ev.id)
                 if b.id == bid)
    assert block.status == "done"
    assert block.actual_minutes == 80
    assert block.efficiency == 0.9
    assert block.planned_minutes == 90


def test_with_conn_does_not_close_connection(pg_conn):
    """Le piège psycopg3 : `with conn:` natif ferme la connexion. Pas l'adaptateur."""
    from planner.storage import repositories as repos

    with pg_conn:
        pg_conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("pg_smoke", "1"),
        )
    # deuxième requête APRÈS la sortie du with : la connexion doit être vivante
    assert repos.get_setting(pg_conn, "pg_smoke") == "1"
    with pytest.raises(RuntimeError), pg_conn:
        pg_conn.execute("SELECT 1").fetchone()
        raise RuntimeError("rollback attendu")
    assert pg_conn.execute("SELECT 1").fetchone()[0] == 1


def test_reimport_reconciliation_on_postgres(pg_conn):
    from planner.core.importer import import_course_file

    report = import_course_file(pg_conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    assert report.created == 0
    assert report.unchanged == 2
