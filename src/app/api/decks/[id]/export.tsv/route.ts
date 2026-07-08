import { NextResponse } from "next/server";
import prisma from "@/lib/db";

export const runtime = "nodejs";

function clean(field: string): string {
  return field.replace(/[\t\r\n]+/g, " ");
}

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

  const body = deck.cards
    .map((c) => `${clean(c.front)}\t${clean(c.back)}`)
    .join("\n");

  return new NextResponse(body, {
    status: 200,
    headers: {
      "Content-Type": "text/tab-separated-values; charset=utf-8",
      "Content-Disposition": `attachment; filename="deck-${id}.tsv"`,
    },
  });
}
