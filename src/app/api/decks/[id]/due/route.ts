import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { toCardDto } from "@/lib/serializers";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const deck = await prisma.deck.findUnique({ where: { id } });
  if (!deck) {
    return NextResponse.json({ error: "Deck not found." }, { status: 404 });
  }

  const cards = await prisma.card.findMany({
    where: { deckId: id, dueAt: { lte: new Date() } },
    orderBy: { dueAt: "asc" },
  });

  return NextResponse.json({ cards: cards.map(toCardDto) });
}
