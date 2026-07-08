import { NextResponse } from "next/server";
import prisma from "@/lib/db";
import { generateFlashcards, generateQuiz, generateGuide } from "@/lib/ai";

export const runtime = "nodejs";

type GenerateType = "deck" | "quiz" | "guide";

const TYPE_LABELS: Record<GenerateType, string> = {
  deck: "Deck",
  quiz: "Quiz",
  guide: "Study Guide",
};

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const cls = await prisma.class.findUnique({ where: { id } });
  if (!cls) {
    return NextResponse.json({ error: "Class not found." }, { status: 404 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { type, materialIds } = (body ?? {}) as {
    type?: unknown;
    materialIds?: unknown;
  };

  if (type !== "deck" && type !== "quiz" && type !== "guide") {
    return NextResponse.json(
      { error: "Field 'type' must be one of: deck, quiz, guide." },
      { status: 400 },
    );
  }

  let materials;
  if (Array.isArray(materialIds) && materialIds.length > 0) {
    const ids = materialIds.filter((m): m is string => typeof m === "string");
    materials = await prisma.material.findMany({
      where: { id: { in: ids }, classId: id },
    });
  } else {
    materials = await prisma.material.findMany({
      where: { classId: id, status: "EXTRACTED" },
    });
  }

  const usable = materials.filter(
    (m) => typeof m.extractedText === "string" && m.extractedText.trim().length > 0,
  );

  if (usable.length === 0) {
    return NextResponse.json(
      { error: "No materials with extracted text are available for generation." },
      { status: 400 },
    );
  }

  const combinedText = usable
    .map((m) => `## ${m.filename}\n\n${m.extractedText}`)
    .join("\n\n");

  const title = `${TYPE_LABELS[type as GenerateType]} – ${cls.name} – ${new Date().toLocaleDateString()}`;

  try {
    if (type === "deck") {
      const drafts = await generateFlashcards(combinedText);
      const sourceMaterialId = usable.length === 1 ? usable[0].id : null;
      const deck = await prisma.deck.create({
        data: {
          classId: id,
          title,
          cards: {
            create: drafts.map((d) => ({
              front: d.front,
              back: d.back,
              sourceMaterialId,
            })),
          },
        },
      });
      return NextResponse.json({ deck: { id: deck.id, title: deck.title } });
    }

    if (type === "quiz") {
      const drafts = await generateQuiz(combinedText);
      const quiz = await prisma.quiz.create({
        data: {
          classId: id,
          title,
          questions: {
            create: drafts.map((q, index) => ({
              type: q.type,
              prompt: q.prompt,
              choicesJson: q.choices ? JSON.stringify(q.choices) : null,
              answer: q.answer,
              explanation: q.explanation,
              order: index,
            })),
          },
        },
      });
      return NextResponse.json({ quiz: { id: quiz.id, title: quiz.title } });
    }

    // guide
    const draft = await generateGuide(combinedText, cls.name);
    const guide = await prisma.studyGuide.create({
      data: {
        classId: id,
        title,
        contentMd: draft.contentMd,
      },
    });
    return NextResponse.json({ guide: { id: guide.id, title: guide.title } });
  } catch (err) {
    return NextResponse.json(
      { error: (err as Error).message || "Generation failed." },
      { status: 500 },
    );
  }
}
