"use client";

import { useState } from "react";
import Spinner from "@/components/Spinner";

export default function ConfirmButton({
  onConfirm,
  confirmMessage,
  children,
  className = "",
  busyLabel = "Working…",
}: {
  onConfirm: () => Promise<void> | void;
  confirmMessage: string;
  children: React.ReactNode;
  className?: string;
  busyLabel?: string;
}) {
  const [busy, setBusy] = useState(false);

  const handleClick = async () => {
    if (typeof window !== "undefined" && !window.confirm(confirmMessage)) return;
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  };

  return (
    <button type="button" onClick={handleClick} disabled={busy} className={className}>
      {busy ? (
        <span className="inline-flex items-center gap-2">
          <Spinner size="sm" />
          {busyLabel}
        </span>
      ) : (
        children
      )}
    </button>
  );
}
