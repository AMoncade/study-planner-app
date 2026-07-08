"use client";

import { useEffect, useState } from "react";
import Spinner from "@/components/Spinner";

interface EngineStatus {
  provider: "ollama" | "anthropic" | "offline";
  model: string;
  visionModel: string;
  ready: boolean;
  detail: string;
  installedModels?: string[];
}

/**
 * Pull a `run this command` style snippet out of a detail string so it can
 * be rendered as copyable inline code, e.g. "...run: ollama pull llama3.1".
 */
function splitCommand(detail: string): { text: string; command: string | null } {
  const match = detail.match(/^(.*?:\s*)(ollama [^.]+)\.?$/);
  if (!match) return { text: detail, command: null };
  return { text: match[1], command: match[2] };
}

export default function EngineBanner() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/engine")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("bad response"))))
      .then((data: EngineStatus) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) return null;

  if (!status) {
    return (
      <div className="mb-4 flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-500">
        <Spinner size="sm" />
        Checking AI engine…
      </div>
    );
  }

  if (status.ready) {
    return (
      <div className="mb-4 flex items-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-2.5 text-sm text-cyan-800">
        <span aria-hidden="true">✓</span>
        <span>
          AI engine: <span className="font-semibold">{status.provider}</span> ({status.model})
        </span>
      </div>
    );
  }

  const { text, command } = splitCommand(status.detail);

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
      <span aria-hidden="true">⚠</span>
      <span>{text}</span>
      {command && (
        <code className="rounded bg-amber-100 px-2 py-0.5 font-mono text-xs text-amber-900">
          {command}
        </code>
      )}
    </div>
  );
}
