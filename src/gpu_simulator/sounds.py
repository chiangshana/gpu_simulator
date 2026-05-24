"""音效回饋(零外部相依套件)。

第九輪升級:每種 GPU kernel 對應一個自己的 chord 動機(motif),
讓使用者**用聽的**就能分辨「現在 GPU 在跑什麼」。

設計:
- 一般 UI 音效(成就、HALT、答對等)→ 短音 pattern
- Kernel 開始 → 該 kernel 專屬的 chord(2-3 個音的琶音)
- Kernel 完成 → 短亮音

Windows 用內建 :mod:`winsound`;其他平台 fallback :class:`QApplication.beep`;
都失敗時靜默 — 音效永遠是 nice-to-have,不能讓主流程崩潰。

聲音播放走背景 thread,絕對不阻塞 UI。
"""

from __future__ import annotations

import contextlib
import sys
import threading
from enum import Enum


class SoundEffect(Enum):
    """已支援的 UI 音效類型(非 kernel 觸發的)。"""

    KERNEL_DONE = "kernel_done"
    HALT = "halt"
    ACHIEVEMENT = "achievement"
    QUIZ_CORRECT = "quiz_correct"
    QUIZ_WRONG = "quiz_wrong"
    KLAUNCH_GENERIC = "klaunch_generic"  # 通用 KLAUNCH 提示音(若沒指定 kernel)


# ---------------------------------------------------------------------------
# UI 音效 pattern(winsound.Beep 序列:每個 tuple = (頻率 Hz, 持續毫秒))
# ---------------------------------------------------------------------------
_UI_PATTERNS: dict[SoundEffect, tuple[tuple[int, int], ...]] = {
    SoundEffect.KERNEL_DONE: ((880, 60),),
    SoundEffect.HALT: ((440, 120), (330, 120)),
    SoundEffect.ACHIEVEMENT: ((660, 80), (880, 80), (1320, 160)),
    SoundEffect.QUIZ_CORRECT: ((1000, 80), (1320, 100)),
    SoundEffect.QUIZ_WRONG: ((220, 200),),
    SoundEffect.KLAUNCH_GENERIC: ((660, 60), (880, 60)),
}

# ---------------------------------------------------------------------------
# 每種 kernel 一段 chord(用 12 平均律的頻率,聽起來像 chiptune 短旋律)
# 設計:不同 kernel 用不同調性 + 不同節奏,讓人聽得出個性。
# ---------------------------------------------------------------------------
KERNEL_CHORDS: dict[str, tuple[tuple[int, int], ...]] = {
    # vector_add — 大調 C-E-G,輕快上行(代表「平行加法,衝高處」)
    "vector_add": ((523, 70), (659, 70), (784, 80)),
    # interpolation — 平緩 D-F#-A,慢速(代表「線性插值,慢慢過去」)
    "interpolation": ((587, 100), (740, 100), (880, 110)),
    # hash — 短促 random-ish 不和諧音(代表「打亂、雜湊」)
    "hash": ((659, 50), (440, 50), (740, 60)),
    # texture_load — 重低音 C2-G2-C3 三音,漸強(代表「載入大資料」)
    "texture_load": ((262, 90), (392, 90), (523, 130)),
    # idle_compression — 低頻長音(代表「省電、休息」)
    "idle_compression": ((196, 200),),
    # app_launch — 高音上行 G-B-D-G(代表「啟動、開機」)
    "app_launch": ((392, 60), (494, 60), (587, 60), (784, 100)),
    # page_nav — 雙音「叮叮」(代表「翻頁」)
    "page_nav": ((1047, 70), (784, 90)),
}


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------
def play(effect: SoundEffect) -> None:
    """非阻塞地播一段 UI 音效;失敗時靜音。"""
    pattern = _UI_PATTERNS.get(effect)
    if pattern is None:
        return
    _play_pattern(pattern)


def play_kernel_chord(kernel_name: str) -> None:
    """根據 kernel 名稱播放它專屬的 chord;名稱未知時 fallback 為通用 KLAUNCH 音。"""
    pattern = KERNEL_CHORDS.get(kernel_name)
    if pattern is None:
        pattern = _UI_PATTERNS[SoundEffect.KLAUNCH_GENERIC]
    _play_pattern(pattern)


def play_idle_pulse() -> None:
    """給「正在 KWAIT 卡住」的時候播的呼吸式低音脈衝。"""
    _play_pattern(((196, 60),))


# ---------------------------------------------------------------------------
# 內部:平台後端
# ---------------------------------------------------------------------------
def _play_pattern(pattern: tuple[tuple[int, int], ...]) -> None:
    """背景 thread 播放整段 pattern。"""
    if not pattern:
        return
    if sys.platform.startswith("win"):
        _play_pattern_windows(pattern)
    else:
        _play_qt_beep()


def _play_pattern_windows(pattern: tuple[tuple[int, int], ...]) -> None:
    import winsound

    def _worker() -> None:
        for frequency_hz, duration_ms in pattern:
            with contextlib.suppress(Exception):
                winsound.Beep(int(frequency_hz), int(duration_ms))

    thread = threading.Thread(target=_worker, name="gpu-simulator-sound", daemon=True)
    thread.start()


def _play_qt_beep() -> None:
    with contextlib.suppress(Exception):
        from PySide6.QtWidgets import QApplication

        application = QApplication.instance()
        if application is not None:
            application.beep()
