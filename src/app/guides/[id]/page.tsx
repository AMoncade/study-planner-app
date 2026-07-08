"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import { apiFetch, getErrorMessage } from "@/components/api";
import Spinner from "@/components/Spinner";
import ErrorNotice from "@/components/ErrorNotice";

type GuideDto = { id: string; title: string; contentMd: string };

const markdownComponents: Components = {
  h1: ({ children }) => <h1 className="mb-3 mt-6 text-2xl font-bold text-gray-900 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-6 text-xl font-bold text-gray-900 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-2 mt-5 text-lg font-semibold text-gray-900">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-1 mt-4 text-base font-semibold text-gray-900">{children}</h4>,
  p: ({ children }) => <p className="my-3 text-sm leading-relaxed text-gray-700">{children}</p>,
  ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-6 text-sm text-gray-700">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-6 text-sm text-gray-700">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-cyan-700 underline underline-offset-2">
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-4 border-cyan-300 pl-4 text-sm italic text-gray-600">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-6 border-gray-200" />,
  code: ({ children, className }) => {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code className={`block whitespace-pre-wrap font-mono text-xs ${className ?? ""}`}>{children}</code>
      );
    }
    return (
      <code className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-800">{children}</code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-xl border border-gray-200 bg-gray-50 p-3">{children}</pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-gray-200 bg-gray-50 px-2 py-1 text-left font-semibold text-gray-700">
      {children}
    </th>
  ),
  td: ({ children }) => <td className="border border-gray-200 px-2 py-1 text-gray-700">{children}</td>,
};

export default function GuidePage() {
  const params = useParams<{ id: string }>();
  const guideId = params.id as string;

  const [guide, setGuide] = useState<GuideDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    apiFetch<{ guide: GuideDto }>(`/api/guides/${guideId}`)
      .then((data) => setGuide(data.guide))
      .catch((err) => setError(getErrorMessage(err)));
  };

  useEffect(load, [guideId]);

  const handleDownload = () => {
    if (!guide) return;
    const blob = new Blob([guide.contentMd], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${guide.title.replace(/[^a-z0-9-_ ]/gi, "").trim() || "study-guide"}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-6">
        <ErrorNotice message={error} onRetry={load} />
      </main>
    );
  }

  if (!guide) {
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <h1 className="min-w-0 truncate text-2xl font-bold text-gray-900">{guide.title}</h1>
        <div className="flex shrink-0 flex-wrap gap-2">
          <a
            href={`/api/guides/${guideId}/export.html`}
            download
            className="rounded-lg bg-cyan-600 px-3 py-2 text-center text-sm font-semibold text-white hover:bg-cyan-700"
          >
            Download for phone (HTML)
          </a>
          <button
            type="button"
            onClick={handleDownload}
            className="rounded-lg border border-cyan-600 px-3 py-2 text-sm font-semibold text-cyan-700 hover:bg-cyan-50"
          >
            Download .md
          </button>
        </div>
      </div>
      <div className="mt-6 rounded-xl border border-gray-200 bg-white p-5">
        <ReactMarkdown components={markdownComponents}>{guide.contentMd}</ReactMarkdown>
      </div>
    </main>
  );
}
