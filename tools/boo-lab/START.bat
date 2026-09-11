@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1 && (set PY=py -3) || (set PY=python)
if not exist .venv (
  echo Creating .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Need Python 3.11+ on PATH
    exit /b 1
  )
)
call .venv\Scriptsctivate.bat
python -m pip install -q -U pip
python -m pip install -q -e .

if not exist .env (
  copy /Y .env.example .env >nul
  echo.
  echo First run: edit the two folder paths in .env
  echo   BOO_FLAC_ROOT = your ripped CDs
  echo   BOO_GP_ROOT   = your Guitar Pro tabs
  echo Then save, run START.bat again.
  notepad .env
  exit /b 0
)

echo Scanning library ...
boo-lab scan
echo.
echo UI: http://127.0.0.1:8765
start "" http://127.0.0.1:8765
boo-lab studio --port 8765
