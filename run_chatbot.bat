@echo off
title Line OA Gemini AI Chatbot Launcher
cls

echo =======================================================
echo     Starting Line OA Gemini AI Chatbot Setup
echo =======================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Python is not installed or not in PATH!
    echo Please install Python 3.10+ and add it to your environment variables.
    pause
    exit /b
)

:: 2. Setup Env File
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [System] Created .env file from template.
        echo.
        echo WARNING: Please open the new '.env' file in this folder
        echo and configure your LINE and Gemini credentials before running.
        echo.
        pause
    ) else (
        echo [Error] .env.example not found. Please create .env manually.
        pause
        exit /b
    )
)

:: 3. Install Dependencies
echo [System] Installing Python libraries from requirements.txt...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [Error] Failed to install Python dependencies.
    pause
    exit /b
)
echo [System] Python dependencies satisfied.
echo.

:: 4. Start Server
echo [System] Launching FastAPI Chatbot Server...
echo.
python main.py
pause
