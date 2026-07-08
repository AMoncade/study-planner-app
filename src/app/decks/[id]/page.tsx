"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import type { CardDto, Grade } from "@/lib/types";
import { apiFetch, getErrorMessage } from "@/components/api";
import Spinner from "@/components/Spinner";
import ErrorNotice from "@/components/ErrorNotice";
import ConfirmButton from "@/components/ConfirmButton";

type DeckDto = { id: string; title: string; classId: string; cards: CardDto[] };
type Mode = "review" | "browse";

const GRADE_STYLES: Record<Grade, string> = {
  again: "bg-red-600 hover:bg-red-700",
  hard: "bg-orange-500 hover:bg-orange-600",
  good: "bg-green-600 hover:bg-green-700",
  easy: "bg-cyan-600 hover:bg-cyan-700",
};

const GRADE_LABELS: Record<Grade, string> = {
  again: "Again",
  hard: "Hard",
  good: "Good",
  easy: "Easy",
};

function formatDueDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffHrs = diffMs / (1000 * 60 * 60);
  if (diffHrs < 1) return "soon";
  if (diffHrs < 24) return `in ${Math.round(diffHrs)}h`;
  const diffDays = Math.round(diffHrs / 24);
  if (diffDays === 1) return "tomorrow";
  if (diffDays < 7) return `in ${diffDays} days`;
  return d.toLocaleDateString();
}

