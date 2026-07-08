"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { GradeResultDto, QuizDetailDto } from "@/lib/types";
import { apiFetch, getErrorMessage } from "@/components/api";
import Spinner from "@/components/Spinner";
import ErrorNotice from "@/components/ErrorNotice";

type GradeResponse = { score: number; total: number; results: GradeResultDto[] };

export default function QuizPage() {
  const params = useParams<{ id: string }>();
  const quizId = params.id as string;

  const [quiz, setQuiz] = useState<QuizDetailDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<GradeResponse | null>(null);

  const load = () => {
    setError(null);
    apiFetch<{ quiz: QuizDetailDto }>(`/api/quizzes/${quizId}`)
      .then((data) => setQuiz(data.quiz))
      .catch((err) => setError(getErrorMessage(err)));
  };

  useEffect(load, [quizId]);

  const setAnswer = (questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await apiFetch<GradeResponse>(`/api/quizzes/${quizId}/grade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers }),
      });
      setResult(res);
    } catch (err) {
      setSubmitError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetake = () => {
    setResult(null);
    setAnswers({});
    setSubmitError(null);
  };

  const resultFor = (questionId: string) => result?.results.find((r) => r.questionId === questionId);

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-6">
        <ErrorNotice message={error} onRetry={load} />
      </main>
    );
  }

  if (!quiz) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-12">
        <div className="flex justify-center">
          <Spinner size="lg" />
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 sm:py-10">
      <h1 className="truncate text-2xl font-bold text-gray-900">{quiz.title}</h1>

      {result && (
        <div className="mt-4 rounded-xl border border-cyan-200 bg-cyan-50 p-4 text-center">
          <p className="text-lg font-bold text-cyan-800">
            Score: {result.score} / {result.total}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        {quiz.questions.map((q, i) => {
          const r = resultFor(q.id);
          const graded = !!result;
          const borderClass = graded ? (r?.correct ? "border-green-400 bg-green-50" : "border-red-400 bg-red-50") : "border-gray-200 bg-white";
          return (
            <fieldset
              key={q.id}
              disabled={graded}
              className={`rounded-xl border p-4 ${borderClass}`}
            >
              <legend className="mb-2 text-sm font-semibold text-gray-900">
                {i + 1}. {q.prompt}
              </legend>

              {q.type === "mcq" && (
                <div className="flex flex-col gap-2">
                  {(q.choices ?? []).map((choice) => (
                    <label key={choice} className="flex items-center gap-2 text-sm text-gray-700">
                      <input
                        type="radio"
                        name={q.id}
                        value={choice}
                        checked={answers[q.id] === choice}
                        onChange={() => setAnswer(q.id, choice)}
                        className="h-4 w-4 accent-cyan-600"
                      />
                      {choice}
                    </label>
                  ))}
                </div>
              )}

              {q.type === "tf" && (
                <div className="flex gap-4">
                  {["True", "False"].map((choice) => (
                    <label key={choice} className="flex items-center gap-2 text-sm text-gray-700">
                      <input
                        type="radio"
                        name={q.id}
                        value={choice}
                        checked={answers[q.id] === choice}
                        onChange={() => setAnswer(q.id, choice)}
                        className="h-4 w-4 accent-cyan-600"
                      />
                      {choice}
                    </label>
                  ))}
                </div>
              )}

              {q.type === "short" && (
                <input
                  type="text"
                  value={answers[q.id] ?? ""}
                  onChange={(e) => setAnswer(q.id, e.target.value)}
                  placeholder="Your answer"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-cyan-600 focus:outline-none focus:ring-1 focus:ring-cyan-600 disabled:bg-gray-100"
                />
              )}

              {graded && r && (
                <div className="mt-3 border-t border-black/10 pt-2 text-sm">
                  <p className="text-gray-700">
                    <span className="font-medium">Your answer:</span> {r.yourAnswer || "(no answer)"}
                  </p>
                  {!r.correct && (
                    <p className="text-gray-700">
                      <span className="font-medium">Correct answer:</span> {r.correctAnswer}
                    </p>
                  )}
                  {r.explanation && <p className="mt-1 text-gray-500">{r.explanation}</p>}
                </div>
              )}
            </fieldset>
          );
        })}

        {submitError && <ErrorNotice message={submitError} />}

        {!result ? (
          <button
            type="submit"
            disabled={submitting}
            className="flex items-center justify-center gap-2 rounded-xl bg-cyan-600 py-3.5 text-base font-semibold text-white hover:bg-cyan-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting && <Spinner size="sm" className="border-white border-t-transparent" />}
            Submit
          </button>
        ) : (
          <button
            type="button"
            onClick={handleRetake}
            className="rounded-xl border border-cyan-600 py-3.5 text-base font-semibold text-cyan-700 hover:bg-cyan-50"
          >
            Retake
          </button>
        )}
      </form>
    </main>
  );
}
