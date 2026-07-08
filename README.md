# Study Creator

Turn your class materials (PDFs, text files, photos of notes) into study guides, flashcards, and practice tests automatically. Works on your computer and your phone.

## What it does

1. Create a class (e.g. "BIO 201").
2. Upload materials: PDFs, `.txt`/`.md` files, or photos of handwritten notes.
3. The app extracts the content once (AI handles OCR and handwriting).
4. One tap generates a **flashcard deck**, a **practice test**, or a **study guide**.
5. Study: review flashcards with Anki-style spaced repetition, take graded quizzes with explanations, read/download the guide. Export cards to Anki (TSV).

## Run it locally

```bash
npm install
npx prisma db push      # creates the SQLite database
npm run dev             # http://localhost:3000
```

By default it runs in **mock mode** (`MOCK_AI=1` in `.env`), so you can click through the whole app with no API key. Mock mode produces placeholder cards/quizzes from your text so you can see how everything works.

## Turn on real AI

To get real extraction (including handwriting OCR) and quality question generation, set an [Anthropic API key](https://console.anthropic.com):

```bash
# .env
ANTHROPIC_API_KEY="sk-ant-..."
ANTHROPIC_MODEL="claude-sonnet-5"   # optional, this is the default
MOCK_AI="0"
```

Cost is usage-based, roughly 1–5 cents per document.

## Use it on your phone

- **Now (local network):** run `npm run dev` and open your computer's LAN IP (e.g. `http://192.168.1.x:3000`) in your phone's browser while on the same Wi-Fi.
- **Anywhere (deploy):** deploy to Vercel and switch `DATABASE_URL` to a hosted Postgres (Neon/Supabase free tier). Then "Add to Home Screen" on your phone. See `PLAN.md` (Phase 3) for the deployment steps.

## Tech

Next.js 15 (App Router) · TypeScript · Tailwind CSS · Prisma + SQLite · Anthropic Claude API.

## Project layout

- `src/lib/ai.ts` — extraction + generation (mock + real Claude)
- `src/lib/srs.ts` — SM-2 spaced-repetition scheduler
- `src/app/api/**` — REST endpoints
- `src/app/**` — dashboard, class, deck, quiz, guide pages
- `prisma/schema.prisma` — data model

See `PLAN.md` for the full roadmap.
