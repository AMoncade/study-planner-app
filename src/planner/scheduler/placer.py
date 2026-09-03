"""Étape E — placement glouton piloté par échéance (EDF) avec fonction de coût.

Fonction pure : plan(courses, evaluations, constraints, settings, today) -> PlanResult.
Aucun accès base, aucun aléatoire, aucun datetime.now() : déterministe et rejouable.

Choix documenté : la fenêtre d'étude s'arrête la veille de l'échéance (le jour J est
réservé à l'épreuve elle-même) — plus strict que la marge ε de §4, jamais moins sûr.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from planner.config import EngineSettings
from planner.core.models import Constraint, Course, Evaluation, StudyBlock
from planner.scheduler.availability import (
    SLOTS_PER_DAY,
    build_grid,
    day_capacity,
    total_capacity,
)
from planner.scheduler.curve import day_targets, revision_window
from planner.scheduler.metrics import PlanMetrics, compute_metrics
from planner.scheduler.workload import total_hours


@dataclass
class PlanResult:
    blocks: list[StudyBlock]
    deficits: dict[str, float]           # external_id -> heures manquantes
    rho: float                           # facteur de réduction en surcharge (1.0 sinon)
    exclusions: dict[str, str]           # external_id -> raison d'exclusion
    targets: dict[str, float]            # external_id -> H_total (après ρ)
    metrics: PlanMetrics = None


@dataclass
class _DayState:
    """État mutable d'un jour pendant le placement."""

    slots_free: list[bool]               # libre selon la grille (contraintes/séances)
    owner: list[int | None] = None       # index d'évaluation par créneau occupé
    hours_total: float = 0.0
    hours_by_eval: dict[int, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.owner is None:
            self.owner = [None] * SLOTS_PER_DAY


def _slot_time(day: date, slot: int) -> datetime:
    return datetime.combine(day, time(slot // 2, 30 * (slot % 2)))


def _free_runs(state: _DayState) -> list[tuple[int, int]]:
    """Plages contiguës [début, fin) de créneaux libres et non occupés."""
    runs, start = [], None
    for i in range(SLOTS_PER_DAY + 1):
        available = i < SLOTS_PER_DAY and state.slots_free[i] and state.owner[i] is None
        if available and start is None:
            start = i
        elif not available and start is not None:
            runs.append((start, i))
            start = None
    return runs


class _Placer:
    def __init__(
        self,
        courses: list[Course],
        evaluations: list[Evaluation],
        constraints: list[Constraint],
        s: EngineSettings,
        today: date,
        previous_blocks: list[StudyBlock] | None,
        fixed_blocks: list[StudyBlock] | None = None,
        hours_done: dict[int, float] | None = None,
    ):
        self.s = s
        self.today = today
        self.courses = {c.id: c for c in courses}
        self.evaluations = evaluations
        self.constraints = constraints
        self.previous = previous_blocks or []
        self.fixed = fixed_blocks or []            # blocs verrouillés/faits : figés
        self.hours_done = hours_done or {}         # clé : id BD d'évaluation -> heures
        self.exclusions: dict[str, str] = {}
        self.placed_init: dict[int, float] = {}
        self.blocks: list[StudyBlock] = []
        self.placed_hours: dict[int, float] = {}   # clé : index d'évaluation
        self.day_states: dict[date, _DayState] = {}

    # -------------------------------------------------------------- préparation

    def prepare(self) -> tuple[list[tuple[Evaluation, tuple[date, date], float]], float]:
        """Filtre les évaluations, calcule fenêtres, charges et facteur ρ."""
        candidates: list[tuple[Evaluation, tuple[date, date]]] = []
        for ev in self.evaluations:
            if ev.archived:
                continue
            if ev.weight <= 0:
                self.exclusions[ev.external_id] = "pondération nulle (bonus) : non planifié"
                continue
            if ev.due_at is None:
                self.exclusions[ev.external_id] = "échéance manquante : à saisir"
                continue
            window = revision_window(ev, self.today, self.s)
            if window is None:
                self.exclusions[ev.external_id] = "trop tard : échéance passée ou imminente"
                continue
            candidates.append((ev, window))

        if not candidates:
            return [], 1.0

        horizon_end = max(w[1] for _, w in candidates)
        grid = build_grid(
            self.today, horizon_end, self.constraints, list(self.courses.values()), self.s
        )
        self.day_states = {
            d: _DayState(slots_free=list(slots)) for d, slots in grid.items()
        }

        # heures restantes après déduction du travail déjà fait (étape F)
        loads: dict[str, float] = {}
        remaining_candidates = []
        for ev, window in candidates:
            full = total_hours(ev, self.courses[ev.course_id], self.s)
            load = max(0.0, full - self.hours_done.get(ev.id, 0.0))
            if load < 0.5:
                self.exclusions[ev.external_id] = "charge déjà couverte par le travail fait"
                continue
            loads[ev.external_id] = load
            remaining_candidates.append((ev, window))
        candidates = remaining_candidates
        if not candidates:
            return [], 1.0

        demand = sum(loads.values())
        capacity = total_capacity(grid, self.s)
        rho = 1.0 if demand <= capacity or demand == 0 else capacity / demand

        ordered = sorted(
            candidates, key=lambda item: (item[0].due_at, -item[0].weight, item[0].external_id)
        )

        # blocs figés (verrouillés, faits) : ils occupent la grille et comptent comme placés
        key_by_db_id = {ev.id: ev_key for ev_key, (ev, _) in enumerate(ordered)}
        self.placed_init: dict[int, float] = {}
        for block in self.fixed:
            day = block.start_at.date()
            if day not in self.day_states:
                continue
            state = self.day_states[day]
            ev_key = key_by_db_id.get(block.evaluation_id, -1)
            start = block.start_at.hour * 2 + (1 if block.start_at.minute >= 30 else 0)
            hours = block.planned_minutes / 60
            for i in range(start, min(start + block.planned_minutes // 30, SLOTS_PER_DAY)):
                state.owner[i] = ev_key
            state.hours_total += hours
            if ev_key >= 0:
                state.hours_by_eval[ev_key] = state.hours_by_eval.get(ev_key, 0.0) + hours
                self.placed_init[ev_key] = self.placed_init.get(ev_key, 0.0) + hours

        return [
            (ev, w, loads[ev.external_id] * rho, loads[ev.external_id]) for ev, w in ordered
        ], rho

    # -------------------------------------------------------------- capacités

    def remaining_capacity(self, day: date) -> float:
        state = self.day_states[day]
        cap = day_capacity(state.slots_free, day, self.s)
        return max(0.0, cap - state.hours_total)

    def remaining_capacity_for(self, day: date, eval_index: int) -> float:
        state = self.day_states[day]
        by_eval = self.s.h_jour_eval - state.hours_by_eval.get(eval_index, 0.0)
        return max(0.0, min(self.remaining_capacity(day), by_eval))

    # -------------------------------------------------------------- coût

    def _cost(self, eval_index: int, eval_db_id: int | None, day: date,
              run: tuple[int, int], start: int, dur_slots: int) -> float:
        s = self.s
        state = self.day_states[day]
        end = start + dur_slots

        p_horaire = s.hour_penalty.get(start // 2, 0.0)

        bloc_min_slots = int(s.bloc_min * 2)
        left, right = start - run[0], run[1] - end
        p_frag = sum(1.0 for leftover in (left, right) if 0 < leftover < bloc_min_slots)

        subjects = set(state.hours_by_eval)
        p_div = 1.0 if eval_index not in subjects and len(subjects) >= s.max_subjects_per_day \
            else 0.0

        # même matière à moins d'une heure sur la même journée
        p_chain = 0.0
        lo, hi = max(0, start - 2), min(SLOTS_PER_DAY, end + 2)
        if any(state.owner[i] == eval_index for i in range(lo, hi)):
            p_chain = 1.0

        p_stab = 0.0
        prev_starts = [
            b.start_at for b in self.previous
            if b.evaluation_id == eval_db_id and b.status == "planned"
        ]
        if prev_starts:
            candidate_start = _slot_time(day, start)
            hours_away = min(
                abs((candidate_start - p).total_seconds()) / 3600 for p in prev_starts
            )
            p_stab = min(hours_away / 24.0, 1.0)

        return (s.c1_horaire * p_horaire + s.c2_fragmentation * p_frag
                + s.c3_diversite * p_div + s.c4_enchainement * p_chain
                + s.c5_stabilite * p_stab)

    # -------------------------------------------------------------- placement

    def _candidates(self, eval_index: int, day: date, dur_slots: int):
        """Positions valides : créneaux libres, pause d'au moins un créneau avec tout bloc."""
        state = self.day_states[day]
        for run in _free_runs(state):
            for start in range(run[0], run[1] - dur_slots + 1):
                end = start + dur_slots
                before = state.owner[start - 1] if start > 0 else None
                after = state.owner[end] if end < SLOTS_PER_DAY else None
                if before is not None or after is not None:
                    continue  # pause obligatoire entre blocs d'étude
                yield run, start

    def place_hours(self, ev_key: int, ev: Evaluation, day: date, hours: float) -> float:
        """Place jusqu'à `hours` heures ce jour-là. Retourne les heures effectivement placées."""
        s = self.s
        placed = 0.0
        need = min(hours, self.remaining_capacity_for(day, ev_key))
        while need >= s.bloc_min:
            duration = min(need, s.bloc_max)
            duration = int(duration * 2) / 2
            best = None
            dur = duration
            while dur >= s.bloc_min and best is None:
                dur_slots = int(dur * 2)
                for run, start in self._candidates(ev_key, day, dur_slots):
                    cost = self._cost(ev_key, ev.id, day, run, start, dur_slots)
                    key = (cost, start)
                    if best is None or key < best[0]:
                        best = (key, start, dur_slots)
                if best is None:
                    dur -= 0.5
            if best is None:
                break
            _, start, dur_slots = best
            state = self.day_states[day]
            for i in range(start, start + dur_slots):
                state.owner[i] = ev_key
            block_hours = dur_slots / 2
            state.hours_total += block_hours
            state.hours_by_eval[ev_key] = state.hours_by_eval.get(ev_key, 0.0) + block_hours
            self.blocks.append(StudyBlock(
                id=None, evaluation_id=ev.id, start_at=_slot_time(day, start),
                end_at=_slot_time(day, start + dur_slots),
                planned_minutes=int(block_hours * 60),
            ))
            placed += block_hours
            need = min(hours - placed, self.remaining_capacity_for(day, ev_key))
        return placed

    def run(self) -> PlanResult:
        ordered, rho = self.prepare()
        targets: dict[str, float] = {}
        deficits: dict[str, float] = {}
        target_curves: dict[str, dict[date, float]] = {}

        for ev_key, (ev, (w_start, w_end), h_total, h_unscaled) in enumerate(ordered):
            targets[ev.external_id] = h_total
            due_day = ev.due_at.date()
            window_days = [
                w_start + timedelta(days=i) for i in range((w_end - w_start).days + 1)
            ]
            capacities = {
                d: self.remaining_capacity_for(d, ev_key) for d in window_days
            }
            h_needed = max(0.0, h_total - self.placed_init.get(ev_key, 0.0))
            day_plan = day_targets(h_needed, window_days, due_day, capacities, self.s)
            target_curves[ev.external_id] = day_plan

            placed_total = self.placed_init.get(ev_key, 0.0)
            # jours traités du plus proche de l'échéance au plus lointain, avec report
            # cumulé (carry) : une courbe aplatie produit des cibles de 0,5 h, sous
            # bloc_min — sans carry elles ne seraient jamais placées et tout le volume
            # partirait dans le reliquat, entassé au début de fenêtre. Le carry agrège
            # les demi-heures en blocs plaçables un jour sur deux, en avançant le
            # travail (jamais vers l'échéance).
            carry = 0.0
            for day in sorted(window_days, key=lambda d: (due_day - d).days):
                want = day_plan.get(day, 0.0) + carry
                if want < self.s.bloc_min:
                    carry = want
                    continue
                placed = self.place_hours(ev_key, ev, day, want)
                placed_total += placed
                carry = want - placed

            # report final : le reliquat (pertes d'arrondi, jours saturés) se place au
            # plus près de l'échéance — la fraîcheur paie, et la veille reste le jour
            # le plus chargé de la fenêtre.
            remaining = h_total - placed_total
            if remaining >= 0.5:
                for day in sorted(window_days, key=lambda d: (due_day - d).days):
                    if remaining < 0.5:
                        break
                    placed = self.place_hours(
                        ev_key, ev, day, max(remaining, self.s.bloc_min)
                    )
                    placed_total += placed
                    remaining -= placed

            self.placed_hours[ev_key] = placed_total
            # Le déficit se mesure contre la charge NON réduite par ρ : en surcharge,
            # l'alerte « préparation insuffisante » doit rester visible (§4, étape G).
            deficit = max(0.0, h_unscaled - placed_total)
            deficits[ev.external_id] = deficit if deficit >= 0.5 else 0.0

        placed_by_external = {
            ev.external_id: self.placed_hours.get(ev_key, 0.0)
            for ev_key, (ev, _, _, _) in enumerate(ordered)
        }
        metrics = compute_metrics(
            self.blocks, targets, placed_by_external, target_curves, self.s
        )
        return PlanResult(
            blocks=sorted(self.blocks, key=lambda b: b.start_at),
            deficits=deficits,
            rho=rho,
            exclusions=self.exclusions,
            targets=targets,
            metrics=metrics,
        )


def plan(
    courses: list[Course],
    evaluations: list[Evaluation],
    constraints: list[Constraint],
    settings: EngineSettings,
    today: date,
    previous_blocks: list[StudyBlock] | None = None,
    fixed_blocks: list[StudyBlock] | None = None,
    hours_done: dict[int, float] | None = None,
) -> PlanResult:
    """Génère un plan d'étude complet. Fonction pure et déterministe.

    previous_blocks : anciens blocs planifiés (terme de stabilité P_stabilité).
    fixed_blocks    : blocs intouchables (verrouillés, faits) qui occupent la grille.
    hours_done      : heures déjà réalisées par id d'évaluation (réduisent la charge).
    """
    return _Placer(
        courses, evaluations, constraints, settings, today,
        previous_blocks, fixed_blocks, hours_done,
    ).run()