export default function DeckPage() {
  const params = useParams<{ id: string }>();
  const deckId = params.id as string;

  const [deck, setDeck] = useState<DeckDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("review");

  // Review mode state
  const [queue, setQueue] = useState<CardDto[] | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewedCount, setReviewedCount] = useState(0);

  // Browse mode state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftFront, setDraftFront] = useState("");
  const [draftBack, setDraftBack] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [browseError, setBrowseError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    Promise.all([
      apiFetch<{ deck: DeckDto }>(`/api/decks/${deckId}`),
      apiFetch<{ cards: CardDto[] }>(`/api/decks/${deckId}/due`),
    ])
      .then(([deckRes, dueRes]) => {
        setDeck(deckRes.deck);
        setQueue(dueRes.cards);
        setReviewedCount(0);
        setRevealed(false);
      })
      .catch((err) => setError(getErrorMessage(err)));
  };

  useEffect(load, [deckId]);

  const nextDue = useMemo(() => {
    if (!deck) return null;
    const future = deck.cards.filter((c) => new Date(c.dueAt).getTime() > Date.now());
    if (future.length === 0) return null;
    future.sort((a, b) => new Date(a.dueAt).getTime() - new Date(b.dueAt).getTime());
    const soonest = future[0];
    const soonestCount = future.filter((c) => c.dueAt === soonest.dueAt).length;
    return { at: soonest.dueAt, count: soonestCount };
  }, [deck]);

  const currentCard = queue && queue.length > 0 ? queue[0] : null;

  const handleGrade = async (grade: Grade) => {
    if (!currentCard) return;
    setReviewing(true);
    setReviewError(null);
    try {
      await apiFetch<{ card: CardDto }>(`/api/cards/${currentCard.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ grade }),
      });
      setQueue((prev) => (prev ? prev.slice(1) : prev));
      setReviewedCount((n) => n + 1);
      setRevealed(false);
    } catch (err) {
      setReviewError(getErrorMessage(err));
    } finally {
      setReviewing(false);
    }
  };

  const startEdit = (card: CardDto) => {
    setEditingId(card.id);
    setDraftFront(card.front);
    setDraftBack(card.back);
    setBrowseError(null);
  };

  const saveEdit = async (cardId: string) => {
    setSavingEdit(true);
    setBrowseError(null);
    try {
      const res = await apiFetch<{ card: CardDto }>(`/api/cards/${cardId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ front: draftFront, back: draftBack }),
      });
      setDeck((prev) =>
        prev ? { ...prev, cards: prev.cards.map((c) => (c.id === cardId ? res.card : c)) } : prev
      );
      setEditingId(null);
    } catch (err) {
      setBrowseError(getErrorMessage(err));
    } finally {
      setSavingEdit(false);
    }
  };

  const deleteCard = async (cardId: string) => {
    await apiFetch<{ ok: true }>(`/api/cards/${cardId}`, { method: "DELETE" });
    setDeck((prev) => (prev ? { ...prev, cards: prev.cards.filter((c) => c.id !== cardId) } : prev));
    setQueue((prev) => (prev ? prev.filter((c) => c.id !== cardId) : prev));
  };

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-6">
        <ErrorNotice message={error} onRetry={load} />
      </main>
    );
  }

  if (!deck || !queue) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-12">
        <div className="flex justify-center">
          <Spinner size="lg" />
        </div>
      </main>
    );
  }

  const totalDueThisSession = reviewedCount + queue.length;

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 sm:py-10">
      <h1 className="truncate text-2xl font-bold text-gray-900">{deck.title}</h1>

      <div className="mt-4 flex gap-2 rounded-lg bg-gray-100 p-1">
        <button
          type="button"
          onClick={() => setMode("review")}
          className={`flex-1 rounded-md py-2 text-sm font-semibold transition ${
            mode === "review" ? "bg-white text-cyan-700 shadow-sm" : "text-gray-500"
          }`}
        >
          Review
        </button>
        <button
          type="button"
          onClick={() => setMode("browse")}
          className={`flex-1 rounded-md py-2 text-sm font-semibold transition ${
            mode === "browse" ? "bg-white text-cyan-700 shadow-sm" : "text-gray-500"
          }`}
        >
          Browse
        </button>
      </div>

      {mode === "review" && (
        <div className="mt-6">
          {reviewError && <ErrorNotice message={reviewError} className="mb-4" />}
          {currentCard ? (
            <>
              <p className="mb-2 text-center text-xs font-medium text-gray-400">
                {reviewedCount + 1} of {totalDueThisSession}
              </p>
              <div className="min-h-56 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <p className="text-center text-lg font-medium text-gray-900">{currentCard.front}</p>
                {revealed && (
                  <>
                    <hr className="my-4 border-gray-200" />
                    <p className="text-center text-base text-gray-700">{currentCard.back}</p>
                  </>
                )}
              </div>

              {!revealed ? (
                <button
                  type="button"
                  onClick={() => setRevealed(true)}
                  className="mt-4 w-full rounded-xl bg-cyan-600 py-4 text-base font-semibold text-white hover:bg-cyan-700"
                >
                  Show answer
                </button>
              ) : (
                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {(["again", "hard", "good", "easy"] as Grade[]).map((g) => (
                    <button
                      key={g}
                      type="button"
                      disabled={reviewing}
                      onClick={() => handleGrade(g)}
                      className={`rounded-xl py-4 text-sm font-semibold text-white transition disabled:opacity-50 ${GRADE_STYLES[g]}`}
                    >
                      {GRADE_LABELS[g]}
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="rounded-2xl border border-gray-200 bg-white p-8 text-center">
              <p className="text-lg font-semibold text-gray-900">All caught up!</p>
              {nextDue ? (
                <p className="mt-2 text-sm text-gray-500">
                  {nextDue.count} card{nextDue.count > 1 ? "s" : ""} due {formatDueDate(nextDue.at)}.
                </p>
              ) : (
                <p className="mt-2 text-sm text-gray-500">No more cards scheduled.</p>
              )}
            </div>
          )}
        </div>
      )}

      {mode === "browse" && (
        <div className="mt-6">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm text-gray-500">{deck.cards.length} cards</p>
            <a
              href={`/api/decks/${deckId}/export.tsv`}
              className="rounded-lg border border-cyan-600 px-3 py-1.5 text-xs font-semibold text-cyan-700 hover:bg-cyan-50"
            >
              Export TSV (Anki)
            </a>
          </div>
          {browseError && <ErrorNotice message={browseError} className="mb-3" />}
          <ul className="flex flex-col gap-2">
            {deck.cards.map((card) => (
              <li key={card.id} className="rounded-xl border border-gray-200 bg-white p-3">
                {editingId === card.id ? (
                  <div className="flex flex-col gap-2">
                    <label className="text-xs font-medium text-gray-500">Front</label>
                    <textarea
                      value={draftFront}
                      onChange={(e) => setDraftFront(e.target.value)}
                      rows={2}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-cyan-600 focus:outline-none focus:ring-1 focus:ring-cyan-600"
                    />
                    <label className="text-xs font-medium text-gray-500">Back</label>
                    <textarea
                      value={draftBack}
                      onChange={(e) => setDraftBack(e.target.value)}
                      rows={2}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-cyan-600 focus:outline-none focus:ring-1 focus:ring-cyan-600"
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={savingEdit}
                        onClick={() => saveEdit(card.id)}
                        className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-cyan-600 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
                      >
                        {savingEdit && <Spinner size="sm" className="border-white border-t-transparent" />}
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <button type="button" onClick={() => startEdit(card)} className="block w-full text-left">
                      <p className="text-sm font-medium text-gray-900">{card.front}</p>
                      <p className="mt-1 text-sm text-gray-500">{card.back}</p>
                    </button>
                    <div className="mt-2 flex justify-end">
                      <ConfirmButton
                        onConfirm={() => deleteCard(card.id)}
                        confirmMessage="Delete this card?"
                        className="text-xs font-medium text-red-500 hover:text-red-700"
                      >
                        Delete
                      </ConfirmButton>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
