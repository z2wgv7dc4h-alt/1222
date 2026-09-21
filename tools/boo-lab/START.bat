@echo off
REM Launch the boo-lab studio. Requires setup.bat to have run once.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo No .venv found. Run setup.bat first:
  echo   setup.bat --flac "C:\path\to\audio-corpus" --gp "C:\path\to\gp-tabs"
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"

echo Scanning corpus into data/map.csv ...
python -m boo_lab.cli scan

echo Hashing new FLACs (skips already-hashed rows) ...
python -m boo_lab.cli hash

echo Full intern prep (stems, beats, structure/drafts, drums, vocals, lyrics, sync, extract, figures, tempo_hints, compare, learn, predict, status) ...
echo Resumable and cache-first: skips work already on disk. Never Guess / never Save keepers.
python -m boo_lab.cli interns
if errorlevel 1 (
  echo.
  echo WARNING: interns exited with errors - studio still opens; check the log above.
)

echo.
echo Studio: http://127.0.0.1:8765   (Ctrl+C to stop; restart after .py changes)
echo Lab: Guess computes live; Load drafts / Lyrics use prep above. Heard+Save stays yours.
python -m boo_lab.cli studio --port 8765
pause
