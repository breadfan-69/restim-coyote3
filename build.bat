@echo off
setlocal enabledelayedexpansion

cd /d "c:\Users\andre\Downloads\coyoterestim\restim"

echo Cleaning old builds...
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul

echo.
echo Killing Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 3 /nobreak

echo.
echo Building executable...
python -m PyInstaller restim.spec --clean --noconfirm

if exist "dist\restim\restim.exe" (
    echo.
    echo ✓ BUILD SUCCESSFUL!
    echo.
    echo Launching application...
    timeout /t 2 /nobreak
    start "" "dist\restim\restim.exe"
) else (
    echo.
    echo ✗ BUILD FAILED - exe not found
    pause
)
