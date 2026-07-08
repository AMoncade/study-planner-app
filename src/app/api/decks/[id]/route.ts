import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { toCardDto } from "@/lib/serializers";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const deck = await prisma.deck.findUnique({
    where: { id },
    include: { cards: { orderBy: { createdAt: "asc" } } },
  });

  if (!deck) {
    return NextResponse.json({ error: "Deck not found." }, { status: 404 });
  }

  return NextResponse.json({
    deck: {
      id: deck.id,
      title: deck.title,
      classId: deck.classId,
      cards: deck.cards.map(toCardDto),
    },
  });
}
