@echo off
setlocal

set "GAME_EXE=%ProgramFiles(x86)%\Steam\steamapps\common\TrackMania Nations Forever\TmForever.exe"

if not exist "%GAME_EXE%" (
  echo TmForever.exe was not found at:
  echo %GAME_EXE%
  echo.
  echo Set GAME_EXE in this script to your actual installation path.
  exit /b 1
)

echo SHA-256 for:
echo %GAME_EXE%
certutil -hashfile "%GAME_EXE%" SHA256
echo.
echo Record this hash in bridge\profiles\ for an exact-build profile.
