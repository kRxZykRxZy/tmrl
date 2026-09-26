@echo off
setlocal EnableExtensions

rem TMRL launcher for TMInterface 1.4.3 installed beside TmForever.exe.
rem
rem Usage:
rem   launch_50.cmd "C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever"
rem
rem The folder must contain BOTH:
rem   TMInterface.exe
rem   TmForever.exe

if not "%~1"=="" set "GAME_DIR=%~1"

if not defined GAME_DIR (
  echo Missing TrackMania Nations Forever folder.
  echo.
  echo Example:
  echo   launch_50.cmd "C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever"
  exit /b 2
)

if not exist "%GAME_DIR%\TMInterface.exe" (
  echo TMInterface.exe not found:
  echo   "%GAME_DIR%\TMInterface.exe"
  exit /b 3
)

if not exist "%GAME_DIR%\TmForever.exe" (
  echo TmForever.exe not found:
  echo   "%GAME_DIR%\TmForever.exe"
  exit /b 4
)

echo TMInterface 1.4.3 folder:
echo   "%GAME_DIR%"
echo.
echo Found:
echo   TMInterface.exe
echo   TmForever.exe
echo.
echo Starting 50 instances from the TrackMania directory...
echo.

pushd "%GAME_DIR%" || exit /b 5

for /L %%N in (0,1,49) do call :launch_one %%N

popd

echo.
echo Finished sending 50 launch requests.
echo.
echo Verify the TMInterface server names before starting TMRL:
echo   TMInterface0 ... TMInterface49
exit /b 0

:launch_one
echo [%%1] starting
start "" "TMInterface.exe"
timeout /t 1 /nobreak >nul
exit /b 0
