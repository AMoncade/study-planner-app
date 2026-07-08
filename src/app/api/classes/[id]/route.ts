import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { toMaterialDto } from "@/lib/serializers";
import type {
  ClassDetailDto,
  DeckSummaryDto,
  QuizSummaryDto,
  GuideSummaryDto,
} from "@/lib/types";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const cls = await prisma.class.findUnique({
    where: { id },
    include: {
      materials: { orderBy: { createdAt: "desc" } },
      decks: {
        orderBy: { createdAt: "desc" },
        include: { _count: { select: { cards: true } } },
      },
      quizzes: {
        orderBy: { createdAt: "desc" },
        include: { _count: { select: { questions: true } } },
      },
      guides: { orderBy: { createdAt: "desc" } },
    },
  });

  if (!cls) {
    return NextResponse.json({ error: "Class not found." }, { status: 404 });
  }

  const now = new Date();
  const decks: DeckSummaryDto[] = [];
  for (const deck of cls.decks) {
    const dueCount = await prisma.card.count({
      where: { deckId: deck.id, dueAt: { lte: now } },
    });
    decks.push({
      id: deck.id,
      title: deck.title,
      cardCount: deck._count.cards,
      dueCount,
      createdAt: deck.createdAt.toISOString(),
    });
  }

  const quizzes: QuizSummaryDto[] = cls.quizzes.map((q) => ({
    id: q.id,
    title: q.title,
    questionCount: q._count.questions,
    createdAt: q.createdAt.toISOString(),
  }));

  const guides: GuideSummaryDto[] = cls.guides.map((g) => ({
    id: g.id,
    title: g.title,
    createdAt: g.createdAt.toISOString(),
  }));

  const dto: ClassDetailDto = {
    id: cls.id,
    name: cls.name,
    term: cls.term,
    materials: cls.materials.map(toMaterialDto),
    decks,
    quizzes,
    guides,
  };

  return NextResponse.json({ class: dto });
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const existing = await prisma.class.findUnique({ where: { id } });
  if (!existing) {
    return NextResponse.json({ error: "Class not found." }, { status: 404 });
  }

  await prisma.class.delete({ where: { id } });
  return NextResponse.json({ ok: true });
}
