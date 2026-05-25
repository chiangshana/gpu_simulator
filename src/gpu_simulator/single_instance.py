"""單實例保護 — 防止 widget 同時跑多份疊在桌面上。

實作:綁一個固定 port 的 TCP socket 當 mutex。
* 第一個 instance:bind 成功,持有 socket 直到 process 結束
* 第二個 instance:bind 失敗(``OSError`` `[WinError 10048]`),回 None,
  呼叫端據此跳訊息給使用者並退出

選 TCP socket 而不是 ``QSharedMemory`` / ``QLocalServer`` 的理由:
* 作業系統會在 process 結束/crash 時自動釋放 port,沒有「stale lock」問題
* 不需要 Qt 已初始化(可以在 ``QApplication()`` 之前就 check)
* 跨平台行為一致(Windows / macOS / Linux)
"""

from __future__ import annotations

import contextlib
import socket

# 任挑的 port,選 47000–49000 區間避開常用服務
DEFAULT_LOCK_PORT = 47891


def try_acquire_lock(port: int = DEFAULT_LOCK_PORT) -> socket.socket | None:
    """嘗試 bind localhost:port 當 mutex。

    回傳值:
    * 成功 → 已 bind+listen 的 :class:`socket.socket`。呼叫端必須在
      整個 application lifecycle 期間持有這個 socket(避免被 GC)。
    * 失敗(port 已被佔用)→ ``None``。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None


def release_lock(lock: socket.socket | None) -> None:
    """乾淨地釋放 lock socket;``None`` 視為 no-op,失敗也吞掉。"""
    if lock is None:
        return
    with contextlib.suppress(Exception):
        lock.close()


def is_lock_held(port: int = DEFAULT_LOCK_PORT) -> bool:
    """探測 ``port`` 是否被佔用;**會在過程中短暫佔用一次**,所以
    呼叫此函式之後請別馬上呼叫 :func:`try_acquire_lock`,中間可能有 race。
    這支 helper 主要給測試用,production code 直接用 :func:`try_acquire_lock`
    並用回傳值判斷即可。
    """
    s = try_acquire_lock(port)
    if s is None:
        return True
    s.close()
    return False
