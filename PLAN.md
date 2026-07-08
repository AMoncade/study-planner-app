# Study Creator: Build Plan

A web app that turns your class materials (PDFs, text files, photos of notes, slides) into study guides, flashcards, and practice tests automatically. Usable on your computer and your phone from the same account, no copy-pasting back and forth.

## The one thing to accept up front

[Certain] To get good results from photos of handwritten notes and to generate quality questions, this app needs an AI model behind it. That means a Claude API key and a per-use cost, roughly 1 to 5 cents per document processed. A fully free version limited to typed PDFs with no smart question generation would be dramatically worse, so this plan assumes the paid API route. Budget expectation for a typical semester of use: a few dollars per month.

## Key decisions (made with defaults, all changeable)

| Decision | Choice | Why |
|---|---|---|
| Platform | Web app, installable on phone as a PWA | One codebase works on computer and phone. Building separate native apps would triple the work for no real gain at this stage. |
| Framework | Next.js 15 (React, TypeScript) on Vercel free tier | Free hosting, free HTTPS, works from any device anywhere. [Likely] the fastest path to something you can actually use on your phone this month. |
| AI engine | Claude API (claude-sonnet-5) | Reads PDFs natively, does OCR on photos including handwriting, and generates flashcards, quizzes, and summaries in one pipeline. |
| Database | Postgres on Neon or Supabase free tier | Stores your classes, materials, generated cards, and review history so both devices see the same data. |
| File storage | Supabase Storage or Vercel Blob free tier | Holds the original uploaded files. |
| Auth | Email magic link, single user to start | You need login so your phone and computer share data, but no need for a full account system for one person. |
| Phone access | PWA install (Add to Home Screen) | Looks and behaves like a native app, gets its own icon, works offline for reviewing already-downloaded cards. A "connector" or separate mobile app is not needed. |

## What the app does, end to end

1. **Upload**: Drag files in from computer, or on the phone take a photo directly or share a file to the app. Group uploads by class (for example "BIO 201", "Stats").
2. **Extract**: The app sends each file to Claude. PDFs and text files are read directly, images go through vision OCR. Output is clean structured text per document, stored in the database. You never do this step manually again.
3. **Generate** (per class or per selected set of materials, one button each):
   - **Study guide**: organized outline of key concepts, definitions, formulas, and likely exam points. Exportable as Markdown or PDF.
   - **Flashcards**: question and answer pairs, plus cloze deletions for definitions and formulas.
   - **Practice test**: multiple choice, true/false, and short answer questions with an answer key and explanations.
4. **Study**:
   - Flashcard review with SM-2 spaced repetition (Anki-style scheduling), so the app decides what you review each day.
   - Take practice tests in-app with instant grading and explanations for wrong answers.
   - Edit or delete any generated card or question, because AI output will occasionally be wrong and you need a one-tap fix.
5. **Export**: Download flashcards as a TSV/CSV file importable into Anki, and study guides as Markdown/PDF, so nothing is locked in.

## Data model (core tables)

- `classes`: id, name, term
- `materials`: id, class_id, filename, file_url, extracted_text, status (uploaded / extracted / failed)
- `decks` and `cards`: card front, back, source material reference, SM-2 fields (ease, interval, due_date)
- `quizzes` and `questions`: type, prompt, choices, answer, explanation
- `reviews`: card_id, grade, timestamp (drives the spaced repetition schedule)

## Build phases

**Phase 1, core pipeline (the automation you asked for):**
Next.js project scaffold, database schema, file upload, Claude extraction pipeline, flashcard generation, basic flashcard review screen. At the end of this phase the back-and-forth is already gone: upload, tap generate, study.

**Phase 2, study depth:**
Spaced repetition scheduling, practice test generation and in-app grading, study guide generation and export, card editing.

**Phase 3, phone polish and deploy:**
PWA manifest and service worker (installable icon, offline card review), camera capture and share-target on mobile, deploy to Vercel with Neon database, magic-link login.

**Phase 4, quality passes (optional, after real use):**
Regenerate weak cards, "focus on what I got wrong" test mode, per-class progress stats, multi-user support if you ever want to share it.

## Risks and honest caveats

- [Certain] AI-generated cards will sometimes contain errors or miss what your professor emphasizes. The edit and delete controls in Phase 2 exist precisely for this, and cards always link back to the source document so you can verify.
- [Likely] Very large PDFs (200+ page textbooks) will need chunking and will cost more per run. The plan handles this by processing per-chapter or per-upload rather than whole-book.
- [Guessing] Your school may have academic integrity rules about uploading course materials to third-party AI services. Worth a 2-minute check of your syllabus before uploading anything exam-related.

## What you need to provide before Phase 3 (deploy)

1. An Anthropic API key from console.anthropic.com (paid, usage-based).
2. A free Vercel account and a free Neon or Supabase account.

Phases 1 and 2 can be built and tested locally in this repo without any of those.
