import type { MaterialStatus } from "@/lib/types";

const STYLES: Record<MaterialStatus, string> = {
  EXTRACTED: "bg-green-100 text-green-800 border-green-200",
  FAILED: "bg-red-100 text-red-800 border-red-200",
  UPLOADED: "bg-gray-100 text-gray-700 border-gray-200",
  EXTRACTING: "bg-gray-100 text-gray-700 border-gray-200",
};

const LABELS: Record<MaterialStatus, string> = {
  EXTRACTED: "Extracted",
  FAILED: "Failed",
  UPLOADED: "Uploaded",
  EXTRACTING: "Extracting…",
};

export default function StatusBadge({
  status,
  error,
}: {
  status: MaterialStatus;
  error?: string | null;
}) {
  const badge = (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );

  if (status === "FAILED" && error) {
    return (
      <span className="group relative inline-flex">
        {badge}
        <span className="pointer-events-none absolute left-1/2 top-full z-10 mt-1 w-max max-w-[16rem] -translate-x-1/2 rounded-lg bg-black px-2 py-1 text-xs text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
          {error}
        </span>
      </span>
    );
  }

  return badge;
}
