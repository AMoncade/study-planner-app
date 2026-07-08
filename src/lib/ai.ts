import { promises as fs } from "fs";
import Anthropic from "@anthropic-ai/sdk";
import type { QuestionType } from "@/lib/types";

const MAX_INPUT_CHARS = 40000;

export interface FlashcardDraft {
  front: string;
  back: string;
}

export interface QuizQuestionDraft {
  type: QuestionType;
  prompt: string;
  choices?: string[];
  answer: string;
  explanation: string;
}

export interface GuideDraft {
  title: string;
  contentMd: string;
}

export function isMockMode(): boolean {
  return process.env.MOCK_AI === "1" || !process.env.ANTHROPIC_API_KEY;
}

function getModel(): string {
  return process.env.ANTHROPIC_MODEL || "claude-sonnet-5";
}

function getClient(): Anthropic {
  return new Anthropic();
}

function truncate(text: string): string {
  return text.length > MAX_INPUT_CHARS ? text.slice(0, MAX_INPUT_CHARS) : text;
}

function isTextMime(mimeType: string): boolean {
  return (
    mimeType === "text/plain" ||
    mimeType === "text/markdown" ||
    mimeType === "text/csv" ||
    mimeType === "text/x-markdown"
  );
}

/**
 * Pull the concatenated text out of an Anthropic message response.
 */
function collectText(message: Anthropic.Message): string {
  return message.content
    .filter((block): block is Anthropic.TextBlock => block.type === "text")
    .map((block) => block.text)
    .join("\n")
    .trim();
}

/**
 * Robustly parse a JSON array/object out of a model response that may be
 * wrapped in markdown fences or surrounded by prose.
 */
function parseJsonFromModel(raw: string): unknown {
  let text = raw.trim();

  // Strip markdown code fences if present.
  const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenceMatch) {
    text = fenceMatch[1].trim();
  }

  // Find the outermost JSON structure: from first [ or { to last ] or }.
  const firstArray = text.indexOf("[");
  const firstObject = text.indexOf("{");
  let start = -1;
  let closeChar = "";
  if (firstArray === -1 && firstObject === -1) {
    throw new Error("No JSON structure found in model response.");
  }
  if (firstArray !== -1 && (firstObject === -1 || firstArray < firstObject)) {
    start = firstArray;
    closeChar = "]";
  } else {
    start = firstObject;
    closeChar = "}";
  }
  const end = text.lastIndexOf(closeChar);
  if (end === -1 || end < start) {
    throw new Error("Malformed JSON structure in model response.");
  }
  const candidate = text.slice(start, end + 1);

  try {
    return JSON.parse(candidate);
  } catch (err) {
    throw new Error(
      `Failed to parse JSON from model response: ${(err as Error).message}`,
    );
  }
}

