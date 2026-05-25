#!/usr/bin/env bash
# ============================================================
#   GPU Simulator 一鍵安裝(macOS / Linux)
#   組員在終端機跑:  bash install.sh
#   或:             chmod +x install.sh && ./install.sh
# ============================================================
set -e

cd "$(dirname "$0")"

echo
echo "============================================================"
echo "  GPU Simulator 一鍵安裝"
echo "============================================================"
echo

# ---- 1. 檢查 Python ----
echo "[1/4] 檢查 Python..."
if ! command -v python3 >/dev/null 2>&1; then
    echo
    echo "X 找不到 python3!"
    echo
    echo "請先安裝 Python 3.10 或更新版本:"
    echo "  macOS:    brew install python@3.12"
    echo "  Ubuntu:   sudo apt install python3 python3-venv python3-pip"
    echo "  其他:     https://www.python.org/downloads/"
    echo
    exit 1
fi
PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "    找到 Python $PY_VERSION"

# ---- 2. 建虛擬環境 ----
echo
echo "[2/4] 建立虛擬環境(.venv)..."
if [ -d .venv ]; then
    echo "    .venv 已存在,跳過"
else
    python3 -m venv .venv
    echo "    建立完成"
fi

# ---- 3. 啟動 venv 並安裝套件 ----
echo
echo "[3/4] 安裝相依套件(可能要 1–2 分鐘)..."
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null 2>&1
pip install -e .
echo "    安裝完成"

# ---- 4. 完成 ----
echo
echo "[4/4] 完成!"
echo
echo "============================================================"
echo "  安裝成功!"
echo
echo "  啟動方式(在這個資料夾下):"
echo "    bash start.sh              # 一般啟動"
echo "    bash start.sh --cinema     # 60 秒自動 demo"
echo "    bash start.sh --monitor    # 直接開硬體儀表板"
echo "============================================================"
echo
