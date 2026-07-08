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

// ---------------------------------------------------------------------------
// Provider resolution
// ---------------------------------------------------------------------------

export type AiProvider = "ollama" | "anthropic" | "offline";

/**
 * Decide which AI backend to use. `AI_PROVIDER` wins if it's a valid value.
 * Otherwise: use Anthropic if a key is configured (and MOCK_AI isn't forcing
 * offline mode), else fall back to Ollama, the local/default engine.
 */
export function getProvider(): AiProvider {
  const envProvider = process.env.AI_PROVIDER;
  if (envProvider === "ollama" || envProvider === "anthropic" || envProvider === "offline") {
    return envProvider;
  }
  if (process.env.ANTHROPIC_API_KEY && process.env.MOCK_AI !== "1") {
    return "anthropic";
  }
  return "ollama";
}

/** True when running the offline heuristic path (no AI engine at all). */
export function isMockMode(): boolean {
  return getProvider() === "offline";
}

export function ollamaHost(): string {
  return process.env.OLLAMA_HOST || "http://localhost:11434";
}

export function ollamaModel(): string {
  return process.env.OLLAMA_MODEL || "llama3.1";
}

export function ollamaVisionModel(): string {
  return process.env.OLLAMA_VISION_MODEL || "llama3.2-vision";
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

// ---------------------------------------------------------------------------
// Ollama client
// ---------------------------------------------------------------------------

const OLLAMA_TIMEOUT_MS = 180000;

/**
 * Call a local Ollama server's chat endpoint and return the response text.
 * `images`, when provided, are base64 strings with no `data:` prefix.
 */
async function ollamaChat(opts: {
  model: string;
  prompt: string;
  images?: string[];
  json?: boolean;
}): Promise<string> {
  const host = ollamaHost();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), OLLAMA_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${host}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: opts.model,
        messages: [
          {
            role: "user",
            content: opts.prompt,
            ...(opts.images ? { images: opts.images } : {}),
          },
        ],
        stream: false,
        ...(opts.json ? { format: "json" } : {}),
        options: { temperature: 0.2, num_predict: 4096 },
      }),
      signal: controller.signal,
    });
  } catch {
    throw new Error(
      `Cannot reach Ollama at ${host}. Install it from https://ollama.com, then run: ollama serve  (and once) ollama pull ${opts.model}.`,
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(
        `Ollama model "${opts.model}" is not installed. Run: ollama pull ${opts.model}`,
      );
    }
    const body = await response.text().catch(() => "");
    throw new Error(`Ollama request failed with status ${response.status}: ${body}`);
  }

  const data = (await response.json()) as { message?: { content?: string } };
  const content = data.message?.content?.trim();
  if (!content) {
    throw new Error("Ollama returned an empty response.");
  }
  return content;
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
    .split(/\r?\n/)
    // Drop Markdown heading lines (e.g. the "## filename" separators added
    // when concatenating materials) so they don't leak into offline cards.
    .filter((line) => !/^\s*#{1,6}\s/.test(line))
    .join(" ")
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
  // Plain text formats are read directly regardless of provider.
  if (isTextMime(mimeType)) {
    return await fs.readFile(filePath, "utf-8");
  }

  const isPdf = mimeType === "application/pdf";
  const isImage = mimeType.startsWith("image/");

  if (!isPdf && !isImage) {
    // Unknown binary type — best effort read as utf-8.
    return await fs.readFile(filePath, "utf-8");
  }

  if (isPdf) {
    // PDFs are always extracted locally with pdf-parse: it's free and works
    // offline, and a typed PDF's text layer is more reliable than sending
    // rendered pages through a model. No provider needs to be involved.
    // Import the internal module directly to skip pdf-parse's debug
    // self-test, which tries to read a bundled sample file on plain import.
    const pdfParse = (await import("pdf-parse/lib/pdf-parse.js")).default;
    const bytes = await fs.readFile(filePath);
    // Pass a plain Uint8Array, not the Node Buffer subclass: pdf-parse's
    // bundled (old) pdf.js misparses the xref table on modern Node when
    // given a Buffer directly, throwing "bad XRef entry" on otherwise
    // valid PDFs.
    const result = await pdfParse(new Uint8Array(bytes));
    const text = result.text || "";
    if (!text.trim()) {
      throw new Error(
        "This PDF has no selectable text (looks scanned). Scanned PDFs and photos need an API key for OCR; typed PDFs and .txt/.md files work offline. " +
          "(Tip: photograph the pages and upload them as images to OCR with Ollama vision.)",
      );
    }
    return text;
  }

  // isImage
  const provider = getProvider();
  const prompt =
    "Transcribe all content in this document faithfully into plain text. " +
    "Include every piece of text, including any handwriting. " +
    "Preserve the structure using Markdown (headings, lists, tables) where appropriate. " +
    "Output only the transcription, with no preamble or commentary.";

  if (provider === "offline") {
    throw new Error(
      "Image OCR needs an AI engine. Use Ollama (set AI_PROVIDER=ollama and pull a vision model like llama3.2-vision) or set ANTHROPIC_API_KEY. Text files and typed PDFs work with no AI.",
    );
  }

  if (provider === "ollama") {
    const bytes = await fs.readFile(filePath);
    const base64 = bytes.toString("base64");
    return await ollamaChat({ model: ollamaVisionModel(), prompt, images: [base64] });
  }

  // anthropic
  const client = getClient();
  const bytes = await fs.readFile(filePath);
  const base64 = bytes.toString("base64");
  const contentBlock: Anthropic.ImageBlockParam = {
    type: "image",
    source: {
      type: "base64",
      media_type: mimeType as "image/jpeg" | "image/png" | "image/gif" | "image/webp",
      data: base64,
    },
  };

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

function validateFlashcards(parsed: unknown): FlashcardDraft[] {
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

export async function generateFlashcards(text: string): Promise<FlashcardDraft[]> {
  const provider = getProvider();
  if (provider === "offline") {
    return mockFlashcards(text);
  }

  const prompt =
    "You are creating study flashcards from the material below. " +
    "Produce between 15 and 25 flashcards covering the key concepts, definitions, and formulas. " +
    "Include some cloze-style (fill-in-the-blank) cards. " +
    "Respond with ONLY a JSON array, no prose and no markdown fences, in exactly this shape: " +
    '[{"front": "question or prompt", "back": "answer"}]. ' +
    `\n\nMATERIAL:\n${truncate(text)}`;

  const raw =
    provider === "ollama"
      ? await ollamaChat({ model: ollamaModel(), prompt, json: true })
      : collectText(
          await getClient().messages.create({
            model: getModel(),
            max_tokens: 8000,
            messages: [{ role: "user", content: prompt }],
          }),
        );

  return validateFlashcards(parseJsonFromModel(raw));
}

// ---------------------------------------------------------------------------
// Quiz generation
// ---------------------------------------------------------------------------

function validateQuiz(parsed: unknown): QuizQuestionDraft[] {
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

export async function generateQuiz(text: string): Promise<QuizQuestionDraft[]> {
  const provider = getProvider();
  if (provider === "offline") {
    return mockQuiz(text);
  }

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

  const raw =
    provider === "ollama"
      ? await ollamaChat({ model: ollamaModel(), prompt, json: true })
      : collectText(
          await getClient().messages.create({
            model: getModel(),
            max_tokens: 8000,
            messages: [{ role: "user", content: prompt }],
          }),
        );

  return validateQuiz(parseJsonFromModel(raw));
}

// ---------------------------------------------------------------------------
// Study guide generation
// ---------------------------------------------------------------------------

function validateGuide(parsed: unknown): GuideDraft {
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

export async function generateGuide(
  text: string,
  className: string,
): Promise<GuideDraft> {
  const provider = getProvider();
  if (provider === "offline") {
    return mockGuide(text, className);
  }

  const prompt =
    `You are creating an organized study guide for the class "${className}" from the material below. ` +
    "The guide should use Markdown with clear headings, cover key terms, and highlight likely exam points. " +
    "Respond with ONLY a JSON object, no prose and no markdown fences, in exactly this shape: " +
    '{"title": "a concise guide title", "contentMd": "the full study guide in Markdown"}. ' +
    `\n\nMATERIAL:\n${truncate(text)}`;

  const raw =
    provider === "ollama"
      ? await ollamaChat({ model: ollamaModel(), prompt, json: true })
      : collectText(
          await getClient().messages.create({
            model: getModel(),
            max_tokens: 8000,
            messages: [{ role: "user", content: prompt }],
          }),
        );

  return validateGuide(parseJsonFromModel(raw));
}

// ---------------------------------------------------------------------------
// Offline generators (no AI engine, no network) — pure functions of the input
// text that use simple heuristics instead of a model. Used whenever
// isMockMode() is true. Output must always read as normal study content,
// never mention that it was generated offline.
// ---------------------------------------------------------------------------

const OFFLINE_DISTRACTORS = [
  "None of the above",
  "An unrelated concept",
  "A common misconception",
];

const DEFINITION_PATTERN =
  /^(.{2,60}?)\s+(is|are|was|were|means|refers to|is defined as)\s+(.+)$/i;

interface DefinitionMatch {
  sentence: string;
  term: string;
  verb: string;
  rest: string;
}

function matchDefinition(sentence: string): DefinitionMatch | null {
  const match = sentence.match(DEFINITION_PATTERN);
  if (!match) return null;
  return { sentence, term: match[1].trim(), verb: match[2].toLowerCase(), rest: match[3].trim() };
}

/**
 * Pick the best word in a sentence to blank out for a cloze card: prefer the
 * longest capitalized (non-sentence-initial) word, otherwise the longest
 * word over 6 characters.
 */
function pickClozeWord(sentence: string): string | null {
  const words = sentence.match(/[A-Za-z][A-Za-z'-]*/g) ?? [];
  const capitalized = words.filter(
    (w, i) => i > 0 && /^[A-Z]/.test(w) && w.length > 2,
  );
  const pool = capitalized.length > 0 ? capitalized : words.filter((w) => w.length > 6);
  if (pool.length === 0) return null;
  return pool.reduce((longest, w) => (w.length > longest.length ? w : longest), pool[0]);
}

function blankWord(sentence: string, word: string): string {
  const re = new RegExp(`\\b${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`);
  return sentence.replace(re, "_____");
}

function mockFlashcards(text: string): FlashcardDraft[] {
  const sentences = splitSentences(text);
  const cards: FlashcardDraft[] = [];
  for (const sentence of sentences) {
    if (cards.length >= 20) break;
    const def = matchDefinition(sentence);
    if (def) {
      cards.push({
        front: `What ${def.verb} ${def.term}?`,
        back: def.sentence,
      });
      continue;
    }
    const word = pickClozeWord(sentence);
    if (word) {
      cards.push({
        front: blankWord(sentence, word),
        back: `${word} (full sentence: ${sentence})`,
      });
    }
  }
  if (cards.length === 0) {
    cards.push({
      front: "No text was extracted",
      back: "Upload a .txt, .md, or typed PDF file to generate cards.",
    });
  }
  return cards;
}

function mockQuiz(text: string): QuizQuestionDraft[] {
  const sentences = splitSentences(text);
  const questions: QuizQuestionDraft[] = [];
  const usable = sentences.slice(0, 8);

  usable.forEach((sentence, index) => {
    if (questions.length >= 8) return;
    if (index % 2 === 0) {
      questions.push({
        type: "mcq",
        prompt: "Which statement is correct?",
        choices: [sentence, ...OFFLINE_DISTRACTORS],
        answer: sentence,
        explanation: "This statement comes directly from your notes.",
      });
    } else {
      questions.push({
        type: "tf",
        prompt: `True or false: ${sentence}`,
        answer: "true",
        explanation: "This statement comes directly from your notes, so it is true.",
      });
    }
  });

  // Add one short-answer fill-in-the-blank question if we can find a good term.
  for (const sentence of usable) {
    if (questions.length >= 8) break;
    const word = pickClozeWord(sentence);
    if (word) {
      questions.push({
        type: "short",
        prompt: `Fill in the blank: ${blankWord(sentence, word)}`,
        answer: word,
        explanation: `The missing word is "${word}", taken from your notes.`,
      });
      break;
    }
  }

  if (questions.length === 0) {
    questions.push({
      type: "short",
      prompt: "What should you upload to generate a quiz?",
      answer: "study material",
      explanation: "Upload a .txt, .md, or typed PDF file to generate quiz questions.",
    });
  }
  return questions;
}

function mockGuide(text: string, className: string): GuideDraft {
  const sentences = splitSentences(text);
  const bullets = sentences.length
    ? sentences.map((s) => `- ${s}`).join("\n")
    : "- No study material was provided.";

  const definitions = sentences
    .map((s) => matchDefinition(s))
    .filter((d): d is DefinitionMatch => d !== null);

  let contentMd = `# ${className} — Study Guide\n\n## Key Points\n\n${bullets}\n`;
  if (definitions.length > 0) {
    const terms = definitions
      .map((d) => `**${d.term}** — ${d.rest}`)
      .join("\n\n");
    contentMd += `\n## Key Terms\n\n${terms}\n`;
  }

  return { title: `${className} — Study Guide`, contentMd };
}
