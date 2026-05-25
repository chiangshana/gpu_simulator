@echo off
REM ============================================================
REM   GPU Simulator — 直接開到「💻 真實硬體」分頁
REM   當作多核 CPU + GPU 即時儀表板用
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
gpu-simulator --monitor
