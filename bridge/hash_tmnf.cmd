@echo off
setlocal

rem Keep the path assignment outside parenthesized IF blocks.
rem This avoids CMD parsing the "(x86)" part of Program Files (x86).
set "GAME_EXE=C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever\TmForever.exe"

if exist "%GAME_EXE%" goto :hash

echo TmForever.exe was not found at:
echo %GAME_EXE%
echo.
echo Edit GAME_EXE in this script if your Steam library is elsewhere.
exit /b 1

:hash
echo SHA-256 for:
echo %GAME_EXE%
echo.
certutil -hashfile "%GAME_EXE%" SHA256
if errorlevel 1 exit /b 1
echo.
echo Record this hash in bridge\profiles\ for an exact-build profile.
exit /b 0
