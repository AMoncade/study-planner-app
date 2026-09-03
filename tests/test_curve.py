"""Tests des étapes B et C : fenêtre de révision et courbe de répartition."""

from datetime import date, datetime, timedelta

from planner.config import EngineSettings
from planner.core.models import Evaluation
from planner.scheduler.curve import day_targets, distribution, revision_window

S = EngineSettings()
TODAY = date(2026, 9, 1)


def make_eval(**kwargs) -> Evaluation:
    defaults = dict(
        id=1, course_id=1, external_id="X-E1", title="E", type="examen_intra",
        weight=30.0, due_at=datetime(2026, 10, 20, 8, 0),
    )
    defaults.update(kwargs)
    return Evaluation(**defaults)


# ---------------------------------------------------------------- fenêtre (B)


def test_window_exam_covers_full_remaining_horizon():
    # décision 2026-09-02 : la fenêtre d'un examen s'étend toujours jusqu'à aujourd'hui
    ev = make_eval(type="examen_intra")
    window = revision_window(ev, TODAY, S)
    assert window == (TODAY, date(2026, 10, 19))  # veille incluse, jour J exclu


def test_window_depth_by_type_non_exam():
    ev = make_eval(type="laboratoire", due_at=datetime(2026, 10, 20, 8, 0))  # D = 7
    window = revision_window(ev, TODAY, S)
    assert window == (date(2026, 10, 13), date(2026, 10, 19))


def test_window_clipped_by_today():
    ev = make_eval(due_at=datetime(2026, 9, 8, 8, 0))
    window = revision_window(ev, TODAY, S)
    assert window == (TODAY, date(2026, 9, 7))


def test_window_travail_starts_at_start_date():
    ev = make_eval(
        type="travail", due_at=datetime(2026, 11, 17, 23, 59),
        start_date=date(2026, 11, 3),
    )
    window = revision_window(ev, TODAY, S)
    assert window[0] == date(2026, 11, 3)  # plus tardive que T-21


def test_window_none_when_too_late():
    ev = make_eval(due_at=datetime(2026, 8, 30, 8, 0))
    assert revision_window(ev, TODAY, S) is None


def test_window_none_without_due_date():
    assert revision_window(make_eval(due_at=None), TODAY, S) is None


# ---------------------------------------------------------------- courbe (C)


def test_distribution_sums_to_one():
    p = distribution(14, S)
    assert abs(sum(p.values()) - 1.0) < 1e-9
    assert set(p) == set(range(1, 15))


def test_distribution_decreasing_with_distance():
    p = distribution(14, S)
    values = [p[t] for t in range(1, 15)]
    assert values == sorted(values, reverse=True)


def test_distribution_floor_keeps_far_days_nonzero():
    p = distribution(14, S)
    assert p[14] >= S.lam / 14 / 2  # le plancher λ garantit l'étalement


def test_day_targets_sum_close_to_total():
    days = [date(2026, 10, d) for d in range(6, 20)]
    capacities = dict.fromkeys(days, 4.0)
    targets = day_targets(10.0, days, date(2026, 10, 20), capacities, S)
    assert abs(sum(targets.values()) - 10.0) <= 1.0  # arrondis 0,5 + plafond journalier


def test_day_targets_redistributes_blocked_days():
    days = [date(2026, 10, d) for d in range(6, 20)]
    capacities = dict.fromkeys(days, 4.0)
    capacities[date(2026, 10, 19)] = 0.0  # veille indisponible
    targets = day_targets(10.0, days, date(2026, 10, 20), capacities, S)
    assert targets.get(date(2026, 10, 19), 0.0) == 0.0
    assert sum(targets.values()) >= 8.5  # la masse est redistribuée, pas perdue


def test_day_targets_respect_per_day_cap():
    days = [date(2026, 10, 18), date(2026, 10, 19)]
    capacities = dict.fromkeys(days, 6.0)
    targets = day_targets(10.0, days, date(2026, 10, 20), capacities, S)
    assert all(v <= S.h_jour_eval for v in targets.values())


def test_day_targets_preserve_mass_on_long_windows():
    # fenêtre longue : cibles journalières < 0,5 h — la masse ne doit PAS disparaître
    # par arrondi (l'agrégation en blocs se fait au placement, via le carry)
    days = [date(2026, 9, 1) + timedelta(days=i) for i in range(90)]
    capacities = dict.fromkeys(days, 4.0)
    targets = day_targets(20.0, days, date(2026, 11, 30), capacities, S)
    assert abs(sum(targets.values()) - 20.0) < 1e-6
