@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%TMI_EXE%"=="" (
  echo TMI_EXE is not set.
  echo Set it to your TMInterface 1.4.3 executable, for example:
  echo   set "TMI_EXE=C:\Path\To\TMInterface.exe"
  echo Then run this file again.
  exit /b 2
)

if not exist "%TMI_EXE%" (
  echo TMInterface executable not found:
  echo %TMI_EXE%
  exit /b 3
)

echo Launching 50 Trackmania/TMInterface instances...
for /L %%N in (0,1,49) do (
  echo Starting instance %%N
  start "" "%TMI_EXE%"
  timeout /t 1 /nobreak >nul
)

echo.
echo All 50 launch requests were sent.
echo Verify the TMInterface console server names are TMInterface0 through TMInterface49.
echo Then from the repository directory run:
echo   python main.py
endlocal