function splitSentences(text: string): string[] {
  return text
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

// ---------------------------------------------------------------------------
// Extraction
// ---------------------------------------------------------------------------

export async function extractText(
  filePath: string,
  mimeType: string,
  filename: string,
): Promise<string> {
  // Plain text formats are read directly in both mock and real mode.
  if (isTextMime(mimeType)) {
    return await fs.readFile(filePath, "utf-8");
  }

  const isPdf = mimeType === "application/pdf";
  const isImage = mimeType.startsWith("image/");

  if (!isPdf && !isImage) {
    // Unknown binary type — best effort read as utf-8.
    return await fs.readFile(filePath, "utf-8");
  }

  if (isMockMode()) {
    return (
      `[MOCK EXTRACTION] Mock mode is on (no API key). Placeholder content for ${filename}.\n\n` +
      "Photosynthesis is the process by which plants convert light energy into chemical energy. " +
      "The mitochondria is the powerhouse of the cell. " +
      "Newton's second law states that force equals mass times acceleration. " +
      "The French Revolution began in 1789. " +
      "Water is composed of two hydrogen atoms and one oxygen atom."
    );
  }

  const client = getClient();
  const bytes = await fs.readFile(filePath);
  const base64 = bytes.toString("base64");

  const prompt =
    "Transcribe all content in this document faithfully into plain text. " +
    "Include every piece of text, including any handwriting. " +
    "Preserve the structure using Markdown (headings, lists, tables) where appropriate. " +
    "Output only the transcription, with no preamble or commentary.";

  const contentBlock = isPdf
    ? ({
        type: "document",
        source: {
          type: "base64",
          media_type: "application/pdf",
          data: base64,
        },
      } as Anthropic.DocumentBlockParam)
    : ({
        type: "image",
        source: {
          type: "base64",
          media_type: mimeType as
            | "image/jpeg"
            | "image/png"
            | "image/gif"
            | "image/webp",
          data: base64,
        },
      } as Anthropic.ImageBlockParam);

  const message = await client.messages.create({
    model: getModel(),
    max_tokens: 8000,
    messages: [
      {
        role: "user",
        content: [contentBlock, { type: "text", text: prompt }],
      },
    ],
  });

  const text = collectText(message);
  if (!text) {
    throw new Error("Extraction returned no text content.");
  }
  return text;
}

// ---------------------------------------------------------------------------
// Flashcard generation
// ---------------------------------------------------------------------------

export async function generateFlashcards(text: string): Promise<FlashcardDraft[]> {
  if (isMockMode()) {
    return mockFlashcards(text);
  }

  const client = getClient();
  const prompt =
    "You are creating study flashcards from the material below. " +
    "Produce between 15 and 25 flashcards covering the key concepts, definitions, and formulas. " +
    "Include some cloze-style (fill-in-the-blank) cards. " +
    "Respond with ONLY a JSON array, no prose and no markdown fences, in exactly this shape: " +
    '[{"front": "question or prompt", "back": "answer"}]. ' +
    `\n\nMATERIAL:\n${truncate(text)}`;

  const message = await client.messages.create({
    model: getModel(),
    max_tokens: 8000,
    messages: [{ role: "user", content: prompt }],
  });

  const parsed = parseJsonFromModel(collectText(message));
  if (!Array.isArray(parsed)) {
    throw new Error("Flashcard generation did not return a JSON array.");
  }
  const cards: FlashcardDraft[] = [];
  for (const item of parsed) {
    if (
      item &&
      typeof item === "object" &&
      typeof (item as Record<string, unknown>).front === "string" &&
      typeof (item as Record<string, unknown>).back === "string"
    ) {
      const front = (item as Record<string, string>).front.trim();
      const back = (item as Record<string, string>).back.trim();
      if (front && back) cards.push({ front, back });
    }
  }
  if (cards.length === 0) {
    throw new Error("Flashcard generation produced no valid cards.");
  }
  return cards;
}

// ---------------------------------------------------------------------------
// Quiz generation
// ---------------------------------------------------------------------------

export async function generateQuiz(text: string): Promise<QuizQuestionDraft[]> {
  if (isMockMode()) {
    return mockQuiz(text);
  }

  const client = getClient();
  const prompt =
    "You are creating a quiz from the material below. " +
    "Produce between 8 and 12 questions mixing multiple choice, true/false, and short answer. " +
    'Each multiple-choice question ("mcq") must have exactly 4 choices, with the answer being one of the choices verbatim. ' +
    'True/false questions ("tf") must have an answer of "true" or "false". ' +
    'Short answer questions ("short") expect a concise answer. ' +
    "Every question must include an explanation. " +
    "Respond with ONLY a JSON array, no prose and no markdown fences, in exactly this shape: " +
    '[{"type": "mcq"|"tf"|"short", "prompt": "the question", "choices": ["a","b","c","d"], "answer": "correct answer", "explanation": "why"}]. ' +
    'Omit "choices" for tf and short questions. ' +
    `\n\nMATERIAL:\n${truncate(text)}`;

  const message = await client.messages.create({
    model: getModel(),
    max_tokens: 8000,
    messages: [{ role: "user", content: prompt }],
  });

  const parsed = parseJsonFromModel(collectText(message));
  if (!Array.isArray(parsed)) {
    throw new Error("Quiz generation did not return a JSON array.");
  }
  const questions: QuizQuestionDraft[] = [];
  for (const item of parsed) {
    if (!item || typeof item !== "object") continue;
    const rec = item as Record<string, unknown>;
    const type = rec.type;
    if (type !== "mcq" && type !== "tf" && type !== "short") continue;
    if (typeof rec.prompt !== "string" || typeof rec.answer !== "string") continue;
    const question: QuizQuestionDraft = {
      type,
      prompt: rec.prompt.trim(),
      answer: rec.answer.trim(),
      explanation: typeof rec.explanation === "string" ? rec.explanation.trim() : "",
    };
    if (type === "mcq") {
      if (
        !Array.isArray(rec.choices) ||
        !rec.choices.every((c) => typeof c === "string")
      ) {
        continue;
      }
      question.choices = (rec.choices as string[]).map((c) => c.trim());
    }
    if (!question.prompt || !question.answer) continue;
    questions.push(question);
  }
  if (questions.length === 0) {
    throw new Error("Quiz generation produced no valid questions.");
  }
  return questions;
}

// ---------------------------------------------------------------------------
// Study guide generation
// ---------------------------------------------------------------------------

export async function generateGuide(
  text: string,
  className: string,
): Promise<GuideDraft> {
  if (isMockMode()) {
    return mockGuide(text);
  }

  const client = getClient();
  const prompt =
    `You are creating an organized study guide for the class "${className}" from the material below. ` +
    "The guide should use Markdown with clear headings, cover key terms, and highlight likely exam points. " +
    "Respond with ONLY a JSON object, no prose and no markdown fences, in exactly this shape: " +
    '{"title": "a concise guide title", "contentMd": "the full study guide in Markdown"}. ' +
    `\n\nMATERIAL:\n${truncate(text)}`;

  const message = await client.messages.create({
    model: getModel(),
    max_tokens: 8000,
    messages: [{ role: "user", content: prompt }],
  });

  const parsed = parseJsonFromModel(collectText(message));
  if (
    !parsed ||
    typeof parsed !== "object" ||
    Array.isArray(parsed) ||
    typeof (parsed as Record<string, unknown>).title !== "string" ||
    typeof (parsed as Record<string, unknown>).contentMd !== "string"
  ) {
    throw new Error("Guide generation did not return a valid object.");
  }
  const rec = parsed as Record<string, string>;
  const title = rec.title.trim();
  const contentMd = rec.contentMd.trim();
  if (!title || !contentMd) {
    throw new Error("Guide generation produced empty content.");
  }
  return { title, contentMd };
}

// ---------------------------------------------------------------------------
// Deterministic mock generators (pure functions of the input text)
// ---------------------------------------------------------------------------

const MOCK_DISTRACTORS = [
  "None of the above",
  "An unrelated concept",
  "A common misconception",
];

function firstWords(sentence: string, count: number): string {
  return sentence.split(/\s+/).slice(0, count).join(" ");
}

function mockFlashcards(text: string): FlashcardDraft[] {
  const sentences = splitSentences(text);
  const cards: FlashcardDraft[] = [];
  for (const sentence of sentences.slice(0, 10)) {
    cards.push({
      front: `Recall (mock): "${firstWords(sentence, 8)}..."`,
      back: sentence,
    });
  }
  if (cards.length === 0) {
    cards.push({
      front: 'Recall (mock): "No content available..."',
      back: "No study material was provided.",
    });
  }
  return cards;
}

function mockQuiz(text: string): QuizQuestionDraft[] {
  const sentences = splitSentences(text);
  const questions: QuizQuestionDraft[] = [];
  const usable = sentences.slice(0, 6);
  usable.forEach((sentence, index) => {
    if (index % 2 === 0) {
      questions.push({
        type: "mcq",
        prompt: `Which statement is correct? (mock #${index + 1})`,
        choices: [sentence, ...MOCK_DISTRACTORS],
        answer: sentence,
        explanation: "The correct choice is the statement taken from the source material.",
      });
    } else {
      questions.push({
        type: "tf",
        prompt: `True or false (mock #${index + 1}): ${sentence}`,
        answer: "true",
        explanation: "This statement is drawn directly from the source material, so it is true.",
      });
    }
  });
  // Add a short-answer question if we have material for it.
  if (usable.length > 0) {
    const sentence = usable[0];
    questions.push({
      type: "short",
      prompt: `Short answer (mock): What is the first key term in: "${firstWords(sentence, 8)}..."?`,
      answer: firstWords(sentence, 1),
      explanation: "The expected answer is the first word of the source sentence.",
    });
  }
  if (questions.length === 0) {
    questions.push({
      type: "short",
      prompt: "Short answer (mock): No content was provided. What should you upload?",
      answer: "material",
      explanation: "Upload study material to generate a real quiz.",
    });
  }
  return questions;
}

function mockGuide(text: string): GuideDraft {
  const sentences = splitSentences(text);
  const bullets = sentences.length
    ? sentences.map((s) => `- ${s}`).join("\n")
    : "- No study material was provided.";
  const contentMd = `# Study Guide (mock)\n\n## Key Points\n\n${bullets}\n`;
  return { title: "Study Guide (mock)", contentMd };
}
