"""Modèles du domaine (ARCHITECTURE §3.1). Dataclasses pures, sans logique d'accès aux données."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

# Jours de la semaine : index 0 = lundi (aligné sur date.weekday()).
WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")

EVALUATION_TYPES = (
    "examen_final", "examen_intra", "quiz", "travail", "projet",
    "presentation", "laboratoire", "lecture", "participation", "autre",
)

# Types dont l'échéance par défaut est l'heure d'un examen (08:00) plutôt
# qu'une remise (23:59) — ARCHITECTURE §2.3, champ due_time.
EXAM_TYPES = ("examen_final", "examen_intra")

SESSION_KINDS = ("cours", "tp", "laboratoire", "atelier", "demonstration")

CONSTRAINT_CATEGORIES = (
    "travail", "entrainement", "transport", "sommeil", "personnel", "cours", "autre",
)

BLOCK_STATUSES = ("planned", "done", "partial", "skipped", "moved")

CONFIDENCES = ("high", "medium", "low")


@dataclass
class Session:
    """Séance récurrente d'un cours ; bloque des créneaux (§4.4)."""

    id: int | None
    kind: str
    weekday: int  # 0 = lundi … 6 = dimanche
    start: time
    end: time
    room: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    except_dates: list[date] = field(default_factory=list)


@dataclass
class Course:
    id: int | None
    code: str
    title: str
    term: str
    institution: str | None = None
    credits: int | None = None
    instructor: str | None = None
    language: str = "fr"
    difficulty: int = 3
    effort_multiplier: float = 1.0
    archived: bool = False
    sessions: list[Session] = field(default_factory=list)


@dataclass
class Evaluation:
    id: int | None
    course_id: int | None
    external_id: str
    title: str
    type: str
    weight: float
    due_at: datetime | None = None
    start_date: date | None = None
    duration_minutes: int | None = None
    modality: str | None = None
    location: str | None = None
    cumulative: bool | None = None
    group_work: bool | None = None
    content_scope: list[str] = field(default_factory=list)
    scope_units: int | None = None
    deliverable: str | None = None
    estimated_pages: int | None = None
    resources: list[str] = field(default_factory=list)
    notes: str | None = None
    confidence: str = "high"
    source_excerpt: str | None = None
    manual_hours_override: float | None = None
    status: str = "active"
    archived: bool = False


@dataclass
class Constraint:
    """Indisponibilité fixe : hebdomadaire (weekday) ou ponctuelle (specific_date)."""

    id: int | None
    label: str
    category: str
    weekday: int | None  # exclusif avec specific_date
    specific_date: date | None
    start: time
    end: time
    rrule: str | None = None
    priority: int = 0
    color: str | None = None


@dataclass
class StudyBlock:
    id: int | None
    evaluation_id: int
    start_at: datetime
    end_at: datetime
    planned_minutes: int
    status: str = "planned"
    locked: bool = False
    generation_id: int | None = None
    actual_minutes: int | None = None
    efficiency: float | None = None
    note: str | None = None
