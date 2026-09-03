"""Répartition hebdomadaire « régulier dès maintenant » (décision utilisateur, 2026-09-02).

Scénario type semestre réel : aujourd'hui = début septembre, quiz hebdomadaires,
intras à la mi-octobre, finaux à la mi-décembre. Le plan doit donner de l'étude
constante chaque semaine dès le début, avec une montée DOUCE avant les examens :
- chaque semaine entre aujourd'hui et le dernier examen reçoit > 0 h ;
- la première semaine reçoit >= 3 h (l'app ne doit jamais paraître « vide ») ;
- ratio (semaine max / semaine médiane non nulle) <= 3 (pas de mur de décembre) ;
- aucune semaine ne dépasse la capacité hebdomadaire théorique.
"""

from datetime import date, datetime, timedelta

from planner.config import EngineSettings
from planner.core.models import Course, Evaluation
from planner.scheduler.placer import plan

S = EngineSettings()
TODAY = date(2026, 9, 1)  # mardi, début du trimestre d'automne
LAST_EXAM = date(2026, 12, 17)


def make_courses() -> list[Course]:
    return [
        Course(id=i, code=f"MAT1{i}00", title=f"Cours {i}", term="A26", difficulty=3)
        for i in range(1, 5)
    ]


def make_semester_evaluations() -> list[Evaluation]:
    """4 cours : quiz hebdos (sept -> nov), intras mi-octobre, finaux mi-décembre."""
    evals: list[Evaluation] = []
    next_id = 1
    for course_id in range(1, 5):
        code = f"MAT1{course_id}00"
        # intra la semaine du 13 octobre, final la semaine du 14 décembre
        evals.append(Evaluation(
            id=next_id, course_id=course_id, external_id=f"{code}-INTRA",
            title="Intra", type="examen_intra", weight=30.0,
            due_at=datetime(2026, 10, 12 + course_id, 8, 0), scope_units=5,
        ))
        next_id += 1
        evals.append(Evaluation(
            id=next_id, course_id=course_id, external_id=f"{code}-FINAL",
            title="Final", type="examen_final", weight=40.0,
            due_at=datetime(2026, 12, 13 + course_id, 8, 0), scope_units=10,
            cumulative=True,
        ))
        next_id += 1
    # quiz hebdomadaires (3 cours) : chaque mardi du 8 septembre au 24 novembre
    for course_id in (1, 2, 3):
        code = f"MAT1{course_id}00"
        for week in range(12):
            due = datetime(2026, 9, 8, 8, 0) + timedelta(weeks=week)
            evals.append(Evaluation(
                id=next_id, course_id=course_id,
                external_id=f"{code}-QUIZ{week + 1}", title=f"Quiz {week + 1}",
                type="quiz", weight=5.0, due_at=due,
            ))
            next_id += 1
    return evals


def hours_by_week(blocks) -> dict[int, float]:
    """Heures placées par semaine (semaine 0 = les 7 jours à partir d'aujourd'hui)."""
    weeks: dict[int, float] = {}
    for b in blocks:
        index = (b.start_at.date() - TODAY).days // 7
        weeks[index] = weeks.get(index, 0.0) + (b.end_at - b.start_at).total_seconds() / 3600
    return weeks


def weekly_capacity(week_index: int) -> float:
    """Capacité théorique de la semaine : somme des plafonds journaliers."""
    return sum(
        S.h_jour_max((TODAY + timedelta(days=week_index * 7 + i)).weekday())
        for i in range(7)
    )


def test_every_week_gets_study_time():
    result = plan(make_courses(), make_semester_evaluations(), [], S, TODAY)
    weeks = hours_by_week(result.blocks)
    last_week = (LAST_EXAM - TODAY).days // 7
    for w in range(last_week + 1):
        assert weeks.get(w, 0.0) > 0.0, f"semaine {w} vide (début {TODAY + timedelta(days=7 * w)})"


def test_first_week_gets_at_least_three_hours():
    result = plan(make_courses(), make_semester_evaluations(), [], S, TODAY)
    weeks = hours_by_week(result.blocks)
    assert weeks.get(0, 0.0) >= 3.0, f"première semaine : {weeks.get(0, 0.0)} h < 3 h"


def test_peak_week_over_median_week_ratio_bounded():
    result = plan(make_courses(), make_semester_evaluations(), [], S, TODAY)
    weeks = hours_by_week(result.blocks)
    values = sorted(v for v in weeks.values() if v > 0)
    assert values, "aucune heure placée"
    median = values[len(values) // 2]
    ratio = max(values) / median
    assert ratio <= 3.0, f"ratio pic/médiane {ratio:.2f} > 3 (semaines : {weeks})"


def test_no_week_exceeds_weekly_capacity():
    result = plan(make_courses(), make_semester_evaluations(), [], S, TODAY)
    for w, hours in hours_by_week(result.blocks).items():
        assert hours <= weekly_capacity(w) + 1e-9, \
            f"semaine {w} : {hours} h > capacité {weekly_capacity(w)} h"


def test_first_week_covered_by_exams_alone():
    """Cas réel début de session : aucun quiz tôt, intras à 6 semaines, finaux à
    ~14 semaines. Les fenêtres d'examens couvrent tout l'horizon restant : la
    première semaine doit quand même recevoir >= 3 h, et aucune semaine ne doit
    être vide jusqu'au dernier examen."""
    evals = [e for e in make_semester_evaluations() if e.type != "quiz"]
    result = plan(make_courses(), evals, [], S, TODAY)
    weeks = hours_by_week(result.blocks)
    assert weeks.get(0, 0.0) >= 3.0, f"première semaine : {weeks.get(0, 0.0)} h < 3 h"
    last_week = (LAST_EXAM - TODAY).days // 7
    for w in range(last_week + 1):
        assert weeks.get(w, 0.0) > 0.0, f"semaine {w} vide (examens seuls)"


def test_day_before_exam_is_heaviest_of_its_window():
    """La veille d'un examen reste le jour le plus chargé de sa fenêtre pour cette éval."""
    course = Course(id=1, code="MAT1000", title="Analyse", term="A26")
    final = Evaluation(
        id=1, course_id=1, external_id="MAT1000-FINAL", title="Final",
        type="examen_final", weight=50.0, due_at=datetime(2026, 12, 15, 8, 0),
        scope_units=10, cumulative=True,
    )
    result = plan([course], [final], [], S, TODAY)
    per_day: dict[date, float] = {}
    for b in result.blocks:
        d = b.start_at.date()
        per_day[d] = per_day.get(d, 0.0) + (b.end_at - b.start_at).total_seconds() / 3600
    eve = date(2026, 12, 14)
    assert per_day, "aucun bloc placé"
    assert per_day.get(eve, 0.0) == max(per_day.values()), \
        f"la veille ({per_day.get(eve, 0.0)} h) n'est pas le jour le plus chargé"
