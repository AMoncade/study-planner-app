"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import type { ClassDetailDto, MaterialDto } from "@/lib/types";
import { apiFetch, getErrorMessage } from "@/components/api";
import Spinner from "@/components/Spinner";
import ErrorNotice from "@/components/ErrorNotice";
import StatusBadge from "@/components/StatusBadge";
import ConfirmButton from "@/components/ConfirmButton";

type GenerateType = "deck" | "quiz" | "guide";

const ACCEPT = ".pdf,.txt,.md,image/*";

export default function ClassDetailPage() {
  const params = useParams<{ id: string }>();
  const classId = params.id as string;
  const router = useRouter();

  const [detail, setDetail] = useState<ClassDetailDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [generating, setGenerating] = useState<GenerateType | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    apiFetch<{ class: ClassDetailDto }>(`/api/classes/${classId}`)
      .then((data) => setDetail(data.class))
      .catch((err) => setError(getErrorMessage(err)));
  };

  useEffect(load, [classId]);

  const addFiles = (files: FileList | File[]) => {
    setStagedFiles((prev) => [...prev, ...Array.from(files)]);
  };

  const handleUpload = async () => {
    if (stagedFiles.length === 0) return;
    setUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      for (const file of stagedFiles) formData.append("files", file);
      await apiFetch<{ materials: MaterialDto[] }>(`/api/classes/${classId}/materials`, {
        method: "POST",
        body: formData,
      });
      setStagedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      load();
    } catch (err) {
      setUploadError(getErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const toggleMaterial = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleGenerate = async (type: GenerateType) => {
    setGenerating(type);
    setGenerateError(null);
    try {
      const body: { type: GenerateType; materialIds?: string[] } = { type };
      if (selected.size > 0) body.materialIds = Array.from(selected);
      const result = await apiFetch<{
        deck?: { id: string; title: string };
        quiz?: { id: string; title: string };
        guide?: { id: string; title: string };
      }>(`/api/classes/${classId}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (result.deck) router.push(`/decks/${result.deck.id}`);
      else if (result.quiz) router.push(`/quizzes/${result.quiz.id}`);
      else if (result.guide) router.push(`/guides/${result.guide.id}`);
      else load();
    } catch (err) {
      setGenerateError(getErrorMessage(err));
    } finally {
      setGenerating(null);
    }
  };

  const handleDeleteClass = async () => {
    await apiFetch<{ ok: true }>(`/api/classes/${classId}`, { method: "DELETE" });
    router.push("/");
  };

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-6">
        <ErrorNotice message={error} onRetry={load} />
      </main>
    );
  }

  if (!detail) {
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
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold text-gray-900">{detail.name}</h1>
          {detail.term && <p className="text-sm text-gray-500">{detail.term}</p>}
        </div>
        <ConfirmButton
          onConfirm={handleDeleteClass}
          confirmMessage={`Delete "${detail.name}" and everything in it? This can't be undone.`}
          busyLabel="Deleting…"
          className="shrink-0 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
        >
          Delete class
        </ConfirmButton>
      </div>

      {/* Materials */}
      <section className="mt-8">
        <h2 className="text-base font-semibold text-gray-900">Materials</h2>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`mt-3 flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition ${
            dragOver ? "border-cyan-500 bg-cyan-50" : "border-gray-300 bg-white hover:border-cyan-400"
          }`}
        >
          <p className="text-sm font-medium text-gray-700">Drop files here or tap to choose</p>
          <p className="text-xs text-gray-400">PDF, TXT, Markdown, or photos of notes</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.length) addFiles(e.target.files);
            }}
          />
        </div>

        {stagedFiles.length > 0 && (
          <div className="mt-3 rounded-xl border border-gray-200 bg-white p-3">
            <ul className="flex flex-col gap-1 text-sm text-gray-700">
              {stagedFiles.map((f, i) => (
                <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-2">
                  <span className="truncate">{f.name}</span>
                  <button
                    type="button"
                    onClick={() => setStagedFiles((prev) => prev.filter((_, idx) => idx !== i))}
                    className="shrink-0 text-xs font-medium text-gray-400 hover:text-red-600"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={handleUpload}
              disabled={uploading}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {uploading && <Spinner size="sm" className="border-white border-t-transparent" />}
              {uploading ? "Uploading…" : `Upload ${stagedFiles.length} file${stagedFiles.length > 1 ? "s" : ""}`}
            </button>
          </div>
        )}
        {uploadError && <ErrorNotice message={uploadError} className="mt-3" />}

        {detail.materials.length > 0 && (
          <ul className="mt-3 flex flex-col gap-2">
            {detail.materials.map((m) => (
              <li
                key={m.id}
                className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-3 py-2.5"
              >
                <input
                  type="checkbox"
                  checked={selected.has(m.id)}
                  onChange={() => toggleMaterial(m.id)}
                  className="h-5 w-5 shrink-0 accent-cyan-600"
                  aria-label={`Select ${m.filename} for generation`}
                />
                <span className="min-w-0 flex-1 truncate text-sm text-gray-800">{m.filename}</span>
                <StatusBadge status={m.status} error={m.error} />
              </li>
            ))}
          </ul>
        )}
        {detail.materials.length > 0 && (
          <p className="mt-2 text-xs text-gray-400">
            {selected.size > 0
              ? `${selected.size} selected for generation`
              : "None selected — generation will use all materials"}
          </p>
        )}
      </section>

      {/* Generate */}
      <section className="mt-8">
        <h2 className="text-base font-semibold text-gray-900">Generate</h2>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
          {(
            [
              ["deck", "Flashcard deck"],
              ["quiz", "Practice test"],
              ["guide", "Study guide"],
            ] as [GenerateType, string][]
          ).map(([type, label]) => (
            <button
              key={type}
              type="button"
              onClick={() => handleGenerate(type)}
              disabled={generating !== null || detail.materials.length === 0}
              className="flex items-center justify-center gap-2 rounded-lg border border-cyan-600 bg-white px-4 py-3 text-sm font-semibold text-cyan-700 transition hover:bg-cyan-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {generating === type && <Spinner size="sm" />}
              {label}
            </button>
          ))}
        </div>
        {detail.materials.length === 0 && (
          <p className="mt-2 text-xs text-gray-400">Upload a material before generating.</p>
        )}
        {generateError && <ErrorNotice message={generateError} className="mt-3" />}
      </section>

      {/* Decks */}
      <section className="mt-8">
        <h2 className="text-base font-semibold text-gray-900">Flashcard decks</h2>
        {detail.decks.length === 0 ? (
          <p className="mt-2 text-sm text-gray-400">None yet.</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-2">
            {detail.decks.map((d) => (
              <li key={d.id}>
                <Link
                  href={`/decks/${d.id}`}
                  className="flex items-center justify-between gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 hover:border-cyan-300 hover:shadow-sm"
                >
                  <span className="truncate text-sm font-medium text-gray-800">{d.title}</span>
                  <span className="flex shrink-0 items-center gap-2 text-xs text-gray-500">
                    {d.cardCount} cards
                    {d.dueCount > 0 && (
                      <span className="rounded-full bg-cyan-100 px-2 py-0.5 font-semibold text-cyan-700">
                        {d.dueCount} due
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Quizzes */}
      <section className="mt-8">
        <h2 className="text-base font-semibold text-gray-900">Practice tests</h2>
        {detail.quizzes.length === 0 ? (
          <p className="mt-2 text-sm text-gray-400">None yet.</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-2">
            {detail.quizzes.map((q) => (
              <li key={q.id}>
                <Link
                  href={`/quizzes/${q.id}`}
                  className="flex items-center justify-between gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 hover:border-cyan-300 hover:shadow-sm"
                >
                  <span className="truncate text-sm font-medium text-gray-800">{q.title}</span>
                  <span className="shrink-0 text-xs text-gray-500">{q.questionCount} questions</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Guides */}
      <section className="mt-8 mb-10">
        <h2 className="text-base font-semibold text-gray-900">Study guides</h2>
        {detail.guides.length === 0 ? (
          <p className="mt-2 text-sm text-gray-400">None yet.</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-2">
            {detail.guides.map((g) => (
              <li key={g.id}>
                <Link
                  href={`/guides/${g.id}`}
                  className="block truncate rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-800 hover:border-cyan-300 hover:shadow-sm"
                >
                  {g.title}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
