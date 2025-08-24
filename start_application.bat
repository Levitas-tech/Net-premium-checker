@echo off
title Net Premium Checker - Starting Application
color 0A

echo.
echo ========================================
echo    NET PREMIUM CHECKER STARTUP
echo ========================================
echo.
echo Starting the application...
echo Please wait while we initialize everything...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    echo.
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org
    echo.
    pause
    exit /b 1
)

REM Check if required files exist
if not exist "main.py" (
    echo ERROR: main.py not found
    echo Please run this script from the project root directory
    echo.
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo ERROR: frontend/package.json not found
    echo Please run this script from the project root directory
    echo.
    pause
    exit /b 1
)

echo ✓ Python found: 
python --version
echo ✓ Node.js found:
node --version
echo.

REM Install Python dependencies if requirements.txt exists
if exist "requirements.txt" (
    echo Installing Python dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo WARNING: Some Python dependencies failed to install
        echo The application may not work properly
        echo.
    ) else (
        echo ✓ Python dependencies installed
    )
    echo.
)

REM Install frontend dependencies if node_modules doesn't exist
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    npm install
    if errorlevel 1 (
        echo WARNING: Frontend dependencies failed to install
        echo The application may not work properly
        echo.
    ) else (
        echo ✓ Frontend dependencies installed
    )
    cd ..
    echo.
)

echo Starting backend server...
echo.
start "Backend Server" cmd /k "python start_all.py"

REM Wait a bit for backend to start
timeout /t 5 /nobreak >nul

echo Starting frontend application...
echo.
start "Frontend App" cmd /k "cd frontend && npm start"

echo.
echo ========================================
echo    APPLICATION STARTING UP!
echo ========================================
echo.
echo ✓ Backend server is starting...
echo ✓ Frontend application is starting...
echo.
echo Please wait for both windows to fully load:
echo 1. Backend server should show "Running on http://..."
echo 2. Frontend should open in your browser automatically
echo.
echo If the browser doesn't open automatically, go to:
echo http://localhost:3000
echo.
echo To stop the application, close both command windows.
echo.
echo ========================================
echo.
pause
