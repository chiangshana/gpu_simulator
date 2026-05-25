#!/usr/bin/env bash
# ============================================================
#   GPU Simulator — 啟動 (macOS / Linux)
#   用法:
#     bash start.sh              # 一般啟動
#     bash start.sh --cinema     # 60 秒自動 demo
#     bash start.sh --monitor    # 直接開硬體儀表板
# ============================================================
set -e

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo
    echo "X 還沒安裝!請先跑:  bash install.sh"
    echo
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
gpu-simulator "$@"
