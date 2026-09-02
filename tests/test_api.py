"""Tests de l'API web (Phase 9) — TestClient FastAPI contre la base Postgres de test.

Sautés sans DATABASE_URL_TEST, même garde-fou d'égalité que test_sync (le seeding
passe par sync.push, qui tronque la base visée).
"""

import os
import secrets as pysecrets
from datetime import date
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TEST_URL = os.environ.get("DATABASE_URL_TEST")

pytestmark = pytest.mark.skipif(
    not TEST_URL,
    reason="DATABASE_URL_TEST absent : tests API sautés",
)

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 2)
TEST_PIN = pysecrets.token_hex(4)  # PIN jetable, jamais affiché
GOOD = {"X-App-Pin": TEST_PIN}


@pytest.fixture(scope="module")
def client():
    if (os.environ.get("DATABASE_URL") == TEST_URL
            and os.environ.get("PG_TEST_ALLOW_TRUNCATE") != "1"):
        pytest.fail(
            "DATABASE_URL_TEST est identique à DATABASE_URL : le seeding TRONQUE la "
            "base visée. Pointer DATABASE_URL_TEST vers une base jetable."
        )
    # ---- seeding : SQLite en mémoire -> push vers la base de test
    from planner.config import EngineSettings
    from planner.core.importer import import_course_file
    from planner.scheduler.placer import plan
    from planner.storage import repositories as repos
    from planner.storage.db import connect
    from planner.storage.pg import connect_pg
    from planner.sync import push

    sqlite_conn = connect(":memory:")
    for name in ("mat1000_a26.json", "mat1400_a26.json",
                 "mat1600_a26.json", "mat1720_a26.json"):
        import_course_file(sqlite_conn, FIXTURES / name, today=TODAY)
    courses = repos.list_courses(sqlite_conn)
    evaluations = [
        e for c in courses for e in repos.list_evaluations(sqlite_conn, course_id=c.id)
    ]
    for b in plan(courses, evaluations, [], EngineSettings(), TODAY).blocks:
        repos.insert_study_block(sqlite_conn, b.evaluation_id, b.start_at, b.end_at)
    pg_conn = connect_pg(url=TEST_URL)
    push(sqlite_conn, pg_conn, force=True)
    pg_conn.close()
    sqlite_conn.close()

    # ---- app : PIN de test + connexions API routées vers la base de test
    saved = {k: os.environ.get(k) for k in ("APP_PIN", "DATABASE_URL")}
    os.environ["APP_PIN"] = TEST_PIN
    os.environ["DATABASE_URL"] = TEST_URL  # _get_db lit DATABASE_URL via connect_pg()

    from fastapi.testclient import TestClient

    from planner.web.api import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture()
def pg(client):
    from planner.storage.pg import connect_pg

    conn = connect_pg(url=TEST_URL, migrate=False)
    yield conn
    conn.close()


def _a_week_with_blocks(client) -> dict:
    """La semaine du 2026-09-07 contient des blocs (offset calculé depuis aujourd'hui)."""
    offset = (date(2026, 9, 7) - (date.today() - __import__("datetime").timedelta(
        days=date.today().weekday()))).days // 7
    return client.get(f"/api/week?offset={offset}", headers=GOOD).json()


def test_health_without_pin(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_week_requires_pin(client):
    assert client.get("/api/week").status_code == 401
    assert client.get("/api/week", headers={"X-App-Pin": "mauvais"}).status_code == 401


def test_week_with_pin_returns_labeled_blocks(client):
    data = _a_week_with_blocks(client)
    assert len(data["days"]) == 7
    blocks = [b for day in data["days"] for b in day["blocks"]]
    assert blocks, "la semaine de test doit contenir des blocs"
    for block in blocks:
        assert block["course"].startswith("MAT")
        assert block["evaluation"]
        assert block["status"] in ("planned", "done", "partial", "skipped")


def test_status_invalid_value_rejected(client, pg):
    block_id = pg.execute("SELECT id FROM study_blocks ORDER BY id").fetchone()[0]
    response = client.post(f"/api/blocks/{block_id}/status", headers=GOOD,
                           json={"status": "sieste"})
    assert response.status_code == 422


def test_status_update_persists(client, pg):
    block_id = pg.execute("SELECT id FROM study_blocks ORDER BY id").fetchone()[0]
    response = client.post(f"/api/blocks/{block_id}/status", headers=GOOD,
                           json={"status": "partial", "actual_minutes": 45})
    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["status"]) == (block_id, "partial")
    row = pg.execute(
        "SELECT status, actual_minutes FROM study_blocks WHERE id = ?", (block_id,)
    ).fetchone()
    assert tuple(row) == ("partial", 45)


def test_status_unknown_block_404(client):
    response = client.post("/api/blocks/999999/status", headers=GOOD,
                           json={"status": "done"})
    assert response.status_code == 404


def test_recalculate_is_pure_preview(client, pg):
    before = pg.execute(
        "SELECT id FROM study_blocks ORDER BY id").fetchall()
    response = client.post("/api/recalculate", headers=GOOD)
    assert response.status_code == 200
    body = response.json()
    assert body["persisted"] is False
    assert set(body["diff"]) == {"kept", "moved", "added", "removed"}
    after = pg.execute(
        "SELECT id FROM study_blocks ORDER BY id").fetchall()
    assert after == before  # même NOMBRE et mêmes id : rien n'a été écrit


def test_index_and_manifest_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Plan-Études" in page.text
    manifest = client.get("/manifest.json")
    assert manifest.status_code == 200
    assert manifest.json()["display"] == "standalone"
