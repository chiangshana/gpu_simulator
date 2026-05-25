# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for gpu_simulator.

Build with:
    pyinstaller gpu_simulator.spec --noconfirm --clean

輸出在 dist/GPU-Simulator/(--onedir 模式;組員把整個資料夾複製過去雙擊 .exe 就跑)。
這比 --onefile 更可靠,因為 PySide6 的 Qt 外掛在單檔模式下啟動很慢、出錯也不好除錯。
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# --- 收集 gpu_simulator 套件下所有子模組(含 vendored tiny8_full)----------
hiddenimports = collect_submodules("gpu_simulator")

# --- matplotlib backend / PySide6 plugins 用 PyInstaller hook 自動處理 -----
# 但這幾個底層 backend 模組,pyinstaller 偶爾抓不到,顯式加上保險。
hiddenimports += [
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_agg",
    "PySide6.QtSvg",
    "PySide6.QtNetwork",
]

# --- 把 tiny8_full 內可能有的 .asm / 範例檔(若有)也帶進去 -----------------
datas = collect_data_files("gpu_simulator")


a = Analysis(
    ["gpu_simulator_main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 開發 / 測試工具,不需要打包
        "pytest",
        "pytest_cov",
        "ruff",
        "PyInstaller",
        # 可選相依,沒裝就會 ImportError 並 graceful fallback
        # 把它們排除可以避免不必要的肥大
        "pynvml",
        "GPUtil",
        "pyttsx3",
        "anthropic",
        # matplotlib 預設拉一堆 GUI backend,我們只用 Qt agg
        "tkinter",
        "_tkinter",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GPU-Simulator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX 壓縮對 PySide6 經常有問題,關掉
    console=False,        # --windowed:雙擊不會跳黑視窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GPU-Simulator",
)
