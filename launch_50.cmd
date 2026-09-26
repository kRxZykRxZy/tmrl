@echo off
setlocal EnableExtensions

rem TMRL 50-instance launcher for TMInterface 1.4.3.
rem
rem Usage:
rem   launch_50.cmd "C:\Path\To\TMInterface.exe" "C:\Path\To\TrackMania Nations Forever"
rem
rem Example Steam:
rem   launch_50.cmd "C:\TMInterface\TMInterface.exe" "C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever"
rem
rem TMInterface.exe and TmForever.exe do NOT have to be in the same directory.

if not "%~1"=="" set "TMI_EXE=%~1"
if not "%~2"=="" set "GAME_DIR=%~2"

if not defined TMI_EXE (
  echo Missing TMInterface.exe path.
  echo.
  echo Example:
  echo   launch_50.cmd "C:\TMInterface\TMInterface.exe" "C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever"
  exit /b 2
)

if not defined GAME_DIR (
  echo Missing TrackMania Nations Forever directory.
  echo.
  echo Find it in Steam:
  echo   Library ^> TrackMania Nations Forever ^> Properties ^> Installed Files ^> Browse
  echo.
  echo Then pass the folder containing TmForever.exe as the second argument.
  exit /b 2
)

if not exist "%TMI_EXE%" (
  echo TMInterface.exe not found:
  echo   "%TMI_EXE%"
  exit /b 3
)

if not exist "%GAME_DIR%\TmForever.exe" (
  echo TmForever.exe not found:
  echo   "%GAME_DIR%\TmForever.exe"
  echo.
  echo Steam TMNF normally installs the game executable as TmForever.exe.
  exit /b 4
)

echo TMInterface:
echo   "%TMI_EXE%"
echo.
echo TrackMania:
echo   "%GAME_DIR%\TmForever.exe"
echo.
echo Launching 50 instances...
echo.

for /L %%N in (0,1,49) do call :launch_one %%N

echo.
echo Finished sending 50 launch requests.
echo Verify the instances expose:
echo   TMInterface0 ... TMInterface49
exit /b 0

:launch_one
echo [%%1] starting
start "" /D "%GAME_DIR%" "%TMI_EXE%"
timeout /t 1 /nobreak >nul
exit /b 0
