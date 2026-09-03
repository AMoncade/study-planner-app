"""Import de l'horaire .ics du centre étudiant UdeM (ARCHITECTURE §2.7, Phase 12).

Chaque VEVENT est rattaché à un cours existant par son sigle (MAT1400, IFT-1015…)
détecté dans SUMMARY/DESCRIPTION. Les récurrences (RRULE + EXDATE) deviennent des
séances hebdomadaires ; les événements d'examen (intra/final/quiz) ne créent pas de
séance mais sont confrontés aux évaluations en base. Les heures avec fuseau
(America/Toronto) sont converties en heure locale naïve, comme partout ailleurs.

Réconciliation par (weekday, start, end) : ré-importer le même fichier ne duplique
rien ; les séances absentes du .ics (p. ex. issues du plan de cours JSON) sont
conservées, jamais supprimées.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from itertools import islice
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr
from icalendar import Calendar

from planner.core.errors import ImportBlockedError
from planner.core.models import Course, Evaluation, Session
from planner.storage import repositories as repos

LOCAL_TZ = ZoneInfo("America/Toronto")

# Sigle UdeM : 2 à 4 lettres puis 4 chiffres, séparés ou non (MAT1400, IFT-1015, MAT 1400).
COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,4})[ -]?(\d{4})\b")

# Mots-clés d'examen -> types d'évaluation compatibles. L'ordre compte :
# « examen intra » doit tomber sur intra avant le générique « examen ».
EXAM_KEYWORDS = (
    ("intra", ("examen_intra",)),
    ("final", ("examen_final",)),
    ("quiz", ("quiz",)),
    ("examen", ("examen_intra", "examen_final")),
)

# Mots-clés de type de séance (défaut : cours magistral).
SESSION_KIND_KEYWORDS = (
    ("laboratoire", "laboratoire"),
    ("labo", "laboratoire"),
    ("atelier", "atelier"),
    ("demonstration", "demonstration"),
    ("travaux pratiques", "tp"),
    ("tp", "tp"),
)

# Garde-fou contre une RRULE sans fin : ~2 ans d'occurrences hebdomadaires.
MAX_OCCURRENCES = 120


@dataclass
class ExamMatch:
    """Confrontation d'un événement d'examen du .ics avec une évaluation en base."""

    course_code: str
    summary: str
    ics_date: date
    ics_time: time | None
    status: str = "unknown"  # "confirmed" | "conflict" | "unknown"
    external_id: str | None = None
    db_date: date | None = None
    applied: bool = False


@dataclass
class CourseSessionsReport:
    course_code: str
    created: int = 0
    updated: int = 0
    unchanged: int = 0


@dataclass
class IcsImportReport:
    courses: dict[str, CourseSessionsReport] = field(default_factory=dict)
    exams: list[ExamMatch] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ utilitaires


def _normalize(text: str) -> str:
    """Minuscules sans accents, pour comparer les mots-clés."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _to_local_naive(value: datetime | date) -> datetime:
    """Ramène un instant .ics en heure locale naïve (convention de toute l'app)."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(LOCAL_TZ).replace(tzinfo=None)
        return value
    return datetime.combine(value, time(0, 0))


def _event_text(event, key: str) -> str:
    value = event.get(key)
    return "" if value is None else str(value)


def _find_course_code(summary: str, description: str) -> str | None:
    match = COURSE_CODE_RE.search(summary) or COURSE_CODE_RE.search(description)
    return None if match is None else match.group(1) + match.group(2)


def _detect_exam_types(summary: str) -> tuple[str, ...] | None:
    words = _normalize(summary)
    for keyword, types in EXAM_KEYWORDS:
        if re.search(rf"\b{keyword}\b", words):
            return types
    return None


def _detect_kind(summary: str, description: str) -> str:
    words = _normalize(f"{summary} {description}")
    for keyword, kind in SESSION_KIND_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", words):
            return kind
    return "cours"


def _exdates(event) -> list[date]:
    raw = event.get("EXDATE")
    if raw is None:
        return []
    lists = raw if isinstance(raw, list) else [raw]
    return sorted({_to_local_naive(entry.dt).date() for lst in lists for entry in lst.dts})


def _occurrences(event, dtstart) -> list[datetime]:
    """Développe la RRULE avec dateutil ; l'événement simple donne une occurrence."""
    rrule_prop = event.get("RRULE")
    if rrule_prop is None:
        return [_to_local_naive(dtstart)]
    rule = rrulestr(rrule_prop.to_ical().decode("ascii"), dtstart=dtstart)
    return [_to_local_naive(occ) for occ in islice(rule, MAX_OCCURRENCES)]


