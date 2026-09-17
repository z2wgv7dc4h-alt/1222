@echo off
REM Kept for muscle memory. Installs once if needed, then launches the studio.
REM It does NOT overwrite .env -- setup.bat writes that only when --flac is passed.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0setup.bat" %*
  if errorlevel 1 exit /b 1
)

call "%~dp0START.bat"
