"""Étape F — recalcul incrémental (ARCHITECTURE §4).

Règles :
- les blocs passés sont figés (historique) ;
- les blocs `locked` sont figés et leur temps compte comme placé ;
- les blocs `done`/`partial` réduisent la charge restante (minutes réelles × efficacité) ;
- un bloc `skipped` NE réDUIT PAS la charge : le travail est repoussé, pas fait ;
- les blocs futurs `planned` non verrouillés sont libérés puis replacés,
  P_stabilité les ramenant vers leurs positions actuelles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from planner.config import EngineSettings
from planner.core.models import Constraint, Course, Evaluation, StudyBlock
from planner.scheduler.placer import PlanResult, plan


@dataclass
class RebalanceDiff:
    kept: int      # blocs replacés exactement au même endroit
    moved: int     # blocs replacés ailleurs (même évaluation)
    added: int     # blocs en plus par rapport à l'existant libéré
    removed: int   # blocs en moins
    freed_ids: list[int]           # ids BD des blocs planned libérés (à supprimer si appliqué)
    new_blocks: list[StudyBlock]   # blocs générés (à insérer si appliqué)


def hours_done_by_evaluation(
    blocks: list[StudyBlock], default_efficiency: float = 1.0
) -> dict[int, float]:
    """H_fait(e) = Σ minutes réelles × η sur les blocs done/partial."""
    done: dict[int, float] = {}
    for b in blocks:
        if b.status not in ("done", "partial"):
            continue
        minutes = b.actual_minutes if b.actual_minutes is not None else b.planned_minutes
        eta = b.efficiency if b.efficiency is not None else default_efficiency
        done[b.evaluation_id] = done.get(b.evaluation_id, 0.0) + minutes / 60 * eta
    return done


def rebalance(
    courses: list[Course],
    evaluations: list[Evaluation],
    constraints: list[Constraint],
    existing_blocks: list[StudyBlock],
    settings: EngineSettings,
    now: datetime,
) -> tuple[PlanResult, RebalanceDiff]:
    """Recalcule le plan sur [now, ...] sans toucher à l'historique ni aux blocs verrouillés."""
    freed = [
        b for b in existing_blocks
        if b.status == "planned" and not b.locked and b.start_at >= now
    ]
    fixed_future = [
        b for b in existing_blocks
        if b.start_at >= now and b not in freed and b.status != "skipped"
    ]
    hours_done = hours_done_by_evaluation(existing_blocks)

    result = plan(
        courses, evaluations, constraints, settings, now.date(),
        previous_blocks=freed, fixed_blocks=fixed_future, hours_done=hours_done,
    )

    old_positions = {(b.evaluation_id, b.start_at) for b in freed}
    new_positions = {(b.evaluation_id, b.start_at) for b in result.blocks}
    kept = len(old_positions & new_positions)
    diff = RebalanceDiff(
        kept=kept,
        moved=min(len(freed), len(result.blocks)) - kept,
        added=max(0, len(result.blocks) - len(freed)),
        removed=max(0, len(freed) - len(result.blocks)),
        freed_ids=[b.id for b in freed if b.id is not None],
        new_blocks=result.blocks,
    )
    return result, diff


def apply_rebalance(conn, diff: RebalanceDiff) -> None:
    """Applique le différentiel : supprime les blocs libérés, insère les nouveaux."""
    from planner.storage import repositories as repos

    with conn:
        for block_id in diff.freed_ids:
            repos.delete_study_block(conn, block_id)
        for b in diff.new_blocks:
            repos.insert_study_block(conn, b.evaluation_id, b.start_at, b.end_at)
