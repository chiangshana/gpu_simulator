"""底部狀態列 — 永遠顯示在主視窗最下方。

格式:`v0.9.0 · 模式:Cinema · Kernels:42 · 利用率:68% · FPS:60`

資料層 :class:`StatusSnapshot` 用純 dataclass,可以單獨測試「字串組裝」。
UI 端 :class:`StatusBar` 是個 QFrame,QLabel 用 monospace 顯示。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StatusSnapshot:
    """目前狀態 — 由 widget 每秒組裝一次。"""

    version: str
    mode: str = "即時"
    kernels: int = 0
    utilization_percent: float = 0.0
    fps: float = 0.0
    extra: tuple[str, ...] = field(default_factory=tuple)

    def format_text(self) -> str:
        parts = [
            f"v{self.version}",
            f"模式:{self.mode}",
            f"Kernels:{self.kernels}",
            f"利用率:{self.utilization_percent:.0f}%",
            f"FPS:{self.fps:.0f}",
        ]
        parts.extend(self.extra)
        return "  ·  ".join(parts)


# ---------------------------------------------------------------------------
# Qt widget
# ---------------------------------------------------------------------------
def build_status_bar(parent, initial: StatusSnapshot):
    """回傳一個 QFrame 已經設好 label,呼叫端可用 ``frame._label.setText(...)``。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

    frame = QFrame(parent)
    frame.setObjectName("statusBar")
    frame.setStyleSheet(
        """
        QFrame#statusBar {
            background: rgba(25, 28, 38, 230);
            border-top: 1px solid rgba(100, 130, 180, 100);
        }
        QLabel#statusLabel {
            color: rgba(220, 230, 240, 230);
            font-family: 'Consolas', 'Cascadia Mono', monospace;
            font-size: 9pt;
            padding: 4px 10px;
        }
        """
    )
    frame.setFixedHeight(26)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel(initial.format_text(), frame)
    label.setObjectName("statusLabel")
    label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    layout.addWidget(label, 1)
    frame._status_label = label  # type: ignore[attr-defined]
    return frame


def update_status_bar(frame, snapshot: StatusSnapshot) -> None:
    label = getattr(frame, "_status_label", None)
    if label is not None:
        label.setText(snapshot.format_text())
