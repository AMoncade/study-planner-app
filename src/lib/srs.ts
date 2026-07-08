import type { Grade } from "@/lib/types";

export interface SrsState {
  ease: number;
  intervalDays: number;
  reps: number;
  lapses: number;
}

export interface SrsResult extends SrsState {
  dueAt: Date;
}

const GRADE_TO_QUALITY: Record<Grade, number> = {
  again: 1,
  hard: 3,
  good: 4,
  easy: 5,
};

/**
 * SM-2 scheduler.
 *
 * Grade → quality mapping: again=1, hard=3, good=4, easy=5.
 *
 * If quality < 3 (a lapse): reps reset to 0, lapses incremented, interval 0,
 * due in 10 minutes. Otherwise reps incremented and interval grows
 * (1 day, then 6 days, then intervalDays * ease). The ease factor is always
 * updated afterwards with the standard SM-2 formula, clamped to a 1.3 floor.
 */
export function applyReview(
  card: { ease: number; intervalDays: number; reps: number; lapses: number },
  grade: Grade,
): SrsResult {
  const quality = GRADE_TO_QUALITY[grade];
  const now = Date.now();

  let { ease, intervalDays, reps, lapses } = card;

  if (quality < 3) {
    reps = 0;
    lapses = lapses + 1;
    intervalDays = 0;
    const dueAt = new Date(now + 10 * 60 * 1000);
    ease = Math.max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));
    return { ease, intervalDays, reps, lapses, dueAt };
  }

  reps = reps + 1;
  if (reps === 1) {
    intervalDays = 1;
  } else if (reps === 2) {
    intervalDays = 6;
  } else {
    intervalDays = Math.round(intervalDays * ease);
  }

  const dueAt = new Date(now + intervalDays * 24 * 60 * 60 * 1000);
  ease = Math.max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02));

  return { ease, intervalDays, reps, lapses, dueAt };
}
