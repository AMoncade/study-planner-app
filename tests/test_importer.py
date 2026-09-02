"""Tests de l'importateur : validation, mapping et réconciliation (ARCHITECTURE §2)."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from planner.core.errors import ImportBlockedError
from planner.core.importer import import_course_data, import_course_file
from planner.storage import repositories as repos
from planner.storage.db import connect

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 1)


@pytest.fixture()
def conn():
    c = connect(":memory:")
    yield c
    c.close()


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- import valide


def test_import_fixture_mat1400(conn):
    report = import_course_file(conn, FIXTURES / "mat1400_a26.json", today=TODAY)
    assert report.course_code == "MAT1400"
    assert report.created == 17
    assert report.updated == 0
    assert report.archived == 0

    courses = repos.list_courses(conn)
    assert len(courses) == 1
    course = courses[0]
    assert course.code == "MAT1400"
    assert course.term == "A26"
    assert course.credits == 4
    assert course.difficulty == 3
    assert len(course.sessions) == 3

    evals = repos.list_evaluations(conn, course_id=course.id)
    assert len(evals) == 17
    intra = next(e for e in evals if e.external_id == "MAT1400-INTRA")
    assert intra.weight == 45.0
    assert intra.due_at == datetime(2026, 10, 26, 15, 30)
    assert intra.scope_units == 5
    assert intra.cumulative is False


def test_import_all_four_fixtures(conn):
    for name in ("mat1000_a26.json", "mat1400_a26.json", "mat1600_a26.json", "mat1720_a26.json"):
        import_course_file(conn, FIXTURES / name, today=TODAY)
    assert {c.code for c in repos.list_courses(conn)} == {
        "MAT1000", "MAT1400", "MAT1600", "MAT1720",
    }


def test_default_due_time_applied(conn):
    # MAT1600 : intra sans heure -> 08:00 (examen), quiz sans heure -> 23:59 (remise)
    import_course_file(conn, FIXTURES / "mat1600_a26.json", today=TODAY)
    course = repos.list_courses(conn)[0]
    evals = {e.external_id: e for e in repos.list_evaluations(conn, course_id=course.id)}
    assert evals["MAT1600-INTRA"].due_at == datetime(2026, 10, 16, 8, 0)
    assert evals["MAT1600-QUIZ1"].due_at == datetime(2026, 10, 1, 23, 59)
    # due_date null -> due_at None
    assert evals["MAT1600-QUIZTP"].due_at is None


def test_confidence_and_null_date_warnings(conn):
    report = import_course_file(conn, FIXTURES / "mat1600_a26.json", today=TODAY)
    joined = " ".join(report.warnings)
    assert "MAT1600-QUIZTP" in joined  # date manquante signalée


# ---------------------------------------------------------------- rejets


def test_reject_malformed_json(conn, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ pas du json", encoding="utf-8")
    with pytest.raises(ImportBlockedError):
        import_course_file(conn, bad, today=TODAY)


def test_reject_schema_invalid(conn):
    data = load_fixture("mat1720_a26.json")
    del data["course"]["code"]
    with pytest.raises(ImportBlockedError) as exc:
        import_course_data(conn, data, today=TODAY)
    assert any("code" in str(e) for e in exc.value.errors)


def test_reject_duplicate_ids(conn):
    data = load_fixture("mat1720_a26.json")
    data["evaluations"].append(dict(data["evaluations"][0]))
    with pytest.raises(ImportBlockedError) as exc:
        import_course_data(conn, data, today=TODAY)
    assert any("unique" in str(e).lower() for e in exc.value.errors)


def test_reject_unknown_schema_version(conn):
    data = load_fixture("mat1720_a26.json")
    data["schema_version"] = "9.9"
    with pytest.raises(ImportBlockedError):
        import_course_data(conn, data, today=TODAY)


def test_reject_impossible_date(conn):
    data = load_fixture("mat1720_a26.json")
    data["evaluations"][0]["due_date"] = "2026-02-30"
    with pytest.raises(ImportBlockedError):
        import_course_data(conn, data, today=TODAY)


def test_reject_start_after_due(conn):
    data = load_fixture("mat1720_a26.json")
    data["evaluations"][0]["start_date"] = "2026-11-01"  # après due_date 2026-10-28
    with pytest.raises(ImportBlockedError):
        import_course_data(conn, data, today=TODAY)


def test_weight_sum_warning(conn):
    data = load_fixture("mat1720_a26.json")
    data["evaluations"][0]["weight"] = 10.0  # somme = 70
    report = import_course_data(conn, data, today=TODAY)
    assert any("100" in w for w in report.warnings)


# ---------------------------------------------------------------- réconciliation


def test_reimport_unchanged_is_noop(conn):
    import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    report = import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    assert report.created == 0
    assert report.updated == 0
    assert report.unchanged == 2
    assert len(repos.list_courses(conn)) == 1


def test_reimport_updates_date_and_invalidates_planned_blocks(conn):
    import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    course = repos.list_courses(conn)[0]
    intra = next(
        e for e in repos.list_evaluations(conn, course_id=course.id)
        if e.external_id == "MAT1720-INTRA"
    )
    done_id = repos.insert_study_block(
        conn, intra.id, datetime(2026, 10, 1, 9, 0), datetime(2026, 10, 1, 11, 0), status="done"
    )
    planned_id = repos.insert_study_block(
        conn, intra.id, datetime(2026, 10, 20, 9, 0), datetime(2026, 10, 20, 11, 0),
        status="planned",
    )

    data = load_fixture("mat1720_a26.json")
    next(e for e in data["evaluations"] if e["id"] == "MAT1720-INTRA")["due_date"] = "2026-11-04"
    report = import_course_data(conn, data, today=TODAY)
    assert report.updated == 1
    assert report.unchanged == 1

    intra2 = next(
        e for e in repos.list_evaluations(conn, course_id=course.id)
        if e.external_id == "MAT1720-INTRA"
    )
    assert intra2.due_at.date() == date(2026, 11, 4)
    blocks = repos.list_study_blocks(conn, evaluation_id=intra2.id)
    ids = {b.id for b in blocks}
    assert done_id in ids
    assert planned_id not in ids


def test_reimport_archives_missing_evaluation(conn):
    import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    data = load_fixture("mat1720_a26.json")
    data["evaluations"] = [e for e in data["evaluations"] if e["id"] != "MAT1720-FINAL"]
    report = import_course_data(conn, data, today=TODAY)
    assert report.archived == 1

    course = repos.list_courses(conn)[0]
    all_evals = repos.list_evaluations(conn, course_id=course.id, include_archived=True)
    final = next(e for e in all_evals if e.external_id == "MAT1720-FINAL")
    assert final.archived is True
    active = repos.list_evaluations(conn, course_id=course.id)
    assert {e.external_id for e in active} == {"MAT1720-INTRA"}


def test_reimport_preserves_manual_fields(conn):
    import_course_file(conn, FIXTURES / "mat1720_a26.json", today=TODAY)
    course = repos.list_courses(conn)[0]
    repos.update_course_manual_fields(conn, course.id, difficulty=5, effort_multiplier=1.5)
    intra = next(
        e for e in repos.list_evaluations(conn, course_id=course.id)
        if e.external_id == "MAT1720-INTRA"
    )
    repos.set_manual_hours_override(conn, intra.id, 12.0)

    data = load_fixture("mat1720_a26.json")
    next(e for e in data["evaluations"] if e["id"] == "MAT1720-INTRA")["weight"] = 45.0
    import_course_data(conn, data, today=TODAY)

    course2 = repos.list_courses(conn)[0]
    assert course2.difficulty == 5
    assert course2.effort_multiplier == 1.5
    intra2 = next(
        e for e in repos.list_evaluations(conn, course_id=course2.id)
        if e.external_id == "MAT1720-INTRA"
    )
    assert intra2.weight == 45.0
    assert intra2.manual_hours_override == 12.0
