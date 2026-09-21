@echo off
REM Launch the boo-lab studio. Requires setup.bat to have run once.
REM Studio opens right after scan/hash. Full intern prep runs in a separate
REM window so a SongFormer EMA hang cannot block labeling.
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

echo.
echo Intern prep in a separate window (stems/beats/structure/...; cache-first).
echo That window can sit on SongFormer without blocking studio. Close it anytime.
start "boo-lab interns" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && echo === boo-lab interns (background) === && echo Resumable / cache-first. Never Guess / never Save keepers. && python -m boo_lab.cli interns & echo. & echo interns finished. Close this window when done. & pause"

echo.
echo Studio: http://127.0.0.1:8765   (Ctrl+C to stop; restart after .py changes)
echo Lab: Guess computes live; Load drafts / Lyrics use prep in the other window.
echo Heard+Save stays yours.
python -m boo_lab.cli studio --port 8765
pause
