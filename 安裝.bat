@echo off
REM ============================================================
REM   GPU Simulator 一鍵安裝(Windows)
REM   組員雙擊這個檔案即可,不需要打開 PowerShell
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   GPU Simulator 一鍵安裝
echo ============================================================
echo.

REM ---- 切到本 .bat 檔所在的資料夾 ---------------------------
cd /d "%~dp0"

REM ---- 1. 檢查 Python ----------------------------------------
echo [1/4] 檢查 Python...
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo X 找不到 Python!
    echo.
    echo 請先安裝 Python 3.10 或更新版本:
    echo   1. 開瀏覽器到 https://www.python.org/downloads/
    echo   2. 下載最新穩定版(避開 3.14 beta^)
    echo   3. 安裝時務必勾選「Add Python to PATH」
    echo   4. 安裝完成後重新雙擊本檔案
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo     找到 Python !PYVER!

REM ---- 2. 建虛擬環境 -----------------------------------------
echo.
echo [2/4] 建立虛擬環境(.venv)...
if exist .venv (
    echo     .venv 已存在,跳過
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo X 建立 .venv 失敗,請確認 Python 安裝正確。
        pause
        exit /b 1
    )
    echo     建立完成
)

REM ---- 3. 啟動 venv 並安裝套件 -------------------------------
echo.
echo [3/4] 安裝相依套件(可能要 1–2 分鐘^)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>nul
pip install -e .
if errorlevel 1 (
    echo X 安裝失敗,把上面的錯誤訊息傳給 Shana。
    pause
    exit /b 1
)
echo     安裝完成

REM ---- 4. 完成 -----------------------------------------------
echo.
echo [4/4] 完成!
echo.
echo ============================================================
echo   安裝成功 ^!
echo.
echo   現在你可以雙擊「啟動.bat」開啟 GPU Simulator
echo   或雙擊「錄影模式.bat」跑 60 秒自動 demo
echo ============================================================
echo.
pause
endlocal
