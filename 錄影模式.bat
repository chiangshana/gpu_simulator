@echo off
REM ============================================================
REM   GPU Simulator — 60 秒自動 demo(錄影 / 簡報用)
REM ============================================================
chcp 65001 >nul

cd /d "%~dp0"

if not exist .venv (
    echo.
    echo X 還沒安裝!請先雙擊「安裝.bat」。
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
gpu-simulator --cinema
