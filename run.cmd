@echo off
setlocal
set "TMI_DIR=C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever"

if not exist "%TMI_DIR%\TMInterface.exe" (
  echo TMInterface.exe not found:
  echo %TMI_DIR%
  exit /b 2
)

cd /d "%~dp0"
echo Starting ONE TMInterface 1.4.3 instance...
start "" /D "%TMI_DIR%" "%TMI_DIR%\TMInterface.exe"
timeout /t 3 /nobreak >nul

echo Installing Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

echo Starting TMRL Control Center...
python main.py
endlocal
