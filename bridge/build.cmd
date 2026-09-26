@echo off
setlocal

cd /d "%~dp0"

where cmake >nul 2>nul
if errorlevel 1 (
  echo CMake was not found in PATH.
  echo Install CMake separately or use a Visual Studio Developer Command Prompt.
  exit /b 1
)

if not exist build-native mkdir build-native

echo [1/2] Configuring 32-bit native bridge...
cmake -S native -B build-native -A Win32
if errorlevel 1 exit /b 1

echo [2/2] Building Release DLL...
cmake --build build-native --config Release
if errorlevel 1 exit /b 1

echo.
echo Native bridge build completed.
echo Output:
echo %~dp0build-native\Release\tmrl_tmnf_bridge.dll
exit /b 0
