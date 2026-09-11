@echo off
cd /d "%~dp0"
if not exist .venv call START.bat
call .venv\Scriptsctivate.bat
echo Installing allin1 (optional section guesser). This is heavy.
python -m pip install allin1
echo Done. Restart START.bat
pause
