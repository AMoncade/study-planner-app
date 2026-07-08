import type {
  MaterialStatus,
  MaterialDto,
  CardDto,
  QuestionType,
} from "@/lib/types";

interface MaterialRow {
  id: string;
  filename: string;
  mimeType: string;
  status: string;
  error: string | null;
  createdAt: Date;
}

export function toMaterialDto(m: MaterialRow): MaterialDto {
  return {
    id: m.id,
    filename: m.filename,
    mimeType: m.mimeType,
    status: m.status as MaterialStatus,
    error: m.error,
    createdAt: m.createdAt.toISOString(),
  };
}

interface CardRow {
  id: string;
  front: string;
  back: string;
  dueAt: Date;
  intervalDays: number;
  ease: number;
  reps: number;
}

export function toCardDto(c: CardRow): CardDto {
  return {
    id: c.id,
    front: c.front,
    back: c.back,
    dueAt: c.dueAt.toISOString(),
    intervalDays: c.intervalDays,
    ease: c.ease,
    reps: c.reps,
  };
}

export function parseQuestionType(type: string): QuestionType {
  return type as QuestionType;
}
