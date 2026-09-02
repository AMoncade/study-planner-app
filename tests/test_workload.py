"""Tests de l'étape A : charge totale d'étude par évaluation (ARCHITECTURE §4)."""

from planner.config import EngineSettings
from planner.core.models import Course, Evaluation
from planner.scheduler.workload import total_hours

S = EngineSettings()


def make_eval(**kwargs) -> Evaluation:
    defaults = dict(
        id=1, course_id=1, external_id="X-E1", title="E", type="examen_intra", weight=20.0,
    )
    defaults.update(kwargs)
    return Evaluation(**defaults)


def make_course(**kwargs) -> Course:
    defaults = dict(id=1, code="X", title="X", term="A26")
    defaults.update(kwargs)
    return Course(**defaults)


def test_reference_evaluation_gets_base_hours():
    # poids 20, difficulté 3, 5 unités : tous les facteurs valent 1.
    ev = make_eval(weight=20.0, scope_units=5)
    assert total_hours(ev, make_course(), S) == S.b_type["examen_intra"]


def test_monotonic_in_weight():
    values = [
        total_hours(make_eval(weight=w), make_course(), S) for w in (10, 20, 30, 40, 60)
    ]
    assert values == sorted(values)
    assert values[0] < values[-1]


def test_weight_sublinear():
    h20 = total_hours(make_eval(weight=20.0), make_course(), S)
    h40 = total_hours(make_eval(weight=40.0), make_course(), S)
    assert h40 < 2 * h20  # un examen à 40 % ne coûte pas le double d'un 20 %


def test_monotonic_in_difficulty():
    values = [
        total_hours(make_eval(), make_course(difficulty=d), S) for d in (1, 2, 3, 4, 5)
    ]
    assert values == sorted(values)


def test_monotonic_in_scope_units():
    values = [
        total_hours(make_eval(scope_units=u), make_course(), S) for u in (1, 3, 5, 10)
    ]
    assert values == sorted(values)


def test_cumulative_increases_load():
    plain = total_hours(make_eval(scope_units=5), make_course(), S)
    cumul = total_hours(make_eval(scope_units=5, cumulative=True), make_course(), S)
    assert cumul > plain


def test_group_work_reduces_load():
    solo = total_hours(make_eval(), make_course(), S)
    group = total_hours(make_eval(group_work=True), make_course(), S)
    assert group < solo


def test_bounds_respected():
    tiny = total_hours(make_eval(type="participation", weight=1.0), make_course(), S)
    assert tiny >= S.h_min
    huge = total_hours(
        make_eval(type="projet", weight=90.0, scope_units=20, cumulative=True),
        make_course(difficulty=5, effort_multiplier=2.0),
        S,
    )
    assert huge <= S.h_max


def test_manual_override_wins():
    ev = make_eval(manual_hours_override=12.0, weight=90.0)
    assert total_hours(ev, make_course(difficulty=5), S) == 12.0


def test_result_is_half_hour_multiple():
    for w in (13, 27, 42, 55):
        h = total_hours(make_eval(weight=float(w)), make_course(), S)
        assert (h * 2) == int(h * 2)


def test_regression_real_fixture_mat1720():
    """Valeurs figées avec les coefficients par défaut (à re-figer après calibration §4.9)."""
    course = make_course(code="MAT1720")
    intra = make_eval(
        external_id="MAT1720-INTRA", type="examen_intra", weight=40.0,
        scope_units=4, cumulative=False,
    )
    final = make_eval(
        external_id="MAT1720-FINAL", type="examen_final", weight=60.0,
        scope_units=8, cumulative=True,
    )
    assert total_hours(intra, course, S) == 13.5
    assert total_hours(final, course, S) == 24.0  # borné par h_max
