@echo off
setlocal EnableExtensions

rem TMRL 50-instance launcher.
rem Use:
rem   launch_50.cmd "C:\Path\To\TMInterface.exe"
rem
rem The /D working-directory flag is important: TMInterface needs to find
rem its companion TmForever.exe relative to its installation directory.

if not "%~1"=="" set "TMI_EXE=%~1"

if not defined TMI_EXE (
  echo TMI_EXE is not set.
  echo.
  echo Example:
  echo   launch_50.cmd "C:\TMInterface\TMInterface.exe"
  echo.
  echo Or:
  echo   set "TMI_EXE=C:\TMInterface\TMInterface.exe"
  echo   launch_50.cmd
  exit /b 2
)

if not exist "%TMI_EXE%" (
  echo TMInterface.exe not found:
  echo   "%TMI_EXE%"
  exit /b 3
)

for %%I in ("%TMI_EXE%") do set "TMI_DIR=%%~dpI"

if not exist "%TMI_DIR%TmForever.exe" (
  echo.
  echo ERROR: TmForever.exe was not found beside TMInterface.exe.
  echo.
  echo TMInterface directory:
  echo   "%TMI_DIR%"
  echo.
  echo Expected:
  echo   "%TMI_DIR%TmForever.exe"
  echo.
  echo Install the compatible TMInterface/TMNF package correctly, then retry.
  exit /b 4
)

echo TMInterface:
echo   "%TMI_EXE%"
echo Game:
echo   "%TMI_DIR%TmForever.exe"
echo.
echo Launching 50 instances...
echo.

for /L %%N in (0,1,49) do call :launch_one %%N

echo.
echo Finished sending 50 launch requests.
echo.
echo Verify that the instances expose:
echo   TMInterface0 ... TMInterface49
echo.
exit /b 0

:launch_one
echo [%%1] starting
start "" /D "%TMI_DIR%" "%TMI_EXE%"
timeout /t 1 /nobreak >nul
exit /b 0