def _event_sessions(event, dtstart, summary: str, description: str) -> list[Session]:
    """Transforme un VEVENT (récurrent ou non) en séances hebdomadaires."""
    start_local = _to_local_naive(dtstart)
    dtend = event.get("DTEND")
    if dtend is not None:
        end_local = _to_local_naive(dtend.dt)
    else:
        duration = event.get("DURATION")
        delta = duration.dt if duration is not None else timedelta(hours=1)
        end_local = start_local + delta
    occurrences = _occurrences(event, dtstart)
    exdates = _exdates(event)
    kind = _detect_kind(summary, description)
    room = _event_text(event, "LOCATION") or None

    sessions = []
    by_weekday: dict[int, list[datetime]] = {}
    for occ in occurrences:
        by_weekday.setdefault(occ.weekday(), []).append(occ)
    for weekday, occs in sorted(by_weekday.items()):
        sessions.append(Session(
            id=None,
            kind=kind,
            weekday=weekday,
            start=start_local.time(),
            end=end_local.time(),
            room=room,
            start_date=min(occs).date(),
            end_date=max(occs).date(),
            except_dates=[d for d in exdates if d.weekday() == weekday],
        ))
    return sessions


# ------------------------------------------------------------------ réconciliation


def _reconcile_sessions(
    conn, course: Course, new_sessions: list[Session], report: CourseSessionsReport
) -> None:
    """Upsert par (weekday, start, end) ; ne supprime jamais une séance existante."""
    existing = {(s.weekday, s.start, s.end): s for s in course.sessions}
    for new in new_sessions:
        key = (new.weekday, new.start, new.end)
        current = existing.get(key)
        if current is None:
            new.id = repos.insert_session(conn, course.id, new)
            existing[key] = new
            report.created += 1
            continue
        same = (
            (current.room or None) == new.room
            and current.start_date == new.start_date
            and current.end_date == new.end_date
            and current.except_dates == new.except_dates
        )
        if same:
            report.unchanged += 1
        else:
            repos.update_session_schedule(conn, current.id, new)
            existing[key] = Session(
                id=current.id, kind=current.kind, weekday=new.weekday, start=new.start,
                end=new.end, room=new.room, start_date=new.start_date,
                end_date=new.end_date, except_dates=new.except_dates,
            )
            report.updated += 1


def _match_exam(
    conn,
    course: Course,
    summary: str,
    when: datetime,
    types: tuple[str, ...],
    apply_exam_dates: bool,
    report: IcsImportReport,
) -> ExamMatch:
    """Confronte un événement d'examen aux évaluations du cours (jamais de séance)."""
    candidates: list[Evaluation] = [
        e for e in repos.list_evaluations(conn, course_id=course.id) if e.type in types
    ]
    ics_date = when.date()
    match = ExamMatch(
        course_code=course.code, summary=summary, ics_date=ics_date, ics_time=when.time()
    )
    exact = [c for c in candidates if c.due_at is not None and c.due_at.date() == ics_date]
    if exact:
        match.status = "confirmed"
        match.external_id = exact[0].external_id
        match.db_date = ics_date
        return match
    if not candidates:
        match.status = "unknown"
        return match
    # Conflit : on vise la candidate la plus proche en date (celles sans date en dernier).
    far = timedelta(days=10_000)
    best = min(
        candidates,
        key=lambda e: abs(e.due_at - when) if e.due_at is not None else far,
    )
    match.status = "conflict"
    match.external_id = best.external_id
    match.db_date = best.due_at.date() if best.due_at is not None else None
    if apply_exam_dates:
        repos.update_evaluation_due_at(conn, best.id, when)
        dropped = repos.delete_planned_blocks(conn, best.id)
        if dropped:
            report.warnings.append(
                f"{best.external_id} : {dropped} bloc(s) planifié(s) invalidé(s) "
                "(échéance déplacée par le .ics), à replanifier."
            )
        match.applied = True
    return match


