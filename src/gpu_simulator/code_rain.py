"""Matrix 風格 code rain 背景特效。

當 GPU 利用率超過門檻(預設 70%),畫面開始下「綠色字元雨」 — 致敬 The Matrix。
低利用率時自動停下來,所以平常不會打擾使用者。

分兩層:

1. **純資料層** — :class:`CodeRain` 用純 Python 管理一堆 :class:`RainStream`,
   每個 stream 有自己的位置、速度、字元串;每 frame ``tick()`` 一次。
2. **Qt overlay 層** — :class:`CodeRainOverlay` 是個透明 QWidget,
   主視窗放它在最底層當背景。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# 用於下雨的字元集 — Tiny8 風的混合(數字 + ASM 助記符 + 一些日文片假名感字)
RAIN_CHARSET: tuple[str, ...] = tuple(
    "0123456789ABCDEFLDIRJMPADDSUBMOVOUTKLAUNCHWAITSTLDLDS"
)


@dataclass
class RainStream:
    """一條垂直往下流的字元串。"""

    column_x: int
    head_y: float
    speed: float       # 像素 / tick
    length: int        # 字元數
    chars: list[str] = field(default_factory=list)
    flicker_seed: int = 0

    def tick(self) -> None:
        self.head_y += self.speed

    def char_at(self, index: int) -> str:
        if 0 <= index < len(self.chars):
            return self.chars[index]
        return "0"

    def is_off_screen(self, height: int) -> bool:
        tail_y = self.head_y - self.length * 16
        return tail_y > height


@dataclass
class CodeRain:
    """整個 code rain 的狀態。"""

    width: int = 360
    height: int = 600
    column_spacing: int = 16
    streams: list[RainStream] = field(default_factory=list)
    active: bool = False
    activation_threshold: float = 0.70  # GPU util > 此值才下雨
    deactivation_threshold: float = 0.40

    def update_utilization(self, utilization: float) -> None:
        """utilization 0..1;到一定門檻啟動,降下來就關。"""
        if utilization >= self.activation_threshold:
            self.active = True
        elif utilization <= self.deactivation_threshold:
            self.active = False
            self.streams.clear()

    def tick(self, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        if not self.active:
            return
        # 隨機補新 stream(讓畫面持續有東西在掉)
        target_stream_count = max(8, self.width // (self.column_spacing * 2))
        if len(self.streams) < target_stream_count:
            self._spawn_stream(rng)
        # 推進現有 stream
        for stream in self.streams:
            stream.tick()
        # 把離開螢幕的清掉
        self.streams = [s for s in self.streams if not s.is_off_screen(self.height)]

    def _spawn_stream(self, rng: random.Random) -> None:
        column_index = rng.randrange(0, max(1, self.width // self.column_spacing))
        length = rng.randint(8, 20)
        chars = [rng.choice(RAIN_CHARSET) for _ in range(length)]
        stream = RainStream(
            column_x=column_index * self.column_spacing,
            head_y=-rng.randint(0, 60),
            speed=rng.uniform(2.0, 4.5),
            length=length,
            chars=chars,
            flicker_seed=rng.randint(0, 9999),
        )
        self.streams.append(stream)

    def reset(self) -> None:
        self.streams.clear()
        self.active = False


# ===========================================================================
# Qt overlay
# ===========================================================================
def build_overlay(parent):
    """建立透明、滑鼠穿透的 code rain overlay。"""
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QFont, QPainter
    from PySide6.QtWidgets import QWidget

    class CodeRainOverlay(QWidget):
        FRAME_INTERVAL_MS = 50  # 20 FPS,雨慢一點才有 Matrix 感

        def __init__(self, host: QWidget) -> None:
            super().__init__(host)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setStyleSheet("background: transparent;")
            self.lower()  # 放到最底層當背景
            self._rain = CodeRain(width=host.width(), height=host.height())
            self._timer = QTimer(self)
            self._timer.setInterval(self.FRAME_INTERVAL_MS)
            self._timer.timeout.connect(self._on_frame)
            self.resize(host.size())

        @property
        def rain(self) -> CodeRain:
            return self._rain

        def set_utilization(self, utilization: float) -> None:
            self._rain.update_utilization(utilization)
            if self._rain.active and not self._timer.isActive():
                self._timer.start()
            if not self._rain.active and self._timer.isActive():
                self._timer.stop()

        def _on_frame(self) -> None:
            self._rain.width = self.width()
            self._rain.height = self.height()
            self._rain.tick()
            self.update()

        def paintEvent(self, event) -> None:  # noqa: N802
            if not self._rain.active or not self._rain.streams:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, False)
            font = QFont("Consolas")
            font.setStyleHint(QFont.Monospace)
            font.setPointSize(11)
            painter.setFont(font)

            for stream in self._rain.streams:
                for offset in range(stream.length):
                    char = stream.char_at(offset)
                    y = int(stream.head_y - offset * 14)
                    # head 最亮,往尾巴漸暗
                    if offset == 0:
                        color = QColor(180, 255, 200, 240)
                    else:
                        fade = max(0, 200 - offset * 12)
                        color = QColor(0, 255, 95, fade)
                    painter.setPen(color)
                    painter.drawText(stream.column_x, y, char)

    return CodeRainOverlay(parent)
