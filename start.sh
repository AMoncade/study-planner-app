#!/usr/bin/env bash
# One-command launcher for Study Creator.
# Just double-click this file (or run `./start.sh` in a terminal) and open
# http://localhost:3000 in your browser. No API key, no cloud, no setup.
set -e

cd "$(dirname "$0")"

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies (first run only, this can take a minute)..."
  npm install
fi

if [ ! -f "prisma/dev.db" ]; then
  echo "Setting up the local database (first run only)..."
  npx prisma generate
  npx prisma db push
fi

if command -v ollama >/dev/null 2>&1; then
  echo "Ollama detected — real AI will run locally. If you haven't already, run: ollama pull llama3.1"
else
  echo "Ollama not found — install it from https://ollama.com for real, free, local AI (the app still starts without it)."
fi

echo ""
echo "Open http://localhost:3000 in your browser"
echo ""

exec npx next dev
