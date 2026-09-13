@echo off
setlocal
set "LAB=C:\Users\RIGGUSPIG\Desktop\god-tier-metal\tools\boo-lab"
set "FLAC=C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\audio-corpus\born_of_osiris"
set "GP=C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs"
if not exist "%LAB%\src\boo_lab" ( echo Missing lab & pause & exit /b 1 )
if not exist "%LAB%\src\boo_lab\static" mkdir "%LAB%\src\boo_lab\static"
copy /Y "%~dp0annotator.html" "%LAB%\src\boo_lab\static\annotator.html" >nul
for %%F in (annotator.py catalogue.py cli.py extract.py guess.py pack.py stems.py lyrics.py ingest.py learn.py gate.py structure.py) do (
  if exist "%~dp0%%F" copy /Y "%~dp0%%F" "%LAB%\src\boo_lab\%%F" >nul
)
(
  echo BOO_FLAC_ROOT=%FLAC%
  echo BOO_GP_ROOT=%GP%
) > "%LAB%\.env"
call "%LAB%\.venv\Scripts\activate.bat"
set "BOO_FLAC_ROOT=%FLAC%"
set "BOO_GP_ROOT=%GP%"
python -m pip install -q python-multipart
echo Scanning...
python -m boo_lab.cli scan
echo http://127.0.0.1:8765
python -m boo_lab.cli studio --port 8765
pause
