@echo off
REM One-command launcher for Study Creator (Windows).
REM Just double-click this file and open http://localhost:3000 in your
REM browser. No API key, no cloud, no setup.

cd /d "%~dp0"

if not exist "node_modules" (
  echo Installing dependencies (first run only, this can take a minute)...
  call npm install
  if errorlevel 1 goto :error
)

if not exist "prisma\dev.db" (
  echo Setting up the local database (first run only)...
  call npx prisma generate
  if errorlevel 1 goto :error
  call npx prisma db push
  if errorlevel 1 goto :error
)

where ollama >nul 2>nul
if errorlevel 1 (
  echo Ollama not found - install it from https://ollama.com for real, free, local AI ^(the app still starts without it^).
) else (
  echo Ollama detected - real AI will run locally. If you haven't already, run: ollama pull llama3.1
)

echo.
echo Open http://localhost:3000 in your browser
echo.

call npx next dev
goto :eof

:error
echo.
echo Something went wrong during setup. See the error above.
pause
exit /b 1
