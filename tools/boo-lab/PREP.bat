@echo off
REM Full intern prep only (no studio). Same as the side window START opens.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No .venv found. Run setup.bat first.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
echo === boo-lab interns ===
echo Resumable / cache-first. Never Guess / never Save keepers.
python -m boo_lab.cli interns
echo.
echo Done.
pause
