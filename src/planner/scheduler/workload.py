"""Étape A — charge totale d'étude par évaluation (ARCHITECTURE §4).

H_total(e) = clamp( B(type) · f_w(w) · f_d(d) · f_u(u) · f_g · m_c , H_min , H_max )
Fonction pure : aucune I/O, aucun accès base.
"""

from __future__ import annotations

from planner.config import EngineSettings
from planner.core.models import Course, Evaluation


def _round_half(hours: float) -> float:
    return round(hours * 2) / 2


def total_hours(ev: Evaluation, course: Course, s: EngineSettings) -> float:
    """Heures d'étude visées pour une évaluation. manual_hours_override court-circuite tout."""
    if ev.manual_hours_override is not None:
        return ev.manual_hours_override

    base = s.b_type.get(ev.type, s.b_type["autre"])
    f_w = (ev.weight / s.w_ref) ** s.alpha if ev.weight > 0 else 0.0
    f_d = 1.0 + s.beta * (course.difficulty - 3)
    f_u = (ev.scope_units / s.u_ref) ** 0.5 if ev.scope_units else 1.0
    if ev.cumulative:
        f_u *= s.cumulative_factor
    f_g = s.group_factor if ev.group_work else 1.0

    hours = base * f_w * f_d * f_u * f_g * course.effort_multiplier
    return _round_half(min(max(hours, s.h_min), s.h_max))
