@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo.
    echo ✗ .venv Python not found at "%PYTHON_EXE%"
    echo   Create the venv first or adjust build.bat.
    pause
    exit /b 1
)

echo Cleaning old builds...
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul

echo.
echo Killing Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 3 /nobreak

echo.
echo Ensuring pyqtgraph is installed in build environment...
"%PYTHON_EXE%" -m pip show pyqtgraph >nul 2>nul || "%PYTHON_EXE%" -m pip install pyqtgraph

echo.
echo Building executable...
"%PYTHON_EXE%" -m PyInstaller restim.spec --clean --noconfirm

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
