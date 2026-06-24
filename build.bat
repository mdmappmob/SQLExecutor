@echo off
chcp 65001 >nul
title SQL Executor - Build

echo ========================================
echo  SQL Executor - Building executable...
echo ========================================
echo.

:: Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

:: Clean previous build
if exist "dist\SQLExecutor.exe" del "dist\SQLExecutor.exe"
if exist "build" rmdir /s /q "build" 2>nul
if exist "*.spec" del /q "*.spec" 2>nul

:: Build
echo [INFO] Building...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "SQLExecutor" ^
    --icon icon.ico ^
    --add-data "domain;domain" ^
    --add-data "application;application" ^
    --add-data "infrastructure;infrastructure" ^
    --add-data "ui;ui" ^
    --hidden-import pyodbc ^
    --hidden-import oracledb ^
    --hidden-import fdb ^
    --hidden-import getpass ^
    --hidden-import sqlglot ^
    --hidden-import pymysql ^
    --hidden-import psycopg2 ^
    --hidden-import keyring ^
    --hidden-import keyring.backends.Windows ^
    --clean ^
    --noconfirm ^
    main.py

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Executable created: dist\SQLExecutor.exe
    echo.
    dir /b dist\SQLExecutor.exe
) else (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

pause
