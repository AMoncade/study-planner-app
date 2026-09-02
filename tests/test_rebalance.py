"""Tests de l'étape F : recalcul incrémental."""

from datetime import date, datetime

from planner.config import EngineSettings
from planner.core.models import Course, Evaluation, StudyBlock
from planner.scheduler.placer import plan
from planner.scheduler.rebalance import hours_done_by_evaluation, rebalance

S = EngineSettings()
TODAY = date(2026, 9, 1)
NOW = datetime(2026, 9, 8, 12, 0)


def make_course(**kwargs) -> Course:
    defaults = dict(id=1, code="MAT1000", title="Analyse 1", term="A26")
    defaults.update(kwargs)
    return Course(**defaults)


def make_eval(**kwargs) -> Evaluation:
    defaults = dict(
        id=1, course_id=1, external_id="MAT1000-INTRA", title="Intra",
        type="examen_intra", weight=40.0, due_at=datetime(2026, 9, 20, 8, 0),
        scope_units=4,
    )
    defaults.update(kwargs)
    return Evaluation(**defaults)


def block(bid, eval_id, start, hours, status="planned", locked=False,
          actual=None, eff=None) -> StudyBlock:
    end = start.replace(hour=start.hour + int(hours), minute=start.minute)
    return StudyBlock(
        id=bid, evaluation_id=eval_id, start_at=start, end_at=end,
        planned_minutes=int(hours * 60), status=status, locked=locked,
        actual_minutes=actual, efficiency=eff,
    )


def hours_of(result):
    return sum(b.planned_minutes for b in result.blocks) / 60


def test_hours_done_counts_done_and_partial_not_skipped():
    blocks = [
        block(1, 1, datetime(2026, 9, 2, 9, 0), 2, status="done"),
        block(2, 1, datetime(2026, 9, 3, 9, 0), 2, status="partial", actual=60),
        block(3, 1, datetime(2026, 9, 4, 9, 0), 2, status="skipped"),
        block(4, 1, datetime(2026, 9, 5, 9, 0), 2, status="planned"),
    ]
    done = hours_done_by_evaluation(blocks)
    assert done[1] == 3.0  # 2 h faites + 1 h partielle ; skipped/planned ignorés


def test_efficiency_weights_done_hours():
    blocks = [block(1, 1, datetime(2026, 9, 2, 9, 0), 2, status="done", eff=0.5)]
    assert hours_done_by_evaluation(blocks)[1] == 1.0


def test_done_work_reduces_replanned_hours():
    course, ev = make_course(), make_eval()
    baseline, _ = rebalance([course], [ev], [], [], S, NOW)
    done = [block(1, 1, datetime(2026, 9, 6, 9, 0), 2, status="done"),
            block(2, 1, datetime(2026, 9, 7, 9, 0), 2, status="done")]
    lighter, _ = rebalance([course], [ev], [], done, S, NOW)
    assert hours_of(lighter) <= hours_of(baseline) - 3.5  # ~4 h de moins


def test_skipped_does_not_reduce_load():
    course, ev = make_course(), make_eval()
    baseline, _ = rebalance([course], [ev], [], [], S, NOW)
    skipped = [block(1, 1, datetime(2026, 9, 6, 9, 0), 2, status="skipped")]
    same, _ = rebalance([course], [ev], [], skipped, S, NOW)
    assert hours_of(same) == hours_of(baseline)


def test_locked_block_is_kept_and_counted():
    course, ev = make_course(), make_eval()
    locked = block(7, 1, datetime(2026, 9, 15, 9, 0), 2, locked=True)
    result, diff = rebalance([course], [ev], [], [locked], S, NOW)
    # aucun nouveau bloc ne chevauche le bloc verrouillé
    for b in result.blocks:
        assert not (b.start_at < locked.end_at and locked.start_at < b.end_at)
    # le temps verrouillé compte comme placé : total nouveau + 2 h ≈ charge cible
    target = result.targets["MAT1000-INTRA"]
    assert hours_of(result) + 2.0 >= target - 1.0


def test_stability_keeps_most_blocks_in_place():
    course, ev = make_course(), make_eval()
    first = plan([course], [ev], [], S, NOW.date())
    existing = [
        StudyBlock(id=i + 1, evaluation_id=b.evaluation_id, start_at=b.start_at,
                   end_at=b.end_at, planned_minutes=b.planned_minutes)
        for i, b in enumerate(first.blocks)
    ]
    _result, diff = rebalance([course], [ev], [], existing, S, NOW)
    # mêmes données, mêmes contraintes : P_stabilité doit garder la majorité en place
    assert diff.kept >= len(existing) * 0.6


def test_diff_counts_are_consistent():
    course, ev = make_course(), make_eval()
    existing = [block(1, 1, datetime(2026, 9, 10, 9, 0), 2)]
    result, diff = rebalance([course], [ev], [], existing, S, NOW)
    assert diff.kept + diff.moved == min(len(existing), len(result.blocks))
    assert diff.freed_ids == [1]
    assert diff.new_blocks == result.blocks
