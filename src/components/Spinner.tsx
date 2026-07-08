export default function Spinner({
  size = "md",
  className = "",
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const dims = size === "sm" ? "h-4 w-4 border-2" : size === "lg" ? "h-8 w-8 border-4" : "h-5 w-5 border-2";
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-cyan-600 border-t-transparent ${dims} ${className}`}
    />
  );
}
