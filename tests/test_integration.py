"""Bout-en-bout sur les 4 fixtures réelles : JSON -> base -> plan -> métriques.

Les valeurs figées ici sont des RÉGRESSIONS avec les coefficients par défaut de §4.9.
Après calibration manuelle (Phase 2, §4.9), les re-figer en connaissance de cause.
"""

from datetime import date
from pathlib import Path

import pytest

from planner.config import EngineSettings
from planner.core.importer import import_course_file
from planner.scheduler.placer import plan
from planner.storage import repositories as repos
from planner.storage.db import connect

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 1)
S = EngineSettings()


@pytest.fixture()
def loaded_conn():
    conn = connect(":memory:")
    for name in ("mat1000_a26.json", "mat1400_a26.json", "mat1600_a26.json",
                 "mat1720_a26.json"):
        import_course_file(conn, FIXTURES / name, today=TODAY)
    yield conn
    conn.close()


def test_full_semester_plan(loaded_conn):
    courses = repos.list_courses(loaded_conn)
    evaluations = [
        e for c in courses for e in repos.list_evaluations(loaded_conn, course_id=c.id)
    ]
    result = plan(courses, evaluations, [], S, TODAY)

    # invariants durs
    assert result.blocks
    for b in result.blocks:
        minutes = (b.end_at - b.start_at).total_seconds() / 60
        assert 60 <= minutes <= 120

    # les bonus (poids 0) et le quiz sans date sont exclus, rien d'autre
    assert set(result.exclusions) == {
        "MAT1400-BONUS1", "MAT1400-BONUS2", "MAT1600-QUIZTP",
    }

    # régression : charges cibles totales avec les coefficients par défaut
    assert result.metrics.total_target_hours == pytest.approx(174.0)
    assert result.rho == 1.0  # le trimestre entier tient (la crête de décembre, non)
    assert result.metrics.coverage >= 0.85
    assert result.metrics.peak_hours <= S.h_jour_max_weekend

    # les finaux de décembre s'entassent : le déficit doit être signalé, pas caché
    assert any(d > 0 for d in result.deficits.values())


def test_plan_determinism_on_real_data(loaded_conn):
    courses = repos.list_courses(loaded_conn)
    evaluations = [
        e for c in courses for e in repos.list_evaluations(loaded_conn, course_id=c.id)
    ]
    r1 = plan(courses, evaluations, [], S, TODAY)
    r2 = plan(courses, evaluations, [], S, TODAY)
    assert [(b.evaluation_id, b.start_at) for b in r1.blocks] == \
           [(b.evaluation_id, b.start_at) for b in r2.blocks]


def test_sessions_block_study_time(loaded_conn):
    """Aucun bloc d'étude ne chevauche une séance de cours réelle."""
    from planner.scheduler.availability import build_grid, slot_index

    courses = repos.list_courses(loaded_conn)
    evaluations = [
        e for c in courses for e in repos.list_evaluations(loaded_conn, course_id=c.id)
    ]
    result = plan(courses, evaluations, [], S, TODAY)
    horizon_end = max(b.end_at.date() for b in result.blocks)
    grid = build_grid(TODAY, horizon_end, [], courses, S)
    for b in result.blocks:
        day = grid[b.start_at.date()]
        start = slot_index(b.start_at.time())
        for i in range(start, start + b.planned_minutes // 30):
            assert day[i], f"bloc {b.start_at} sur un créneau occupé (séance/éveil)"
