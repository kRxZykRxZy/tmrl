@echo off
setlocal

set "TMI_DIR=C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever"

if not exist "%TMI_DIR%\TMInterface.exe" goto :no_tmi
if not exist "%TMI_DIR%\TmForever.exe" goto :no_game

cd /d "%~dp0"
echo Starting ONE TMInterface 1.4.3 instance...
start "" /D "%TMI_DIR%" "%TMI_DIR%\TMInterface.exe"
timeout /t 3 /nobreak >nul

echo Installing Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto :pip_failed

echo Starting TMRL Control Center...
python main.py
goto :end

:no_tmi
echo.
echo TMInterface.exe was not found:
echo "%TMI_DIR%\TMInterface.exe"
echo.
echo Edit TMI_DIR in run.cmd if your installation is elsewhere.
goto :fail

:no_game
echo.
echo TmForever.exe was not found:
echo "%TMI_DIR%\TmForever.exe"
echo.
echo Edit TMI_DIR in run.cmd if your installation is elsewhere.
goto :fail

:pip_failed
echo.
echo Python dependency installation failed.
goto :fail

:fail
endlocal
exit /b 1

:end
endlocal
exit /b 0
