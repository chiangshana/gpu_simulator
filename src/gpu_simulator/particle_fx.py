"""粒子特效系統 — KLAUNCH 噴粒、kernel 完成煙火、KWAIT 釋放波紋。

分兩層:

1. **純資料層** — :class:`Particle` / :class:`ParticleField` 用純 Python 算
   位置、速度、生命週期;沒 Qt 相依,可單獨測試。
2. **Qt overlay 層** — :class:`ParticleOverlay` 是個透明 ``QWidget``,
   放在主視窗之上,每個 frame 把 :class:`ParticleField` 的狀態畫出來。

支援三種發射模式:

- ``LAUNCH`` — KLAUNCH 觸發,粒子從起點朝終點飛去(直線 + 微抖動)
- ``FIREWORK`` — kernel 完成觸發,粒子從中心向外擴散
- ``RIPPLE`` — KWAIT 解除觸發,水波紋從中心擴散
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum


class BurstKind(Enum):
    LAUNCH = "launch"
    FIREWORK = "firework"
    RIPPLE = "ripple"


@dataclass
class Particle:
    """單一粒子的狀態。"""

    x: float
    y: float
    velocity_x: float
    velocity_y: float
    color_r: int  # 0..255
    color_g: int
    color_b: int
    life: float          # 1.0 → 0.0 隨時間遞減
    size: float = 4.0
    gravity: float = 0.0  # 每 tick 加到 velocity_y

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    @property
    def alpha(self) -> int:
        """0..255 — life 線性映射。"""
        return max(0, min(255, int(self.life * 255)))

    def tick(self, decay: float = 0.04) -> None:
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.velocity_y += self.gravity
        self.life = max(0.0, self.life - decay)


@dataclass
class ParticleField:
    """一群活著的粒子;UI 端的 timer 每個 frame 呼叫 :meth:`tick`。"""

    particles: list[Particle] = field(default_factory=list)
    max_particles: int = 600

    def __len__(self) -> int:
        return len(self.particles)

    def tick(self) -> None:
        for particle in self.particles:
            particle.tick()
        self.particles = [particle for particle in self.particles if particle.alive]

    def clear(self) -> None:
        self.particles.clear()

    # ------------------------------------------------------------------
    # 三種發射模式
    # ------------------------------------------------------------------
    def emit_launch(
        self,
        *,
        origin_x: float,
        origin_y: float,
        target_x: float,
        target_y: float,
        count: int = 18,
        color: tuple[int, int, int] = (255, 200, 80),
        seed: int | None = None,
    ) -> None:
        """KLAUNCH:粒子從 origin 朝 target 飛去,帶一點 spread。"""
        rng = random.Random(seed)
        dx = target_x - origin_x
        dy = target_y - origin_y
        max(1.0, math.sqrt(dx * dx + dy * dy))
        # 速度設成讓粒子 15..25 frame 走完
        base_vx = dx / 20.0
        base_vy = dy / 20.0
        for _ in range(count):
            spread_x = rng.uniform(-0.6, 0.6)
            spread_y = rng.uniform(-0.6, 0.6)
            self._add(
                Particle(
                    x=origin_x + rng.uniform(-4, 4),
                    y=origin_y + rng.uniform(-4, 4),
                    velocity_x=base_vx + spread_x,
                    velocity_y=base_vy + spread_y,
                    color_r=color[0],
                    color_g=color[1],
                    color_b=color[2],
                    life=1.0,
                    size=rng.uniform(2.5, 5.0),
                )
            )

    def emit_firework(
        self,
        *,
        center_x: float,
        center_y: float,
        count: int = 28,
        color: tuple[int, int, int] = (120, 220, 140),
        seed: int | None = None,
    ) -> None:
        """Kernel 完成:從中心向外噴。"""
        rng = random.Random(seed)
        for _ in range(count):
            angle = rng.uniform(0, 2 * math.pi)
            speed = rng.uniform(1.5, 3.5)
            self._add(
                Particle(
                    x=center_x,
                    y=center_y,
                    velocity_x=math.cos(angle) * speed,
                    velocity_y=math.sin(angle) * speed,
                    color_r=color[0],
                    color_g=color[1],
                    color_b=color[2],
                    life=1.0,
                    size=rng.uniform(2.5, 4.5),
                    gravity=0.08,  # 煙火會掉下來
                )
            )

    def emit_ripple(
        self,
        *,
        center_x: float,
        center_y: float,
        count: int = 24,
        color: tuple[int, int, int] = (120, 180, 255),
    ) -> None:
        """KWAIT 解除:水波紋(粒子排成圓,慢慢向外擴散)。"""
        for index in range(count):
            angle = (2 * math.pi * index) / count
            self._add(
                Particle(
                    x=center_x,
                    y=center_y,
                    velocity_x=math.cos(angle) * 1.4,
                    velocity_y=math.sin(angle) * 1.4,
                    color_r=color[0],
                    color_g=color[1],
                    color_b=color[2],
                    life=1.0,
                    size=3.0,
                )
            )

    def _add(self, particle: Particle) -> None:
        if len(self.particles) >= self.max_particles:
            self.particles.pop(0)
        self.particles.append(particle)


# ===========================================================================
# Qt overlay — 把 ParticleField 畫到主視窗上方
# ===========================================================================
def build_overlay(parent):
    """為 ``parent`` widget 建立一個透明、滑鼠穿透的 overlay。

    工廠函式;真實 Qt class 只在這裡 import,讓 :mod:`particle_fx` 純資料層
    可以在沒裝 PySide6 的環境也能 import。
    """
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtWidgets import QWidget

    class ParticleOverlay(QWidget):
        """透明 overlay,定時把粒子畫上去。"""

        FRAME_INTERVAL_MS = 33  # ~30 FPS

        def __init__(self, host: QWidget) -> None:
            super().__init__(host)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setStyleSheet("background: transparent;")
            self._field = ParticleField()
            self._timer = QTimer(self)
            self._timer.setInterval(self.FRAME_INTERVAL_MS)
            self._timer.timeout.connect(self._on_frame)
            self.resize(host.size())

        @property
        def field(self) -> ParticleField:
            return self._field

        def start(self) -> None:
            self._timer.start()

        def stop(self) -> None:
            self._timer.stop()

        def emit_launch(self, *args, **kwargs) -> None:
            self._field.emit_launch(*args, **kwargs)
            if not self._timer.isActive():
                self.start()
            self.update()

        def emit_firework(self, *args, **kwargs) -> None:
            self._field.emit_firework(*args, **kwargs)
            if not self._timer.isActive():
                self.start()
            self.update()

        def emit_ripple(self, *args, **kwargs) -> None:
            self._field.emit_ripple(*args, **kwargs)
            if not self._timer.isActive():
                self.start()
            self.update()

        def _on_frame(self) -> None:
            self._field.tick()
            if not self._field.particles:
                self._timer.stop()
            self.update()

        def paintEvent(self, event) -> None:  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            for particle in self._field.particles:
                color = QColor(particle.color_r, particle.color_g, particle.color_b, particle.alpha)
                painter.setBrush(color)
                radius = particle.size
                painter.drawEllipse(
                    int(particle.x - radius),
                    int(particle.y - radius),
                    int(radius * 2),
                    int(radius * 2),
                )

    return ParticleOverlay(parent)
