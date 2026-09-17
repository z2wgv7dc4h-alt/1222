@echo off
REM One-shot boo-lab setup for a fresh machine (Windows).
REM   setup.bat            -> install core + intern + pitch + align
REM   setup.bat --flac DIR --gp DIR   -> also write .env corpus roots
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "FLAC="
set "GP="
:parse
if "%~1"=="" goto afterparse
if /I "%~1"=="--flac" ( set "FLAC=%~2" & shift & shift & goto parse )
if /I "%~1"=="--gp"   ( set "GP=%~2"   & shift & shift & goto parse )
shift
goto parse
:afterparse

where python >nul 2>nul || ( echo Python not found on PATH. Install Python 3.12 first. & exit /b 1 )

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  python -m venv .venv || ( echo venv create failed & exit /b 1 )
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip wheel setuptools

REM GPU torch first: RTX 50xx / Blackwell needs the cu128 index. The CUDA
REM build is hard-pinned in constraints.txt (torch==2.8.0+cu128), so a later
REM extras install cannot silently swap in the PyPI 2.8.0+cpu wheel. Only the
REM CUDA path uses -c: there is no +cu128 wheel for a CPU-only machine.
where nvidia-smi >nul 2>nul
set "CONSTRAINT="
if !errorlevel!==0 (
  echo Installing CUDA torch ^(cu128^) ...
  set "CONSTRAINT=-c constraints.txt"
  python -m pip install -c constraints.txt "torch==2.8.0" "torchaudio==2.8.0" "torchvision==0.23.0" --index-url https://download.pytorch.org/whl/cu128
) else (
  echo No NVIDIA GPU detected -- installing CPU torch.
  python -m pip install "torch==2.8.0" "torchaudio==2.8.0" "torchvision==0.23.0"
)

echo Installing boo-lab + core + interns ...
python -m pip install !CONSTRAINT! -e "." python-multipart
python -m pip install !CONSTRAINT! -e ".[intern]"
python -m pip install !CONSTRAINT! -e ".[pitch]"
python -m pip install !CONSTRAINT! -e ".[align]"

if not "%FLAC%"=="" (
  ( echo BOO_FLAC_ROOT=%FLAC%
    echo BOO_GP_ROOT=%GP% ) > ".env"
  echo Wrote .env
)

echo.
python -m boo_lab.cli doctor --require-interns
if errorlevel 1 (
  echo.
  echo SETUP FAILED: an intern or core dependency is missing (see the hints above).
  echo Fix the install, then re-run doctor:
  echo   .venv\Scripts\python -m boo_lab.cli doctor --require-interns
  pause
  exit /b 1
)
echo.
echo Done. Set BOO_FLAC_ROOT / BOO_GP_ROOT in .env, then:
echo   .venv\Scripts\python -m boo_lab.cli scan
echo   .venv\Scripts\python -m boo_lab.cli studio
pause
