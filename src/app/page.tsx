"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { ClassSummaryDto } from "@/lib/types";
import { apiFetch, getErrorMessage } from "@/components/api";
import Spinner from "@/components/Spinner";
import ErrorNotice from "@/components/ErrorNotice";
import EngineBanner from "@/components/EngineBanner";

export default function Home() {
  const [classes, setClasses] = useState<ClassSummaryDto[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [term, setTerm] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    apiFetch<{ classes: ClassSummaryDto[] }>("/api/classes")
      .then((data) => setClasses(data.classes))
      .catch((err) => setError(getErrorMessage(err)));
  };

  useEffect(load, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      await apiFetch<{ class: { id: string; name: string; term?: string | null } }>("/api/classes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), term: term.trim() || undefined }),
      });
      setName("");
      setTerm("");
      load();
    } catch (err) {
      setCreateError(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 sm:py-10">
      <h1 className="text-2xl font-bold text-gray-900">Your classes</h1>
      <p className="mt-1 text-sm text-gray-500">
        Upload class materials and Study Creator turns them into flashcards, practice tests, and study guides.
      </p>

      <EngineBanner />

      <form
        onSubmit={handleCreate}
        className="mt-6 flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 sm:flex-row sm:items-start"
      >
        <div className="flex flex-1 flex-col gap-3 sm:flex-row">
          <input
            type="text"
            placeholder="Class name (e.g. BIO 201)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-cyan-600 focus:outline-none focus:ring-1 focus:ring-cyan-600"
          />
          <input
            type="text"
            placeholder="Term (optional)"
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            className="min-w-0 sm:w-36 rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-cyan-600 focus:outline-none focus:ring-1 focus:ring-cyan-600"
          />
        </div>
        <button
          type="submit"
          disabled={creating || !name.trim()}
          className="flex items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {creating && <Spinner size="sm" className="border-white border-t-transparent" />}
          Add class
        </button>
      </form>
      {createError && <ErrorNotice message={createError} className="mt-3" />}

      <div className="mt-6">
        {error && <ErrorNotice message={error} onRetry={load} />}
        {!error && classes === null && (
          <div className="flex justify-center py-12">
            <Spinner size="lg" />
          </div>
        )}
        {!error && classes !== null && classes.length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">
            Add a class above, upload your notes or slides, then generate flashcards, a practice test, or a study
            guide in one tap.
          </div>
        )}
        {!error && classes !== null && classes.length > 0 && (
          <ul className="flex flex-col gap-3">
            {classes.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/classes/${c.id}`}
                  className="block rounded-xl border border-gray-200 bg-white p-4 transition hover:border-cyan-300 hover:shadow-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="truncate text-base font-semibold text-gray-900">{c.name}</h2>
                    {c.term && (
                      <span className="shrink-0 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                        {c.term}
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                    <span>{c.counts.materials} materials</span>
                    <span>{c.counts.decks} decks</span>
                    <span>{c.counts.quizzes} quizzes</span>
                    <span>{c.counts.guides} guides</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
