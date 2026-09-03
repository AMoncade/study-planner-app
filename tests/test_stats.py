"""Tests du module pur d'agrégats statistiques (vue Statistiques, phase 14)."""

from datetime import datetime

import pytest

from planner.core.models import Course, Evaluation, StudyBlock
from planner.scheduler.stats import (
    attendance,
    compute_overview,
    hours_by_course,
    weekly_hours,
)

NOW = datetime(2026, 9, 3, 12, 0)  # jeudi, semaine ISO 36


def _block(block_id, start, minutes=60, status="planned",
           actual=None, efficiency=None, evaluation_id=1):
    from datetime import timedelta
    return StudyBlock(
        id=block_id, evaluation_id=evaluation_id, start_at=start,
        end_at=start + timedelta(minutes=minutes), planned_minutes=minutes,
        status=status, actual_minutes=actual, efficiency=efficiency,
    )


def _course(course_id, code):
    return Course(id=course_id, code=code, title=code, term="A26")


def _evaluation(eval_id, course_id):
    return Evaluation(id=eval_id, course_id=course_id, external_id=f"E{eval_id}",
                      title=f"Éval {eval_id}", type="examen_intra", weight=20.0)


# ------------------------------------------------------------------ vue d'ensemble

def test_overview_empty():
    stats = compute_overview([], NOW)
    assert stats.done_hours == 0.0
    assert stats.due_blocks == 0
    assert stats.completion_rate is None
    assert stats.avg_efficiency is None
    assert stats.plan_delta_hours == 0.0


def test_overview_future_blocks_excluded_from_rates():
    blocks = [
        _block(1, datetime(2026, 9, 1, 9), 120, status="done"),      # échu, fait
        _block(2, datetime(2026, 9, 2, 9), 60, status="skipped"),    # échu, manqué
        _block(3, datetime(2026, 9, 10, 9), 90, status="planned"),   # futur : hors taux
    ]
    stats = compute_overview(blocks, NOW)
    assert stats.due_blocks == 2
    assert stats.completed_due_blocks == 1
    assert stats.completion_rate == 0.5
    # heures planifiées échues : 120 + 60 min = 3 h (le bloc futur est exclu)
    assert stats.planned_due_hours == 3.0


def test_overview_partial_counts_actual_minutes():
    blocks = [
        _block(1, datetime(2026, 9, 1, 9), 120, status="partial", actual=45),
        _block(2, datetime(2026, 9, 2, 9), 60, status="done"),  # sans minutes réelles
    ]
    stats = compute_overview(blocks, NOW)
    # 45 min réelles + 60 min planifiées (repli quand actual_minutes est absent)
    assert stats.done_hours == 1.75
    assert stats.completion_rate == 1.0


def test_overview_efficiency_ignores_missing():
    blocks = [
        _block(1, datetime(2026, 9, 1, 9), 60, status="done", efficiency=0.8),
        _block(2, datetime(2026, 9, 1, 11), 60, status="done", efficiency=None),
        _block(3, datetime(2026, 9, 2, 9), 60, status="done", efficiency=0.4),
        # partiel avec efficacité : hors moyenne (blocs faits seulement)
        _block(4, datetime(2026, 9, 2, 11), 60, status="partial", efficiency=1.0),
    ]
    stats = compute_overview(blocks, NOW)
    assert stats.avg_efficiency == pytest.approx(0.6)


def test_overview_plan_delta_signed():
    # 1 h faite pour 3 h planifiées échues -> retard de 2 h (écart négatif)
    blocks = [
        _block(1, datetime(2026, 9, 1, 9), 60, status="done"),
        _block(2, datetime(2026, 9, 1, 11), 60, status="skipped"),
        _block(3, datetime(2026, 9, 2, 9), 60, status="planned"),
    ]
    stats = compute_overview(blocks, NOW)
    assert stats.plan_delta_hours == -2.0

    # 2 h faites pour 1 h planifiée échue -> avance de 1 h (écart positif)
    ahead = [
        _block(1, datetime(2026, 9, 1, 9), 60, status="done", actual=120),
    ]
    assert compute_overview(ahead, NOW).plan_delta_hours == 1.0


# ------------------------------------------------------------------ semaines

def test_weekly_hours_empty():
    assert weekly_hours([], NOW) == []


def test_weekly_hours_fills_empty_weeks():
    blocks = [
        _block(1, datetime(2026, 8, 18, 9), 60, status="done"),     # semaine 34
        _block(2, datetime(2026, 9, 1, 9), 120, status="partial", actual=90),  # sem. 36
        _block(3, datetime(2026, 9, 8, 9), 60),                     # semaine 37, futur
    ]
    weeks = weekly_hours(blocks, NOW)
    assert [w.week for w in weeks] == [34, 35, 36, 37]
    assert weeks[0].done_hours == 1.0
    assert weeks[1].planned_hours == 0.0  # semaine vide intercalée
    assert weeks[1].done_hours == 0.0
    assert weeks[2].done_hours == 1.5
    assert weeks[3].planned_hours == 1.0
    assert weeks[3].done_hours == 0.0
    assert [w.is_current for w in weeks] == [False, False, True, False]
    assert weeks[0].label == "s34"


# ------------------------------------------------------------------ par cours

def test_hours_by_course_color_follows_course():
    courses = [_course(10, "MAT1000"), _course(20, "MAT1720")]
    evaluations = [_evaluation(1, 10), _evaluation(2, 20)]
    blocks = [
        _block(1, datetime(2026, 9, 1, 9), 60, status="done", evaluation_id=2),
        _block(2, datetime(2026, 9, 2, 9), 120, evaluation_id=1),
    ]
    rows = hours_by_course(blocks, evaluations, courses)
    assert [(r.code, r.color_index) for r in rows] == [("MAT1000", 0), ("MAT1720", 1)]
    assert rows[0].done_hours == 0.0
    assert rows[0].planned_hours == 2.0
    assert rows[1].done_hours == 1.0


# ------------------------------------------------------------------ assiduité

def test_attendance_counts_due_blocks_only():
    blocks = [
        _block(1, datetime(2026, 9, 1, 9), 60, status="done"),
        _block(2, datetime(2026, 9, 1, 11), 60, status="partial", actual=30),
        _block(3, datetime(2026, 9, 2, 9), 60, status="skipped"),
        _block(4, datetime(2026, 9, 2, 11), 60, status="planned"),   # échu, non renseigné
        _block(5, datetime(2026, 9, 10, 9), 60, status="planned"),   # futur : exclu
    ]
    stats = attendance(blocks, NOW)
    assert (stats.done, stats.partial, stats.skipped, stats.pending) == (1, 1, 1, 1)
