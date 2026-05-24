"""Toast 通知 — 取代 QMessageBox.info,不阻塞主執行緒。

`ToastManager` 維護一個 toast queue,從畫面右下角往上堆疊,各自會在 ~3 秒後淡出。
資料層(:class:`ToastSpec`)沒 Qt 相依,可以單獨測試「toast 排版邏輯」(堆疊位置、過期時間)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToastLevel(Enum):
    """Toast 的語意層級 — 決定底色跟圖示。"""

    INFO = "info"        # 中性訊息
    SUCCESS = "success"  # 綠色,完成
    WARNING = "warning"  # 黃色,提醒
    ERROR = "error"      # 紅色,錯誤

    @property
    def icon(self) -> str:
        return {
            ToastLevel.INFO: "ℹ️",
            ToastLevel.SUCCESS: "✅",
            ToastLevel.WARNING: "⚠️",
            ToastLevel.ERROR: "❌",
        }[self]

    @property
    def background_color(self) -> str:
        """rgba CSS string — UI 用來上色。"""
        return {
            ToastLevel.INFO: "rgba(40, 100, 200, 235)",
            ToastLevel.SUCCESS: "rgba(40, 160, 70, 235)",
            ToastLevel.WARNING: "rgba(200, 140, 30, 235)",
            ToastLevel.ERROR: "rgba(200, 50, 50, 235)",
        }[self]


@dataclass(frozen=True)
class ToastSpec:
    """一則 toast 的純資料表示 — 不含 Qt。"""

    title: str
    body: str = ""
    level: ToastLevel = ToastLevel.INFO
    duration_ms: int = 3000  # 顯示多久,過了就 fade out

    def display_text(self) -> str:
        if self.body:
            return f"{self.level.icon}  {self.title}\n{self.body}"
        return f"{self.level.icon}  {self.title}"


def stack_y_offset(index: int, toast_height: int, gap: int = 8) -> int:
    """第 ``index`` 個 toast 從底部往上偏移多少 pixel(0-based,0 = 最底)。"""
    if index < 0:
        raise ValueError("index 不能為負")
    return index * (toast_height + gap)


# ---------------------------------------------------------------------------
# Qt overlay — 只有 import 時才碰 PySide6,測試模式可不載入
# ---------------------------------------------------------------------------
def build_toast_widget(parent, spec: ToastSpec):
    """建一個 toast widget(QFrame)+ QPropertyAnimation 控制淡入淡出。"""
    from PySide6.QtCore import (
        QEasingCurve,
        QPropertyAnimation,
        Qt,
        QTimer,
    )
    from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

    frame = QFrame(parent)
    frame.setObjectName("toast")
    frame.setStyleSheet(
        f"""
        QFrame#toast {{
            background: {spec.level.background_color};
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,40);
        }}
        QLabel {{
            color: white;
            font-size: 12pt;
            background: transparent;
        }}
        """
    )
    frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 10)
    label = QLabel(spec.display_text(), frame)
    label.setWordWrap(True)
    label.setTextFormat(Qt.PlainText)
    layout.addWidget(label)

    # 入場:0 → 1 alpha
    frame.setWindowOpacity(0.0)
    fade_in = QPropertyAnimation(frame, b"windowOpacity")
    fade_in.setDuration(220)
    fade_in.setStartValue(0.0)
    fade_in.setEndValue(1.0)
    fade_in.setEasingCurve(QEasingCurve.OutCubic)

    fade_out = QPropertyAnimation(frame, b"windowOpacity")
    fade_out.setDuration(420)
    fade_out.setStartValue(1.0)
    fade_out.setEndValue(0.0)
    fade_out.setEasingCurve(QEasingCurve.InCubic)
    fade_out.finished.connect(frame.deleteLater)

    # 顯示 duration_ms 之後啟動 fade out
    QTimer.singleShot(spec.duration_ms, fade_out.start)

    fade_in.start()
    # 把動畫 reference 掛在 frame 上避免被 GC
    frame._toast_anims = (fade_in, fade_out)  # type: ignore[attr-defined]
    return frame


class ToastManager:
    """Toast 管理員 — 維護一個 toast list,負責堆疊與排版。

    UI 端透過 :meth:`show` 推一則 toast 進來。資料層在這支類別,Qt overlay 由
    :func:`build_toast_widget` 處理。測試可以用 ``with_qt=False`` 跑純資料邏輯。
    """

    DEFAULT_WIDTH = 320
    DEFAULT_HEIGHT = 68
    MARGIN_RIGHT = 24
    MARGIN_BOTTOM = 24

    def __init__(self, parent=None, *, with_qt: bool = True) -> None:
        self._parent = parent
        self._with_qt = with_qt
        self._active: list = []  # list[QFrame] 或 list[ToastSpec] in test mode

    def __len__(self) -> int:
        return len(self._active)

    def show(self, spec: ToastSpec):
        """推一則 toast。回傳建立的 widget(test mode 下回 spec 本身)。"""
        if not self._with_qt or self._parent is None:
            # 純資料模式 — 給測試用
            self._active.append(spec)
            return spec
        widget = build_toast_widget(self._parent, spec)
        widget.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self._active.append(widget)
        self._reposition_all()
        # 過 duration + fade out 時間後從 list 移除
        from PySide6.QtCore import QTimer

        cleanup_delay = spec.duration_ms + 500
        QTimer.singleShot(cleanup_delay, lambda w=widget: self._remove(w))
        return widget

    def _remove(self, widget) -> None:
        if widget in self._active:
            self._active.remove(widget)
        if self._with_qt:
            self._reposition_all()

    def _reposition_all(self) -> None:
        if not self._with_qt or self._parent is None:
            return
        parent_w = self._parent.width()
        parent_h = self._parent.height()
        for idx, widget in enumerate(self._active):
            offset = stack_y_offset(idx, self.DEFAULT_HEIGHT)
            x = parent_w - self.DEFAULT_WIDTH - self.MARGIN_RIGHT
            y = parent_h - self.DEFAULT_HEIGHT - self.MARGIN_BOTTOM - offset
            widget.move(x, max(8, y))
            widget.show()
            widget.raise_()

    def clear(self) -> None:
        for widget in list(self._active):
            if self._with_qt and hasattr(widget, "deleteLater"):
                widget.deleteLater()
        self._active.clear()


# ---------------------------------------------------------------------------
# 便利包裝
# ---------------------------------------------------------------------------
def info(manager: ToastManager, title: str, body: str = "") -> None:
    manager.show(ToastSpec(title=title, body=body, level=ToastLevel.INFO))


def success(manager: ToastManager, title: str, body: str = "") -> None:
    manager.show(ToastSpec(title=title, body=body, level=ToastLevel.SUCCESS))


def warning(manager: ToastManager, title: str, body: str = "") -> None:
    manager.show(ToastSpec(title=title, body=body, level=ToastLevel.WARNING))


def error(manager: ToastManager, title: str, body: str = "") -> None:
    manager.show(ToastSpec(title=title, body=body, level=ToastLevel.ERROR))
