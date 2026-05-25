"""PyInstaller 用的進入點。

直接呼叫 `gpu_simulator.cli.main`。把這個檔放在 repo 根目錄是因為 PyInstaller
要從一個具體的 .py 開始 freeze,雖然 ``[project.scripts]`` 也定義了
``gpu-simulator = gpu_simulator.cli:main``,但 PyInstaller 不會讀 pyproject.toml,
所以需要這支獨立檔。
"""

from __future__ import annotations

import sys


def _force_utf8_stdio() -> None:
    """讓 stdout/stderr 用 UTF-8,確保中文 / emoji 在 Windows console 正確顯示。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == "__main__":
    _force_utf8_stdio()
    from gpu_simulator.cli import main

    sys.exit(main())
