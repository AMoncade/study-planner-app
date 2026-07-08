import { NextResponse } from "next/server";
import { marked } from "marked";
import prisma from "@/lib/db";

export const runtime = "nodejs";

function sanitizeFilename(name: string): string {
  const cleaned = name.replace(/[^A-Za-z0-9._-]/g, "_").trim();
  return cleaned.length > 0 ? cleaned : "study-guide";
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const guide = await prisma.studyGuide.findUnique({ where: { id } });
  if (!guide) {
    return NextResponse.json({ error: "Guide not found." }, { status: 404 });
  }

  const bodyHtml = await marked.parse(guide.contentMd);
  const safeTitle = escapeHtml(guide.title);

  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${safeTitle}</title>
<style>
  :root {
    color-scheme: light;
  }
  * {
    box-sizing: border-box;
  }
  body {
    margin: 0;
    padding: 1.5rem 1.25rem 4rem;
    background: #ffffff;
    color: #1a1a1a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.65;
    font-size: 17px;
    -webkit-text-size-adjust: 100%;
  }
  main {
    max-width: 720px;
    margin: 0 auto;
  }
  h1, h2, h3, h4 {
    color: #0891b2;
    line-height: 1.3;
    margin-top: 2em;
    margin-bottom: 0.5em;
  }
  h1 {
    font-size: 1.7rem;
    margin-top: 0;
    border-bottom: 2px solid #cffafe;
    padding-bottom: 0.4em;
  }
  h2 {
    font-size: 1.35rem;
  }
  h3 {
    font-size: 1.15rem;
  }
  p, li {
    margin: 0.6em 0;
  }
  ul, ol {
    padding-left: 1.4em;
  }
  a {
    color: #0891b2;
  }
  strong {
    color: #0e7490;
  }
  code {
    background: #f0fdff;
    border-radius: 4px;
    padding: 0.15em 0.4em;
    font-size: 0.9em;
    word-break: break-word;
  }
  pre {
    background: #f0fdff;
    border-radius: 8px;
    padding: 0.9em;
    overflow-x: auto;
  }
  pre code {
    background: none;
    padding: 0;
  }
  blockquote {
    margin: 1em 0;
    padding: 0.3em 1em;
    border-left: 4px solid #67e8f9;
    color: #444;
    background: #f7feff;
  }
  hr {
    border: none;
    border-top: 1px solid #e5e5e5;
    margin: 2em 0;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95em;
  }
  th, td {
    border: 1px solid #e5e5e5;
    padding: 0.5em 0.6em;
    text-align: left;
  }
  th {
    background: #f0fdff;
  }
  img {
    max-width: 100%;
    height: auto;
  }
  @media (max-width: 360px) {
    body {
      padding: 1rem 0.85rem 3rem;
      font-size: 16px;
    }
    h1 {
      font-size: 1.4rem;
    }
    h2 {
      font-size: 1.2rem;
    }
  }
</style>
</head>
<body>
<main>
${bodyHtml}
</main>
</body>
</html>
`;

  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Disposition": `attachment; filename="${sanitizeFilename(guide.title)}.html"`,
    },
  });
}
