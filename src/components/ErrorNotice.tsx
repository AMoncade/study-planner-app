export default function ErrorNotice({
  message,
  onRetry,
  className = "",
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={`flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 ${className}`}
    >
      <span className="min-w-0 break-words">{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 font-medium text-red-700 underline underline-offset-2 hover:text-red-900"
        >
          Retry
        </button>
      )}
    </div>
  );
}
