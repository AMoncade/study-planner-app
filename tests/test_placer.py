"""Tests de l'étape E (placement) et G (métriques) : invariants durs et bout-en-bout."""

from datetime import date, datetime, time, timedelta

from planner.config import EngineSettings
from planner.core.models import Constraint, Course, Evaluation
from planner.scheduler.placer import plan

S = EngineSettings()
TODAY = date(2026, 9, 1)


def make_course(**kwargs) -> Course:
    defaults = dict(id=1, code="MAT1000", title="Analyse 1", term="A26")
    defaults.update(kwargs)
    return Course(**defaults)


def make_eval(**kwargs) -> Evaluation:
    defaults = dict(
        id=1, course_id=1, external_id="MAT1000-INTRA", title="Intra",
        type="examen_intra", weight=40.0, due_at=datetime(2026, 9, 20, 8, 0),
        scope_units=4,
    )
    defaults.update(kwargs)
    return Evaluation(**defaults)


def full_day_constraint(weekday: int) -> Constraint:
    return Constraint(
        id=None, label="bloqué", category="travail", weekday=weekday,
        specific_date=None, start=time(0, 0), end=time(23, 59),
    )


def assert_invariants(result, settings=S):
    blocks = result.blocks
    # tailles valides, alignées sur 30 min
    for b in blocks:
        minutes = (b.end_at - b.start_at).total_seconds() / 60
        assert settings.bloc_min * 60 <= minutes <= settings.bloc_max * 60
        assert b.start_at.minute % 30 == 0 and b.end_at.minute % 30 == 0
    # aucun chevauchement, pause >= 15 min entre blocs consécutifs
    ordered = sorted(blocks, key=lambda b: b.start_at)
    for a, b in zip(ordered, ordered[1:], strict=False):
        if a.end_at > b.start_at:
            raise AssertionError(f"chevauchement : {a} / {b}")
        if a.end_at.date() == b.start_at.date():
            assert (b.start_at - a.end_at) >= timedelta(minutes=15)
    # plafonds journaliers
    per_day: dict[date, float] = {}
    for b in blocks:
        per_day.setdefault(b.start_at.date(), 0.0)
        per_day[b.start_at.date()] += (b.end_at - b.start_at).total_seconds() / 3600
    for day, hours in per_day.items():
        cap = settings.h_jour_max_weekend if day.weekday() >= 5 else settings.h_jour_max_week
        assert hours <= cap + 1e-9, f"{day} : {hours} h > plafond {cap}"


def test_single_exam_empty_week():
    result = plan([make_course()], [make_eval()], [], S, TODAY)
    assert result.blocks, "aucun bloc placé"
    assert_invariants(result)
    assert result.deficits.get("MAT1000-INTRA", 0.0) == 0.0
    assert result.rho == 1.0
    # aucun bloc le jour de l'examen ni après
    assert all(b.end_at < datetime(2026, 9, 20, 8, 0) for b in result.blocks)


def test_determinism():
    courses = [make_course()]
    evals = [
        make_eval(),
        make_eval(id=2, external_id="MAT1000-FINAL", type="examen_final",
                  weight=50.0, due_at=datetime(2026, 9, 28, 8, 0)),
    ]
    r1 = plan(courses, evals, [], S, TODAY)
    r2 = plan(courses, evals, [], S, TODAY)
    assert [(b.evaluation_id, b.start_at, b.end_at) for b in r1.blocks] == \
           [(b.evaluation_id, b.start_at, b.end_at) for b in r2.blocks]


def test_two_exams_same_day_both_covered():
    courses = [make_course(), make_course(id=2, code="MAT1600", title="Algèbre")]
    evals = [
        make_eval(),
        make_eval(id=2, course_id=2, external_id="MAT1600-INTRA",
                  due_at=datetime(2026, 9, 20, 13, 0)),
    ]
    result = plan(courses, evals, [], S, TODAY)
    assert_invariants(result)
    placed = {e: 0.0 for e in ("MAT1000-INTRA", "MAT1600-INTRA")}
    by_id = {ev.id: ev.external_id for ev in evals}
    for b in result.blocks:
        placed[by_id[b.evaluation_id]] += (b.end_at - b.start_at).total_seconds() / 3600
    assert placed["MAT1000-INTRA"] > 0 and placed["MAT1600-INTRA"] > 0


def test_overload_reduces_uniformly_with_rho():
    # 5 gros examens dans 6 jours : la demande dépasse la capacité
    courses = [make_course(id=i, code=f"C{i:03d}") for i in range(1, 6)]
    evals = [
        make_eval(id=i, course_id=i, external_id=f"C{i:03d}-INTRA", weight=50.0,
                  scope_units=10, due_at=datetime(2026, 9, 7 + i, 8, 0))
        for i in range(1, 6)
    ]
    result = plan(courses, evals, [], S, TODAY)
    assert result.rho < 1.0
    assert_invariants(result)


def test_deadline_in_two_days():
    result = plan([make_course()], [make_eval(due_at=datetime(2026, 9, 3, 8, 0))], [], S, TODAY)
    assert_invariants(result)
    assert result.blocks, "même à 2 jours, on place ce qu'on peut"
    assert all(b.start_at.date() < date(2026, 9, 3) for b in result.blocks)
    # la fenêtre est trop courte pour tout : un déficit est signalé
    assert result.deficits["MAT1000-INTRA"] > 0


def test_evaluation_too_late_is_excluded():
    result = plan([make_course()], [make_eval(due_at=datetime(2026, 8, 20, 8, 0))], [], S, TODAY)
    assert result.blocks == []
    assert "MAT1000-INTRA" in result.exclusions


def test_evaluation_without_date_is_excluded():
    result = plan([make_course()], [make_eval(due_at=None)], [], S, TODAY)
    assert result.blocks == []
    assert "MAT1000-INTRA" in result.exclusions


def test_zero_weight_bonus_is_excluded():
    result = plan([make_course()], [make_eval(weight=0.0)], [], S, TODAY)
    assert result.blocks == []
    assert "MAT1000-INTRA" in result.exclusions


def test_fully_blocked_days_shift_work():
    # tout est bloqué sauf le week-end
    constraints = [full_day_constraint(w) for w in range(5)]
    result = plan([make_course()], [make_eval()], constraints, S, TODAY)
    assert_invariants(result)
    assert result.blocks
    assert all(b.start_at.date().weekday() >= 5 for b in result.blocks)


def test_metrics_present_and_consistent():
    result = plan([make_course()], [make_eval()], [], S, TODAY)
    m = result.metrics
    assert 0.0 <= m.coverage <= 1.0
    assert m.peak_hours <= S.h_jour_max_weekend + 1e-9
    assert m.total_planned_hours > 0
