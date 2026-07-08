import Link from "next/link";

export default function TopNav() {
  return (
    <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-2xl items-center px-4">
        <Link href="/" className="text-lg font-bold tracking-tight text-gray-900">
          Study<span className="text-cyan-600">Creator</span>
        </Link>
      </div>
    </header>
  );
}
