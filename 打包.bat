@echo off
REM ============================================================
REM   GPU Simulator — 一鍵打包成「單一檔案 .exe」(Windows)
REM
REM   產出:dist\GPU-Simulator.exe(約 75 MB · 單一檔案)
REM        組員下載這一個檔案、雙擊即可,完全不用 Python、不用解壓資料夾
REM
REM   * 需要先跑「安裝.bat」一次,讓 .venv 就緒
REM   * 打包約 1–2 分鐘
REM   * 首次啟動 .exe 慢 5–10 秒(內部解壓到 %TEMP%);同次 boot 內後續啟動很快
REM ============================================================
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo.
echo ============================================================
echo   GPU Simulator — 一鍵打包成 .exe
echo ============================================================
echo.

REM ---- 確認 .venv 存在 ---------------------------------------
if not exist .venv (
    echo X 找不到 .venv,請先雙擊「安裝.bat」。
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

REM ---- 確認 pyinstaller 有裝 ---------------------------------
echo [1/3] 確認 PyInstaller...
pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo     PyInstaller 還沒裝,裝起來中...
    pip install pyinstaller
    if errorlevel 1 (
        echo X PyInstaller 安裝失敗。
        pause
        exit /b 1
    )
)
echo     OK

REM ---- 打包 ---------------------------------------------------
echo.
echo [2/3] 開始打包(約 1–2 分鐘^)...
echo.
pyinstaller gpu_simulator.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo X 打包失敗,請把上面錯誤訊息傳給 Shana。
    pause
    exit /b 1
)

REM ---- 完成 ---------------------------------------------------
echo.
echo [3/3] 完成!
echo.
echo ============================================================
echo   打包成功 ^!
echo.
echo   輸出位置:dist\GPU-Simulator.exe(單一檔案,約 75 MB^)
echo.
echo   組員只要下載這一個 .exe,雙擊就能跑 — 不用裝 Python、
echo   不用解壓、不用任何前置作業。
echo.
echo   建議:直接把 dist\GPU-Simulator.exe 上傳到 GitHub Release,
echo         組員從 Releases 頁面下載即可。
echo ============================================================
echo.
pause
endlocal
