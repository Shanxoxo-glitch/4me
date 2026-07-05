@echo off
title BRIAN AI Assistant Installer
echo.
echo  ╔══════════════════════════════════════╗
echo  ║      BRIAN AI Assistant Setup        ║
echo  ╚══════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause & exit /b 1
)

echo [1/5] Creating Python virtual environment...
cd /d "%~dp0"
python -m venv venv
if errorlevel 1 ( echo [ERROR] venv creation failed & pause & exit /b 1 )

echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/5] Installing openWakeWord from local clone...
pip install -e ..\openWakeWord --quiet
if errorlevel 1 ( echo [WARN] openWakeWord install had issues, continuing... )

echo [4/5] Installing Brian core dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 ( echo [ERROR] Dependency install failed & pause & exit /b 1 )

echo [5/5] Registering Brian for Windows startup...
python install_startup.py

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   BRIAN setup complete!              ║
echo  ║   Run: python main.py                ║
echo  ║   Or just restart your PC!           ║
echo  ╚══════════════════════════════════════╝
echo.
pause
