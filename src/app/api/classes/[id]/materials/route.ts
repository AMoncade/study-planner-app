import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import prisma from "@/lib/db";
import { extractText } from "@/lib/ai";
import { toMaterialDto } from "@/lib/serializers";
import type { MaterialDto } from "@/lib/types";

export const runtime = "nodejs";

function sanitizeFilename(name: string): string {
  const base = path.basename(name || "file");
  const cleaned = base.replace(/[^A-Za-z0-9._-]/g, "_");
  return cleaned.length > 0 ? cleaned : "file";
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const cls = await prisma.class.findUnique({ where: { id } });
  if (!cls) {
    return NextResponse.json({ error: "Class not found." }, { status: 404 });
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "Expected multipart/form-data." },
      { status: 400 },
    );
  }

  const entries = formData.getAll("files").filter((f): f is File => f instanceof File);
  if (entries.length === 0) {
    return NextResponse.json(
      { error: "No files provided in the 'files' field." },
      { status: 400 },
    );
  }

  const uploadsDir = path.join(process.cwd(), "uploads");
  await fs.mkdir(uploadsDir, { recursive: true });

  const results: MaterialDto[] = [];

  for (const file of entries) {
    const filename = file.name || "file";
    const mimeType = file.type || "application/octet-stream";

    const material = await prisma.material.create({
      data: {
        classId: id,
        filename,
        mimeType,
        filePath: "",
        status: "UPLOADED",
      },
    });

    const safeName = `${material.id}-${sanitizeFilename(filename)}`;
    const filePath = path.join(uploadsDir, safeName);

    try {
      const bytes = Buffer.from(await file.arrayBuffer());
      await fs.writeFile(filePath, bytes);
      await prisma.material.update({
        where: { id: material.id },
        data: { filePath },
      });

      const text = await extractText(filePath, mimeType, filename);
      const updated = await prisma.material.update({
        where: { id: material.id },
        data: { extractedText: text, status: "EXTRACTED", error: null },
      });
      results.push(toMaterialDto(updated));
    } catch (err) {
      const updated = await prisma.material.update({
        where: { id: material.id },
        data: {
          status: "FAILED",
          error: (err as Error).message || "Extraction failed.",
        },
      });
      results.push(toMaterialDto(updated));
    }
  }

  return NextResponse.json({ materials: results });
}
