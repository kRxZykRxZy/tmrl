@echo off
setlocal

cd /d "%~dp0"

where cmake >nul 2>nul
if errorlevel 1 (
  echo CMake was not found in PATH.
  exit /b 1
)

echo Detecting a 32-bit-capable CMake generator...

where cl >nul 2>nul
if not errorlevel 1 goto :build_vs

where gcc >nul 2>nul
if not errorlevel 1 goto :build_gcc

echo No C/C++ compiler was found in PATH.
echo.
echo For the 32-bit TMNF bridge, use one of:
echo   1. A Visual Studio Developer Command Prompt with 32-bit tools
echo   2. A MinGW 32-bit toolchain
echo.
echo Do not use a 64-bit-only compiler for the final TMNF DLL.
exit /b 1

:build_vs
if not exist build-native rmdir /s /q build-native 2>nul
echo [1/2] Configuring with Visual Studio 32-bit generator...
cmake -S native -B build-native -G "Visual Studio 17 2022" -A Win32
if errorlevel 1 goto :fail

echo [2/2] Building Release DLL...
cmake --build build-native --config Release
if errorlevel 1 goto :fail
goto :success

:build_gcc
if not exist build-native rmdir /s /q build-native 2>nul
echo [1/2] Configuring with MinGW...
cmake -S native -B build-native -G "MinGW Makefiles"
if errorlevel 1 goto :fail

echo [2/2] Building Release DLL...
cmake --build build-native --config Release
if errorlevel 1 goto :fail
goto :success

:success
echo.
echo Native bridge build completed.
echo Output:
if exist "build-native\Release\tmrl_tmnf_bridge.dll" echo %~dp0build-native\Release\tmrl_tmnf_bridge.dll
if exist "build-native\tmrl_tmnf_bridge.dll" echo %~dp0build-native\tmrl_tmnf_bridge.dll
exit /b 0

:fail
echo.
echo Native bridge build failed.
exit /b 1
