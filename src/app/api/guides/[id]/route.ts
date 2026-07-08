import { NextResponse } from "next/server";
import prisma from "@/lib/db";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const guide = await prisma.studyGuide.findUnique({ where: { id } });
  if (!guide) {
    return NextResponse.json({ error: "Guide not found." }, { status: 404 });
  }

  return NextResponse.json({
    guide: { id: guide.id, title: guide.title, contentMd: guide.contentMd },
  });
}
