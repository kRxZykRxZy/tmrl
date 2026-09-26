@echo off
setlocal

rem Usage:
rem   launch_50.cmd
rem   launch_50.cmd "C:\Path\To\TMInterface.exe"
rem
rem An explicit argument is safest for Steam installs whose path contains
rem parentheses such as "Program Files (x86)".

if not "%~1"=="" set "TMI_EXE=%~1"
if not defined TMI_EXE (
  echo TMI_EXE is not set.
  echo.
  echo Example:
  echo   launch_50.cmd "C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever\TMInterface.exe"
  echo.
  echo Or set it first:
  echo   set "TMI_EXE=C:\Path\To\TMInterface.exe"
  echo   launch_50.cmd
  exit /b 2
)

if not exist "%TMI_EXE%" goto :missing

echo Using:
echo   "%TMI_EXE%"
echo.
echo Sending 50 launch requests...
for /L %%N in (0,1,49) do call :launch_one %%N

echo.
echo Finished sending launch requests.
echo Verify each instance exposes a distinct TMInterface server name before running python main.py.
exit /b 0

:launch_one
echo [%%1] starting TMInterface
start "" "%TMI_EXE%"
timeout /t 1 /nobreak >nul
exit /b 0

:missing
echo TMInterface executable not found:
echo   "%TMI_EXE%"
exit /b 3
