import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import type { GradeResultDto } from "@/lib/types";

export const runtime = "nodejs";

function norm(value: string): string {
  return value.trim().toLowerCase();
}

function isCorrect(type: string, expected: string, given: string): boolean {
  const e = norm(expected);
  const g = norm(given);
  if (type === "short") {
    if (e === g) return true;
    if (e.length > 0 && g.length > 0) {
      return e.includes(g) || g.includes(e);
    }
    return false;
  }
  // mcq and tf: exact case-insensitive trimmed match
  return e === g;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const quiz = await prisma.quiz.findUnique({
    where: { id },
    include: { questions: { orderBy: { order: "asc" } } },
  });

  if (!quiz) {
    return NextResponse.json({ error: "Quiz not found." }, { status: 404 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { answers } = (body ?? {}) as { answers?: unknown };
  if (!answers || typeof answers !== "object" || Array.isArray(answers)) {
    return NextResponse.json(
      { error: "Field 'answers' must be an object mapping questionId to answer." },
      { status: 400 },
    );
  }
  const answerMap = answers as Record<string, unknown>;

  const results: GradeResultDto[] = [];
  let score = 0;

  for (const q of quiz.questions) {
    const rawAnswer = answerMap[q.id];
    const yourAnswer = typeof rawAnswer === "string" ? rawAnswer : "";
    const correct = isCorrect(q.type, q.answer, yourAnswer);
    if (correct) score += 1;
    results.push({
      questionId: q.id,
      correct,
      correctAnswer: q.answer,
      explanation: q.explanation,
      yourAnswer,
    });
  }

  return NextResponse.json({
    score,
    total: quiz.questions.length,
    results,
  });
}
