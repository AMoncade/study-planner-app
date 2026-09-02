"""Tests de la synchronisation SQLite <-> Postgres (Phase 8c).

⚠ DESTRUCTIF côté Postgres : push TRONQUE les tables de la base visée. Comme
test_pg_smoke, ces tests n'utilisent que DATABASE_URL_TEST (sautés si absente) et
refusent une URL identique à DATABASE_URL sans opt-in PG_TEST_ALLOW_TRUNCATE=1.
"""

import os
from datetime import date, datetime
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TEST_URL = os.environ.get("DATABASE_URL_TEST")

pytestmark = pytest.mark.skipif(
    not TEST_URL,
    reason="DATABASE_URL_TEST absent : tests de synchronisation sautés",
)

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 2)


def _snapshot(conn) -> dict:
    """État comparable d'une base : comptes par table + (id, statut) des blocs."""
    from planner.sync import TABLES_IN_DEPENDENCY_ORDER

    state = {
        table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in TABLES_IN_DEPENDENCY_ORDER
    }
    state["blocks"] = sorted(
        tuple(r) for r in
        conn.execute("SELECT id, evaluation_id, start_at, status FROM study_blocks")
    )
    return state


@pytest.fixture(scope="module")
def sqlite_conn():
    from planner.config import EngineSettings
    from planner.core.importer import import_course_file
    from planner.scheduler.placer import plan
    from planner.storage import repositories as repos
    from planner.storage.db import connect

    conn = connect(":memory:")
    for name in ("mat1000_a26.json", "mat1400_a26.json",
                 "mat1600_a26.json", "mat1720_a26.json"):
        import_course_file(conn, FIXTURES / name, today=TODAY)
    courses = repos.list_courses(conn)
    evaluations = [
        e for c in courses for e in repos.list_evaluations(conn, course_id=c.id)
    ]
    result = plan(courses, evaluations, [], EngineSettings(), TODAY)
    for b in result.blocks:
        repos.insert_study_block(conn, b.evaluation_id, b.start_at, b.end_at)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def pg_conn():
    from planner.storage.pg import connect_pg

    if (os.environ.get("DATABASE_URL") == TEST_URL
            and os.environ.get("PG_TEST_ALLOW_TRUNCATE") != "1"):
        pytest.fail(
            "DATABASE_URL_TEST est identique à DATABASE_URL : push TRONQUE la base "
            "visée. Pointer DATABASE_URL_TEST vers une base jetable, ou poser "
            "PG_TEST_ALLOW_TRUNCATE=1 en toute connaissance de cause."
        )
    conn = connect_pg(url=TEST_URL)
    yield conn
    conn.close()


def test_push_replicates_counts_and_ids(sqlite_conn, pg_conn):
    from planner.sync import TABLES_IN_DEPENDENCY_ORDER, push

    counters = push(sqlite_conn, pg_conn)
    assert counters["courses"] == 4
    assert counters["evaluations"] == 28
    assert counters["study_blocks"] > 100
    for table in TABLES_IN_DEPENDENCY_ORDER:
        sqlite_count = sqlite_conn.execute(
            f"SELECT count(*) FROM {table}").fetchone()[0]
        pg_count = pg_conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        assert (counters[table], pg_count) == (sqlite_count, sqlite_count), table
    for table in ("courses", "evaluations", "study_blocks"):
        sqlite_ids = [r[0] for r in sqlite_conn.execute(
            f"SELECT id FROM {table} ORDER BY id")]
        pg_ids = [r[0] for r in pg_conn.execute(
            f"SELECT id FROM {table} ORDER BY id")]
        assert sqlite_ids == pg_ids, table


def test_identity_sequences_rebased_after_push(sqlite_conn, pg_conn):
    """Sans setval, cette insertion lèverait une violation d'unicité sur id=1."""
    from planner.storage import repositories as repos

    max_id = pg_conn.execute("SELECT max(id) FROM study_blocks").fetchone()[0]
    ev_id = pg_conn.execute("SELECT id FROM evaluations ORDER BY id").fetchone()[0]
    new_id = repos.insert_study_block(
        pg_conn, ev_id, datetime(2026, 9, 20, 9, 0), datetime(2026, 9, 20, 10, 0)
    )
    assert new_id == max_id + 1


def test_pull_brings_back_status_only(sqlite_conn, pg_conn):
    from planner.storage import repositories as repos
    from planner.sync import pull

    target = pg_conn.execute(
        "SELECT id FROM study_blocks ORDER BY id").fetchone()[0]
    repos.update_study_block_status(pg_conn, target, "done", actual_minutes=75,
                                    efficiency=1.1)

    before = _snapshot(sqlite_conn)
    counters = pull(pg_conn, sqlite_conn)

    # le bloc ajouté côté Postgres au test précédent n'existe pas côté SQLite
    assert counters["orphelins"] == 1
    assert counters["mis_a_jour"] == counters["blocs_web"] - 1

    row = sqlite_conn.execute(
        "SELECT status, actual_minutes, efficiency FROM study_blocks WHERE id = ?",
        (target,),
    ).fetchone()
    assert row == ("done", 75, 1.1)

    after = _snapshot(sqlite_conn)
    # rien d'autre n'a changé : mêmes comptes partout, mêmes blocs (id, éval, début),
    # seule la ligne cochée a changé de statut
    assert {t: after[t] for t in after if t != "blocks"} == \
           {t: before[t] for t in before if t != "blocks"}
    changed = set(after["blocks"]) ^ set(before["blocks"])
    assert {r[0] for r in changed} == {target}


def test_push_is_idempotent(sqlite_conn, pg_conn):
    from planner.sync import push

    first = push(sqlite_conn, pg_conn)
    state_one = _snapshot(pg_conn)
    second = push(sqlite_conn, pg_conn)
    state_two = _snapshot(pg_conn)
    assert first == second
    assert state_one == state_two
    # et Postgres est bien l'exact reflet de SQLite (le bloc web surnuméraire a disparu)
    assert state_one == _snapshot(sqlite_conn)
