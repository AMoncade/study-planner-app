"""Tests de l'import .ics du centre étudiant : parsing, récurrences, réconciliation,
détection des examens (Phase 12)."""

from datetime import date, datetime, time
from pathlib import Path

import pytest

from planner.core.ics_import import format_ics_report, import_ics_file
from planner.core.importer import import_course_file
from planner.storage import repositories as repos
from planner.storage.db import connect

FIXTURES = Path(__file__).parent / "fixtures"
ICS = FIXTURES / "horaire_a26.ics"
TODAY = date(2026, 9, 1)


@pytest.fixture()
def conn():
    c = connect(":memory:")
    for name in ("mat1000_a26", "mat1400_a26", "mat1600_a26", "mat1720_a26"):
        import_course_file(c, FIXTURES / f"{name}.json", today=TODAY)
    yield c
    c.close()


def course_by_code(conn, code):
    return next(c for c in repos.list_courses(conn) if c.code == code)


# ------------------------------------------------------------ création de séances


def test_sessions_created_for_course_without_sessions(conn):
    report = import_ics_file(conn, ICS, today=TODAY)

    # MAT1600 n'avait aucune séance : les deux événements récurrents en créent deux.
    assert report.courses["MAT1600"].created == 2
    sessions = course_by_code(conn, "MAT1600").sessions
    assert len(sessions) == 2
    theory = next(s for s in sessions if s.weekday == 2)  # mercredi
    assert theory.start == time(13, 30)
    assert theory.end == time(15, 30)
    assert theory.kind == "cours"
    assert theory.start_date == date(2026, 9, 2)
    assert theory.end_date == date(2026, 12, 2)
    assert theory.except_dates == [date(2026, 10, 21)]  # relâche
    assert theory.room == "Pav. André-Aisenstadt, salle 6214"
    tp = next(s for s in sessions if s.weekday == 4)  # vendredi
    assert tp.kind == "tp"
    assert tp.start == time(9, 30)


def test_recurrence_bounds_and_exdates(conn):
    import_ics_file(conn, ICS, today=TODAY)

    # MAT1720 : lundi 10:30-12:30, du 31 août au 7 décembre, sans l'Action de
    # grâce (12 oct.) ni la semaine de relâche (19 oct.).
    sessions = course_by_code(conn, "MAT1720").sessions
    assert len(sessions) == 1
    s = sessions[0]
    assert s.weekday == 0
    assert (s.start, s.end) == (time(10, 30), time(12, 30))
    assert s.start_date == date(2026, 8, 31)
    assert s.end_date == date(2026, 12, 7)
    assert s.except_dates == [date(2026, 10, 12), date(2026, 10, 19)]


# ------------------------------------------------------------ réconciliation


def test_existing_sessions_updated_not_duplicated(conn):
    report = import_ics_file(conn, ICS, today=TODAY)

    # MAT1400 avait déjà ses 3 séances (JSON) : mêmes créneaux -> mises à jour.
    assert report.courses["MAT1400"].created == 0
    assert report.courses["MAT1400"].updated == 3
    sessions = course_by_code(conn, "MAT1400").sessions
    assert len(sessions) == 3
    tuesday = next(s for s in sessions if s.weekday == 1)
    assert tuesday.start_date == date(2026, 9, 1)
    assert tuesday.end_date == date(2026, 12, 1)
    assert tuesday.except_dates == [date(2026, 10, 20)]
    assert tuesday.room == "Pav. André-Aisenstadt, salle 1140"
    # Le kind réglé côté JSON est conservé à la mise à jour.
    monday = next(s for s in sessions if s.weekday == 0)
    assert monday.kind == "tp"


def test_sessions_absent_from_ics_are_kept(conn):
    import_ics_file(conn, ICS, today=TODAY)

    # MAT1000 : le .ics ne couvre que le jeudi ; vendredi et le TP restent en base.
    sessions = course_by_code(conn, "MAT1000").sessions
    assert len(sessions) == 3
    thursday = next(s for s in sessions if s.weekday == 3)
    assert thursday.start_date == date(2026, 9, 3)  # dates remplies par le .ics
    friday = next(s for s in sessions if s.weekday == 4)
    assert friday.start_date is None  # intouchée


def test_reimport_is_idempotent(conn):
    import_ics_file(conn, ICS, today=TODAY)
    counts_before = {
        c.code: len(c.sessions) for c in repos.list_courses(conn)
    }
    report = import_ics_file(conn, ICS, today=TODAY)

    for code, cr in report.courses.items():
        assert cr.created == 0, code
        assert cr.updated == 0, code
    assert {c.code: len(c.sessions) for c in repos.list_courses(conn)} == counts_before


# ------------------------------------------------------------ examens


def exam_by_course(report, code):
    return next(m for m in report.exams if m.course_code == code)


def test_exam_confirmed(conn):
    report = import_ics_file(conn, ICS, today=TODAY)

    match = exam_by_course(report, "MAT1400")
    assert match.status == "confirmed"
    assert match.external_id == "MAT1400-INTRA"
    assert match.ics_date == date(2026, 10, 26)
    # Aucune séance créée pour l'examen : MAT1400 garde ses 3 séances.
    assert len(course_by_code(conn, "MAT1400").sessions) == 3


def test_exam_conflict_reported_without_apply(conn):
    report = import_ics_file(conn, ICS, today=TODAY)

    match = exam_by_course(report, "MAT1600")
    assert match.status == "conflict"
    assert match.external_id == "MAT1600-INTRA"
    assert match.ics_date == date(2026, 10, 17)
    assert match.db_date == date(2026, 10, 16)
    assert match.applied is False
    ev = next(e for e in repos.list_evaluations(conn, course_id=course_by_code(
        conn, "MAT1600").id) if e.external_id == "MAT1600-INTRA")
    assert ev.due_at.date() == date(2026, 10, 16)  # base inchangée sans le flag


def test_exam_conflict_applied_with_flag(conn):
    report = import_ics_file(conn, ICS, today=TODAY, apply_exam_dates=True)

    match = exam_by_course(report, "MAT1600")
    assert match.status == "conflict"
    assert match.applied is True
    ev = next(e for e in repos.list_evaluations(conn, course_id=course_by_code(
        conn, "MAT1600").id) if e.external_id == "MAT1600-INTRA")
    assert ev.due_at == datetime(2026, 10, 17, 9, 0)
    # Un ré-import confirme désormais la date.
    report2 = import_ics_file(conn, ICS, today=TODAY)
    assert exam_by_course(report2, "MAT1600").status == "confirmed"


def test_exam_without_known_evaluation(conn):
    report = import_ics_file(conn, ICS, today=TODAY)

    match = exam_by_course(report, "MAT1720")
    assert match.status == "unknown"
    assert match.ics_date == date(2026, 10, 7)
    # Pas de séance créée pour ce quiz.
    assert len(course_by_code(conn, "MAT1720").sessions) == 1


# ------------------------------------------------------------ événements ignorés


def test_unknown_course_and_non_course_events_ignored(conn):
    report = import_ics_file(conn, ICS, today=TODAY)

    assert any("IFT1015" in entry for entry in report.ignored)
    assert any("Rendez-vous" in entry for entry in report.ignored)
    assert "IFT1015" not in report.courses
    assert all(c.code != "IFT1015" for c in repos.list_courses(conn))


# ------------------------------------------------------------ rapport texte


def test_format_report_mentions_key_facts(conn):
    report = import_ics_file(conn, ICS, today=TODAY)
    text = format_ics_report(report)

    assert "MAT1600" in text
    assert "confirmé" in text
    assert "conflit" in text.lower()
    assert "IFT1015" in text
