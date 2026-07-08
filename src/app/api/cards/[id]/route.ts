import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { toCardDto } from "@/lib/serializers";

export const runtime = "nodejs";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const existing = await prisma.card.findUnique({ where: { id } });
  if (!existing) {
    return NextResponse.json({ error: "Card not found." }, { status: 404 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { front, back } = (body ?? {}) as { front?: unknown; back?: unknown };
  const data: { front?: string; back?: string } = {};
  if (front !== undefined) {
    if (typeof front !== "string") {
      return NextResponse.json({ error: "'front' must be a string." }, { status: 400 });
    }
    data.front = front;
  }
  if (back !== undefined) {
    if (typeof back !== "string") {
      return NextResponse.json({ error: "'back' must be a string." }, { status: 400 });
    }
    data.back = back;
  }

  const updated = await prisma.card.update({ where: { id }, data });
  return NextResponse.json({ card: toCardDto(updated) });
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const existing = await prisma.card.findUnique({ where: { id } });
  if (!existing) {
    return NextResponse.json({ error: "Card not found." }, { status: 404 });
  }

  await prisma.card.delete({ where: { id } });
  return NextResponse.json({ ok: true });
}
