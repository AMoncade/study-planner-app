"""Étapes B et C — fenêtre de révision et courbe de répartition temporelle (ARCHITECTURE §4).

g(t) mélange décroissance exponentielle (fraîcheur) et plancher uniforme λ (révision
espacée). t = 1 est la veille de l'échéance ; le jour J n'appartient pas à la fenêtre.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from planner.config import EngineSettings
from planner.core.models import Evaluation


def revision_window(
    ev: Evaluation, today: date, s: EngineSettings
) -> tuple[date, date] | None:
    """[premier jour, dernier jour] d'étude possible, ou None si trop tard / sans date."""
    if ev.due_at is None:
        return None
    due_day = ev.due_at.date()
    depth = s.d_type.get(ev.type, s.d_type["autre"])
    start = due_day - timedelta(days=depth)
    if ev.type in ("travail", "projet") and ev.start_date and ev.start_date > start:
        start = ev.start_date
    start = max(start, today)
    end = due_day - timedelta(days=1)  # la veille ; le jour J est exclu (marge ε en aval)
    if start > end:
        return None
    return (start, end)


def distribution(depth: int, s: EngineSettings) -> dict[int, float]:
    """p(t) pour t = 1..depth (t = 1 : veille). Somme exactement 1."""
    tau = depth / s.tau_ratio
    g = {
        t: (1 - s.lam) * math.exp(-(t - 1) / tau) + s.lam / depth
        for t in range(1, depth + 1)
    }
    total = sum(g.values())
    return {t: v / total for t, v in g.items()}


def day_targets(
    h_total: float,
    window_days: list[date],
    due_day: date,
    capacities: dict[date, float],
    s: EngineSettings,
) -> dict[date, float]:
    """Heures visées par jour de la fenêtre (corrigées, plafonnées, arrondies à 0,5 h).

    Les jours sans capacité voient leur masse redistribuée proportionnellement (correctif 1),
    le plafond par évaluation et par jour est appliqué (correctif 2), puis l'excédent créé
    par le plafond est reversé sur les jours encore ouverts, du plus proche au plus lointain.
    """
    depth = max((due_day - d).days for d in window_days) if window_days else 0
    if depth == 0:
        return {}
    p = distribution(depth, s)

    # masse brute limitée aux jours de la fenêtre ayant de la capacité
    open_days = [d for d in window_days if capacities.get(d, 0.0) > 0.0]
    if not open_days:
        return {}
    weight_sum = sum(p[(due_day - d).days] for d in open_days)
    raw = {d: h_total * p[(due_day - d).days] / weight_sum for d in open_days}

    # plafond par jour, excédent reversé (jours proches d'abord : la fraîcheur paie)
    targets: dict[date, float] = {}
    excess = 0.0
    for d in sorted(open_days, key=lambda x: (due_day - x).days):
        cap = min(s.h_jour_eval, capacities[d])
        take = min(raw[d], cap)
        targets[d] = take
        excess += raw[d] - take
    for d in sorted(open_days, key=lambda x: (due_day - x).days):
        if excess <= 0:
            break
        cap = min(s.h_jour_eval, capacities[d])
        room = cap - targets[d]
        if room > 0:
            add = min(room, excess)
            targets[d] += add
            excess -= add

    # granularité 0,5 h
    return {d: round(v * 2) / 2 for d, v in targets.items() if round(v * 2) / 2 > 0}
