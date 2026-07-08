import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { parseQuestionType } from "@/lib/serializers";
import type { QuizDetailDto, QuizQuestionDto } from "@/lib/types";

export const runtime = "nodejs";

function parseChoices(choicesJson: string | null): string[] | undefined {
  if (!choicesJson) return undefined;
  try {
    const parsed = JSON.parse(choicesJson);
    if (Array.isArray(parsed) && parsed.every((c) => typeof c === "string")) {
      return parsed as string[];
    }
  } catch {
    // fall through
  }
  return undefined;
}

export async function GET(
  _request: Request,
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

  const questions: QuizQuestionDto[] = quiz.questions.map((q) => ({
    id: q.id,
    type: parseQuestionType(q.type),
    prompt: q.prompt,
    choices: parseChoices(q.choicesJson),
  }));

  const dto: QuizDetailDto = {
    id: quiz.id,
    title: quiz.title,
    questions,
  };

  return NextResponse.json({ quiz: dto });
}
