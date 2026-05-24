"""彩蛋系統 — 偵測 Konami code 跟「魔法字」,觸發隱藏特效。

Konami:↑ ↑ ↓ ↓ ← → ← → B A → 觸發超 mega 煙火。
魔法字(連續輸入):"matrix" → 切到 Matrix 主題、"dragon" → 寵物直接進化到龍、
"reset" → 把彩蛋偵測器重置(避免誤觸發)。

資料層 :class:`EasterEggDetector` 是個有限狀態機,純 Python 沒 Qt 相依。
UI 端只需把 keyPress 的 ``str`` 餵進來,看 detector 是否觸發。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# Konami code 的標準鍵序列(用我們自訂的字串標籤)
KONAMI_SEQUENCE: tuple[str, ...] = (
    "UP", "UP", "DOWN", "DOWN",
    "LEFT", "RIGHT", "LEFT", "RIGHT",
    "B", "A",
)

# 內建魔法字
DEFAULT_MAGIC_WORDS: dict[str, str] = {
    "matrix": "trigger_matrix_theme",
    "dragon": "trigger_dragon_pet",
    "rainbow": "trigger_rainbow_burst",
    "boom": "trigger_firework",
}


@dataclass
class EasterEggDetector:
    """有限狀態機 — 同時追蹤 Konami 與 magic word 兩種輸入流。"""

    magic_words: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MAGIC_WORDS))
    _konami_idx: int = 0
    _text_buffer: str = ""
    _max_buffer: int = 24  # 太長就裁切尾巴

    def feed_key(self, label: str) -> str | None:
        """餵一個鍵盤事件;``label`` 是我們自訂的標籤(UP / DOWN / A / B / 一個字母…)。

        Konami code 命中回 ``"konami"``,沒命中回 None。
        """
        expected = KONAMI_SEQUENCE[self._konami_idx]
        if label == expected:
            self._konami_idx += 1
            if self._konami_idx >= len(KONAMI_SEQUENCE):
                self._konami_idx = 0
                return "konami"
            return None
        # 不對 — 重置;但如果這個 key 是 sequence 的開頭也算一次起步
        if label == KONAMI_SEQUENCE[0]:
            self._konami_idx = 1
        else:
            self._konami_idx = 0
        return None

    def feed_char(self, ch: str) -> str | None:
        """餵一個可列印字元;若 buffer 含任何 magic word 後綴,回該 word 的 trigger。"""
        if not ch:
            return None
        # 只看小寫字母 + 數字;空白、符號當分隔
        ch_low = ch.lower()
        if not (ch_low.isalnum()):
            self._text_buffer = ""
            return None
        self._text_buffer = (self._text_buffer + ch_low)[-self._max_buffer:]
        for word, trigger in self.magic_words.items():
            if self._text_buffer.endswith(word):
                self._text_buffer = ""
                return trigger
        return None

    def reset(self) -> None:
        self._konami_idx = 0
        self._text_buffer = ""


# ---------------------------------------------------------------------------
# Qt 整合 helper — 把一個 detector 接到 QWidget 的 keyPressEvent
# ---------------------------------------------------------------------------
def qt_key_to_label(key, text: str = "") -> str | None:
    """把 Qt key code 轉成 :class:`EasterEggDetector` 認得的標籤。"""
    try:
        from PySide6.QtCore import Qt
    except ImportError:
        return None
    mapping = {
        Qt.Key_Up: "UP",
        Qt.Key_Down: "DOWN",
        Qt.Key_Left: "LEFT",
        Qt.Key_Right: "RIGHT",
    }
    if key in mapping:
        return mapping[key]
    if text and len(text) == 1 and text.isalpha():
        return text.upper()
    return None


def make_default_handlers(
    *,
    on_konami: Callable[[], None] | None = None,
    on_matrix: Callable[[], None] | None = None,
    on_dragon: Callable[[], None] | None = None,
    on_rainbow: Callable[[], None] | None = None,
    on_firework: Callable[[], None] | None = None,
) -> dict[str, Callable[[], None]]:
    """把所有 trigger 名稱對應到 callback;沒提供的就用 no-op。"""
    noop = lambda: None  # noqa: E731
    return {
        "konami": on_konami or noop,
        "trigger_matrix_theme": on_matrix or noop,
        "trigger_dragon_pet": on_dragon or noop,
        "trigger_rainbow_burst": on_rainbow or noop,
        "trigger_firework": on_firework or noop,
    }


def dispatch(trigger: str | None, handlers: dict[str, Callable[[], None]]) -> bool:
    """根據 trigger 名稱呼對應 callback;真的有觸發回 True。"""
    import contextlib

    if trigger is None:
        return False
    handler = handlers.get(trigger)
    if handler is None:
        return False
    with contextlib.suppress(Exception):
        handler()
    return True