# ------------------------------------------------------------------ import


def import_ics_text(
    conn, text: str | bytes, today: date, apply_exam_dates: bool = False
) -> IcsImportReport:
    """Importe le contenu d'un .ics déjà lu. Lève ImportBlockedError si illisible.

    `today` est reçu par convention de déterminisme (aucun datetime.now() caché) ;
    l'import lui-même ne dépend que du contenu du fichier.
    """
    del today  # réservé : l'import est indépendant de l'instant courant.
    try:
        calendar = Calendar.from_ical(text)
    except Exception as exc:  # icalendar lève ValueError et divers sous-types
        raise ImportBlockedError([f"Fichier .ics illisible : {exc}"]) from exc

    courses = repos.list_courses(conn)
    by_code = {c.code.replace("-", "").replace(" ", "").upper(): c for c in courses}
    report = IcsImportReport()

    with conn:  # transaction unique : tout ou rien
        for event in calendar.walk("VEVENT"):
            summary = _event_text(event, "SUMMARY")
            description = _event_text(event, "DESCRIPTION")
            label = summary or _event_text(event, "UID") or "(sans titre)"
            dtstart_prop = event.get("DTSTART")
            if dtstart_prop is None:
                report.ignored.append(f"{label} (sans date de début)")
                continue
            code = _find_course_code(summary, description)
            if code is None:
                report.ignored.append(f"{label} (aucun sigle de cours)")
                continue
            course = by_code.get(code)
            if course is None:
                report.ignored.append(f"{label} (sigle inconnu : {code})")
                continue

            exam_types = _detect_exam_types(summary)
            if exam_types is not None:
                when = _to_local_naive(dtstart_prop.dt)
                report.exams.append(_match_exam(
                    conn, course, summary, when, exam_types, apply_exam_dates, report
                ))
                continue

            course_report = report.courses.setdefault(
                course.code, CourseSessionsReport(course_code=course.code)
            )
            try:
                sessions = _event_sessions(event, dtstart_prop.dt, summary, description)
            except (ValueError, TypeError) as exc:
                report.warnings.append(f"{label} : récurrence illisible ({exc}), ignoré.")
                continue
            _reconcile_sessions(conn, course, sessions, course_report)

    return report


def import_ics_file(
    conn, path: str | Path, today: date, apply_exam_dates: bool = False
) -> IcsImportReport:
    """Lit un fichier .ics et l'importe. Lève ImportBlockedError si refusé."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ImportBlockedError([f"Fichier illisible : {exc}"]) from exc
    return import_ics_text(conn, raw, today=today, apply_exam_dates=apply_exam_dates)


# ------------------------------------------------------------------ rapport texte

_EXAM_LABELS = {
    "confirmed": "match confirmé",
    "conflict": "CONFLIT",
    "unknown": "sans évaluation connue",
}


def format_ics_report(report: IcsImportReport) -> str:
    """Rapport lisible, partagé par la CLI et la vue Importer."""
    lines: list[str] = []
    if report.courses:
        lines.append("Séances par cours :")
        for code in sorted(report.courses):
            r = report.courses[code]
            lines.append(f"  {code} : {r.created} créée(s) · {r.updated} mise(s) à jour · "
                         f"{r.unchanged} inchangée(s)")
    else:
        lines.append("Aucune séance de cours reconnue dans le fichier.")
    if report.exams:
        lines.append("Examens détectés :")
        for m in report.exams:
            detail = _EXAM_LABELS[m.status]
            if m.status == "confirmed":
                detail += f" avec {m.external_id} ({m.ics_date})"
            elif m.status == "conflict":
                db = m.db_date.isoformat() if m.db_date else "aucune date en base"
                detail += f" avec {m.external_id} : .ics {m.ics_date} ≠ base {db}"
                detail += " — mise à jour appliquée" if m.applied else \
                    " — relancer avec --apply-exam-dates pour appliquer"
            else:
                detail += f" ({m.ics_date})"
            lines.append(f"  {m.summary} : {detail}")
    if report.ignored:
        lines.append("Événements ignorés :")
        lines.extend(f"  {entry}" for entry in report.ignored)
    lines.extend(f"  ⚠ {w}" for w in report.warnings)
    return "\n".join(lines)
