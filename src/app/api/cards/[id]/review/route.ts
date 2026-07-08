import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { applyReview } from "@/lib/srs";
import { toCardDto } from "@/lib/serializers";
import type { Grade } from "@/lib/types";

export const runtime = "nodejs";

const VALID_GRADES: Grade[] = ["again", "hard", "good", "easy"];

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const card = await prisma.card.findUnique({ where: { id } });
  if (!card) {
    return NextResponse.json({ error: "Card not found." }, { status: 404 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { grade } = (body ?? {}) as { grade?: unknown };
  if (typeof grade !== "string" || !VALID_GRADES.includes(grade as Grade)) {
    return NextResponse.json(
      { error: "Field 'grade' must be one of: again, hard, good, easy." },
      { status: 400 },
    );
  }

  const result = applyReview(
    {
      ease: card.ease,
      intervalDays: card.intervalDays,
      reps: card.reps,
      lapses: card.lapses,
    },
    grade as Grade,
  );

  const updated = await prisma.card.update({
    where: { id },
    data: {
      ease: result.ease,
      intervalDays: result.intervalDays,
      reps: result.reps,
      lapses: result.lapses,
      dueAt: result.dueAt,
    },
  });

  await prisma.review.create({
    data: { cardId: id, grade: grade as Grade },
  });

  return NextResponse.json({ card: toCardDto(updated) });
}
