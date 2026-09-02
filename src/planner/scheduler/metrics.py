"""Étape G — métriques de qualité d'une génération (ARCHITECTURE §4).

Ces métriques sont le harnais de test du moteur : un changement de coefficient se juge
sur elles, pas à l'œil.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from planner.config import EngineSettings
from planner.core.models import StudyBlock


@dataclass
class PlanMetrics:
    coverage: float                 # heures placées / heures visées (1.0 = tout couvert)
    total_planned_hours: float
    total_target_hours: float
    daily_stddev: float             # équilibre journalier (heures/jour)
    kl_divergence: float            # fidélité à la courbe p(t) visée (0 = parfaite)
    peak_hours: float               # charge de pointe (max heures/jour)


def compute_metrics(
    blocks: list[StudyBlock],
    targets: dict[str, float],
    placed: dict[str, float],
    target_curves: dict[str, dict[date, float]],
    s: EngineSettings,
) -> PlanMetrics:
    total_target = sum(targets.values())
    total_planned = sum(placed.values())
    coverage = 1.0 if total_target == 0 else min(1.0, total_planned / total_target)

    per_day: dict[date, float] = {}
    for b in blocks:
        day = b.start_at.date()
        per_day[day] = per_day.get(day, 0.0) + b.planned_minutes / 60

    if per_day:
        values = list(per_day.values())
        mean = sum(values) / len(values)
        daily_stddev = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
        peak = max(values)
    else:
        daily_stddev = 0.0
        peak = 0.0

    # Divergence KL moyenne entre la courbe visée et la répartition réalisée par jour
    # (calculée sur l'agrégat de toutes les évaluations : simple et suffisant en pratique).
    aggregate_target: dict[date, float] = {}
    for curve in target_curves.values():
        for day, hours in curve.items():
            aggregate_target[day] = aggregate_target.get(day, 0.0) + hours
    kl = 0.0
    t_sum = sum(aggregate_target.values())
    q_sum = sum(per_day.values())
    if t_sum > 0 and q_sum > 0:
        for day, hours in aggregate_target.items():
            p = hours / t_sum
            q = per_day.get(day, 0.0) / q_sum
            if p > 0:
                kl += p * math.log(p / max(q, 1e-9))

    return PlanMetrics(
        coverage=coverage,
        total_planned_hours=total_planned,
        total_target_hours=total_target,
        daily_stddev=daily_stddev,
        kl_divergence=kl,
        peak_hours=peak,
    )
