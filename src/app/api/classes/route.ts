import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import type { ClassSummaryDto } from "@/lib/types";

export const runtime = "nodejs";

export async function GET() {
  const classes = await prisma.class.findMany({
    orderBy: { createdAt: "desc" },
    include: {
      _count: {
        select: { materials: true, decks: true, quizzes: true, guides: true },
      },
    },
  });

  const dtos: ClassSummaryDto[] = classes.map((c) => ({
    id: c.id,
    name: c.name,
    term: c.term,
    counts: {
      materials: c._count.materials,
      decks: c._count.decks,
      quizzes: c._count.quizzes,
      guides: c._count.guides,
    },
  }));

  return NextResponse.json({ classes: dtos });
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { name, term } = (body ?? {}) as { name?: unknown; term?: unknown };
  if (typeof name !== "string" || name.trim().length === 0) {
    return NextResponse.json(
      { error: "A non-empty 'name' is required." },
      { status: 400 },
    );
  }

  const created = await prisma.class.create({
    data: {
      name: name.trim(),
      term: typeof term === "string" && term.trim().length > 0 ? term.trim() : null,
    },
  });

  return NextResponse.json({
    class: { id: created.id, name: created.name, term: created.term },
  });
}
