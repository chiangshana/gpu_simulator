@echo off
REM ============================================================
REM   GPU Simulator — 一鍵更新「一鍵安裝包.exe」並推上 GitHub
REM
REM   流程:
REM     1. PyInstaller 重打包             (~1–2 分鐘)
REM     2. 蓋掉根目錄的「一鍵安裝包.exe」
REM     3. git add + commit + push        (~30 秒,看網路)
REM
REM   只要改完程式碼,雙擊本檔即可發新版給組員。
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ============================================================
echo   更新「一鍵安裝包.exe」
echo ============================================================
echo.

REM ---- 0. 環境檢查 --------------------------------------------
if not exist .venv (
    echo X 找不到 .venv,請先雙擊「安裝.bat」一次。
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

pip show pyinstaller >nul 2>nul
if errorlevel 1 (
    echo [0/3] 安裝 PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo X PyInstaller 安裝失敗。
        pause
        exit /b 1
    )
)

REM ---- 1. 打包 ------------------------------------------------
echo.
echo [1/3] PyInstaller 重打包(約 1–2 分鐘^)...
echo.
pyinstaller gpu_simulator.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo X 打包失敗。把上面錯誤訊息傳給 Shana。
    pause
    exit /b 1
)

if not exist dist\GPU-Simulator.exe (
    echo X 打包看似成功,但找不到 dist\GPU-Simulator.exe
    pause
    exit /b 1
)

REM ---- 2. 覆蓋 ------------------------------------------------
echo.
echo [2/3] 覆蓋根目錄的「一鍵安裝包.exe」...
copy /Y dist\GPU-Simulator.exe 一鍵安裝包.exe >nul
if errorlevel 1 (
    echo X 複製失敗。
    pause
    exit /b 1
)
for %%A in (一鍵安裝包.exe) do echo     新版大小:%%~zA bytes(約 %%~zA bytes^)

REM ---- 3. git push 確認 ---------------------------------------
echo.
echo [3/3] 要把新版推到 GitHub 嗎?
echo.
echo   選 Y:自動 git add + commit + push
echo   選 N:本檔案結束,你之後手動跑 git 指令
echo.
choice /C YN /N /M "推到 GitHub? [Y/N]: "
if errorlevel 2 (
    echo.
    echo === 已跳過 git push。手動指令: ===
    echo     git add 一鍵安裝包.exe
    echo     git commit -m "Update 一鍵安裝包.exe"
    echo     git push
    echo.
    pause
    exit /b 0
)

REM 取得今天日期當 commit message
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value ^| find "="') do set DT=%%I
set TODAY=!DT:~0,4!-!DT:~4,2!-!DT:~6,2!

echo.
echo === git add + commit + push ===
git add 一鍵安裝包.exe
git commit -m "Update 一鍵安裝包.exe !TODAY!"
if errorlevel 1 (
    echo.
    echo (沒有變更可 commit,或 commit 失敗;繼續嘗試 push^)
)

echo.
echo 推送中(75 MB,看網路約 30 秒–數分鐘^)...
git push
if errorlevel 1 (
    echo.
    echo X git push 失敗。可能原因:
    echo   - 沒設定 GitHub 認證(第一次 push 通常會跳視窗要登入^)
    echo   - 網路不通
    echo   - 別人在你之前已 push,要先 git pull
    echo.
    pause
    exit /b 1
)

REM ---- 完成 ---------------------------------------------------
echo.
echo ============================================================
echo   完成 ^! 組員去 repo 頁面下載「一鍵安裝包.exe」就是新版。
echo.
echo   GitHub:https://github.com/chiangshana/gpu_simulator
echo ============================================================
echo.
pause
endlocal
