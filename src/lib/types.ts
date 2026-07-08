export type MaterialStatus = "UPLOADED" | "EXTRACTING" | "EXTRACTED" | "FAILED";
export type Grade = "again" | "hard" | "good" | "easy";
export type QuestionType = "mcq" | "tf" | "short";

export interface MaterialDto {
  id: string;
  filename: string;
  mimeType: string;
  status: MaterialStatus;
  error?: string | null;
  createdAt: string;
}

export interface CardDto {
  id: string;
  front: string;
  back: string;
  dueAt: string;
  intervalDays: number;
  ease: number;
  reps: number;
}

export interface DeckSummaryDto {
  id: string;
  title: string;
  cardCount: number;
  dueCount: number;
  createdAt: string;
}

export interface QuizSummaryDto {
  id: string;
  title: string;
  questionCount: number;
  createdAt: string;
}

export interface GuideSummaryDto {
  id: string;
  title: string;
  createdAt: string;
}

export interface ClassSummaryDto {
  id: string;
  name: string;
  term?: string | null;
  counts: { materials: number; decks: number; quizzes: number; guides: number };
}

export interface ClassDetailDto {
  id: string;
  name: string;
  term?: string | null;
  materials: MaterialDto[];
  decks: DeckSummaryDto[];
  quizzes: QuizSummaryDto[];
  guides: GuideSummaryDto[];
}

export interface QuizQuestionDto {
  id: string;
  type: QuestionType;
  prompt: string;
  choices?: string[];
}

export interface QuizDetailDto {
  id: string;
  title: string;
  questions: QuizQuestionDto[];
}

export interface GradeResultDto {
  questionId: string;
  correct: boolean;
  correctAnswer: string;
  explanation?: string | null;
  yourAnswer: string;
}
