"""Qt widget components that render a GPU snapshot.

Every widget here is fully driven by the dictionary returned by
:meth:`gpu_simulator.core.GPU.snapshot`.  None of them hold a reference to
the live GPU object, which keeps the UI thread decoupled from the
simulation and makes each piece trivial to unit-test by handing it a
fabricated snapshot.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gpu_simulator.bridge import TraceRow
from gpu_simulator.commentary import (
    Commentator,
    EventKind,
    classify_row,
)
from gpu_simulator.i18n import kernel_label, t, trigger_label
from gpu_simulator.persistence import SessionMeta

# ---------------------------------------------------------------------------
# shared constants
# ---------------------------------------------------------------------------
HEATMAP_COLD = QColor(40, 50, 80)
HEATMAP_WARM = QColor(255, 170, 40)
HEATMAP_HOT = QColor(240, 70, 70)
PANEL_BG = QColor(24, 26, 34, 220)
TEXT_PRIMARY = QColor(230, 232, 240)
TEXT_DIM = QColor(150, 156, 176)
ACCENT = QColor(120, 180, 255)


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )


def _heatmap_color(value: float) -> QColor:
    """Map ``0.0 → cold``, ``0.5 → warm``, ``1.0 → hot``."""
    if value <= 0.5:
        return _lerp_color(HEATMAP_COLD, HEATMAP_WARM, value * 2.0)
    return _lerp_color(HEATMAP_WARM, HEATMAP_HOT, (value - 0.5) * 2.0)


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    font = QFont()
    font.setBold(True)
    font.setPointSize(9)
    label.setFont(font)
    label.setStyleSheet(f"color: rgba({TEXT_DIM.red()},{TEXT_DIM.green()},{TEXT_DIM.blue()},255);")
    return label


# ---------------------------------------------------------------------------
# stats strip
# ---------------------------------------------------------------------------
class StatsBar(QWidget):
    """Top strip with clock, utilization, and counters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clock_label = QLabel("clock 0")
        self._util_label = QLabel("util 0%")
        self._submitted_label = QLabel("submitted 0")
        self._completed_label = QLabel("completed 0")
        for label in self._all_labels():
            label.setStyleSheet(
                f"color: rgba({TEXT_PRIMARY.red()},{TEXT_PRIMARY.green()},"
                f"{TEXT_PRIMARY.blue()},255); font-size: 10px;"
            )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(10)
        layout.addWidget(self._clock_label)
        layout.addWidget(self._util_label)
        layout.addStretch(1)
        layout.addWidget(self._submitted_label)
        layout.addWidget(self._completed_label)

    def _all_labels(self) -> list[QLabel]:
        return [
            self._clock_label,
            self._util_label,
            self._submitted_label,
            self._completed_label,
        ]

    def update_snapshot(self, snapshot: dict) -> None:
        util_pct = snapshot.get("overall_utilization", 0.0) * 100.0
        self._clock_label.setText(f"時鐘 {snapshot.get('clock', 0)}")
        self._util_label.setText(f"利用率 {util_pct:4.0f}%")
        self._submitted_label.setText(f"已提交 {snapshot.get('kernels_submitted', 0)}")
        self._completed_label.setText(f"已完成 {snapshot.get('kernels_completed', 0)}")


# ---------------------------------------------------------------------------
# SM heatmap
# ---------------------------------------------------------------------------
class SMGridWidget(QWidget):
    """Grid of tiles, each coloured by that SM's warp utilization."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sms: list[dict] = []
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def update_snapshot(self, snapshot: dict) -> None:
        self._sms = snapshot.get("sms", [])
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802  - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        count = len(self._sms)
        if count == 0:
            return
        columns = max(1, math.ceil(math.sqrt(count * 1.8)))
        rows = math.ceil(count / columns)
        padding = 4
        tile_w = (self.width() - padding * (columns + 1)) / columns
        tile_h = (self.height() - padding * (rows + 1)) / rows

        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        for index, sm in enumerate(self._sms):
            row = index // columns
            column = index % columns
            x = padding + column * (tile_w + padding)
            y = padding + row * (tile_h + padding)
            color = _heatmap_color(sm.get("utilization", 0.0))
            painter.setBrush(color)
            painter.setPen(QPen(QColor(0, 0, 0, 90), 1))
            painter.drawRoundedRect(x, y, tile_w, tile_h, 4, 4)

            painter.setPen(QPen(TEXT_PRIMARY))
            painter.drawText(
                int(x + 4),
                int(y + 12),
                f"SM{sm.get('sm_id', index)}",
            )
            util_pct = sm.get("utilization", 0.0) * 100.0
            painter.setPen(QPen(TEXT_PRIMARY))
            painter.drawText(
                int(x + 4),
                int(y + tile_h - 4),
                f"{util_pct:3.0f}%",
            )


# ---------------------------------------------------------------------------
# VRAM bar
# ---------------------------------------------------------------------------
class VRAMBarWidget(QWidget):
    """Horizontal bar showing VRAM usage with a text overlay."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vram: dict = {}
        self.setFixedHeight(22)

    def update_snapshot(self, snapshot: dict) -> None:
        self._vram = snapshot.get("vram", {})
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        width = self.width()
        height = self.height()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(35, 38, 50))
        painter.drawRoundedRect(0, 0, width, height, 4, 4)

        utilization = self._vram.get("utilization", 0.0)
        fill_width = int(width * max(0.0, min(1.0, utilization)))
        painter.setBrush(_heatmap_color(utilization))
        painter.drawRoundedRect(0, 0, fill_width, height, 4, 4)

        used_mib = self._vram.get("used_bytes", 0) / (1024 * 1024)
        total_mib = self._vram.get("capacity_bytes", 0) / (1024 * 1024)
        painter.setPen(QPen(TEXT_PRIMARY))
        painter.drawText(
            8,
            15,
            f"VRAM {used_mib:5.1f} / {total_mib:5.1f} MiB ({utilization * 100:4.1f}%)",
        )


# ---------------------------------------------------------------------------
# pipeline view
# ---------------------------------------------------------------------------
PIPELINE_STAGE_LABELS: tuple[str, ...] = (
    "fetch",
    "decode",
    "execute",
    "memory",
    "writeback",
)


class PipelineWidget(QWidget):
    """Shows how many warps are currently in each pipeline stage."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stage_counts: dict[str, int] = dict.fromkeys(PIPELINE_STAGE_LABELS, 0)
        self._stage_kernels: dict[str, str] = dict.fromkeys(PIPELINE_STAGE_LABELS, "")
        self.setFixedHeight(60)

    def update_snapshot(self, snapshot: dict) -> None:
        counts = dict.fromkeys(PIPELINE_STAGE_LABELS, 0)
        kernels: dict[str, str] = dict.fromkeys(PIPELINE_STAGE_LABELS, "")
        for sm in snapshot.get("sms", []):
            for warp in sm.get("warps", []):
                if warp.get("state") != "running":
                    continue
                stage = warp.get("stage", "fetch")
                counts[stage] = counts.get(stage, 0) + 1
                if not kernels.get(stage):
                    kernels[stage] = warp.get("kernel", "")
        self._stage_counts = counts
        self._stage_kernels = kernels
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        stage_count = len(PIPELINE_STAGE_LABELS)
        padding = 4
        total_spacing = padding * (stage_count + 1)
        cell_width = (self.width() - total_spacing) / stage_count
        cell_height = self.height() - padding * 2
        max_count = max(self._stage_counts.values()) or 1

        for index, stage in enumerate(PIPELINE_STAGE_LABELS):
            x = padding + index * (cell_width + padding)
            y = padding
            count = self._stage_counts.get(stage, 0)
            intensity = count / max_count
            painter.setBrush(_heatmap_color(intensity))
            painter.setPen(QPen(QColor(0, 0, 0, 80), 1))
            painter.drawRoundedRect(x, y, cell_width, cell_height, 4, 4)

            painter.setPen(QPen(TEXT_PRIMARY))
            painter.drawText(int(x + 4), int(y + 12), stage)
            painter.drawText(int(x + 4), int(y + 26), f"×{count}")

            kernel_name = self._stage_kernels.get(stage, "")
            if kernel_name:
                painter.setPen(QPen(TEXT_DIM))
                painter.drawText(
                    int(x + 4),
                    int(y + cell_height - 4),
                    _truncate(kernel_name, max_chars=int(cell_width / 6)),
                )


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    return text[: max_chars - 1] + "…"


# ---------------------------------------------------------------------------
# event log
# ---------------------------------------------------------------------------
class EventLogWidget(QFrame):
    """Scrolling log that mirrors the GPU's internal event ring buffer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self._list_widget = QListWidget(self)
        self._list_widget.setStyleSheet(
            """
            QListWidget {
                background: rgba(20, 22, 30, 180);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(90, 100, 130, 120);
                border-radius: 4px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10px;
            }
            QListWidget::item { padding: 1px 4px; }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list_widget)
        self._seen_clock: int = -1

    def update_snapshot(self, snapshot: dict) -> None:
        entries = snapshot.get("event_log", [])
        new_entries = [entry for entry in entries if entry["clock"] > self._seen_clock]
        if not new_entries:
            return
        for entry in new_entries:
            localized = _localize_event_message(entry["message"])
            item = QListWidgetItem(f"[{entry['clock']:>5}] {localized}")
            self._list_widget.addItem(item)
            self._seen_clock = entry["clock"]
        overflow = self._list_widget.count() - 200
        for _ in range(max(0, overflow)):
            self._list_widget.takeItem(0)
        self._list_widget.scrollToBottom()

    def reset(self) -> None:
        self._list_widget.clear()
        self._seen_clock = -1


# Internal helpers — kept module-level so they can be unit-tested without Qt.
_KERNEL_NAMES_TO_LOCALIZE: tuple[str, ...] = (
    "vector_add",
    "interpolation",
    "texture_load",
    "idle_compression",
    "app_launch",
    "page_nav",
    "hash",  # last so it doesn't gobble inside hash(...)
)
_TRIGGER_NAMES_TO_LOCALIZE: tuple[str, ...] = (
    "mouse_click",
    "mouse_move",
    "focus_change",
    "page_nav",
    "app_launch",
    "idle",
    "keyboard",
)


def _localize_event_message(message: str) -> str:
    """Replace English kernel / trigger / verb tokens with their Chinese form."""
    message = (
        message.replace("submit ", "提交 ")
        .replace("done   ", "完成 ")
        .replace("done ", "完成 ")
        .replace("dropped ", "丟棄 ")
        .replace("VRAM full", "VRAM 已滿")
        .replace("profile=", "型態=")
        .replace("trigger=", "觸發=")
        .replace("grid=", "網格=")
        .replace("compute", "計算密集")
        .replace("memory", "記憶體密集")
        .replace("mixed", "混合型")
        .replace("light", "輕量")
    )
    for kernel_name in _KERNEL_NAMES_TO_LOCALIZE:
        message = message.replace(kernel_name, kernel_label(kernel_name))
    for trigger_name in _TRIGGER_NAMES_TO_LOCALIZE:
        message = message.replace(trigger_name, trigger_label(trigger_name))
    return message


# ---------------------------------------------------------------------------
# analytics chart (matplotlib embedded in Qt)
# ---------------------------------------------------------------------------
class AnalyticsChart(QWidget):
    """Time-series chart of utilisation and VRAM drawn with matplotlib.

    Rendering matplotlib every simulation tick would starve the GUI
    thread, so the chart only redraws once every ``redraw_every`` calls.
    """

    def __init__(
        self,
        history_size: int = 300,
        redraw_every: int = 5,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._redraw_every = max(1, int(redraw_every))
        self._update_counter = 0
        self._clocks: deque[int] = deque(maxlen=history_size)
        self._utilisations: deque[float] = deque(maxlen=history_size)
        self._vram_mib: deque[float] = deque(maxlen=history_size)
        self._canvas = None
        self._figure = None
        self._util_axis = None
        self._vram_axis = None
        self._error_label: QLabel | None = None
        self._build_canvas()

    def _build_canvas(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
        except ImportError:
            self._error_label = QLabel(
                "matplotlib is not installed — run `pip install matplotlib` "
                "to enable the analytics chart."
            )
            self._error_label.setWordWrap(True)
            self._error_label.setStyleSheet(
                f"color: rgba({TEXT_DIM.red()},{TEXT_DIM.green()},{TEXT_DIM.blue()},255);"
            )
            layout.addWidget(self._error_label)
            return

        self._figure = Figure(figsize=(4.2, 2.6), tight_layout=True)
        self._figure.patch.set_alpha(0.0)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setStyleSheet("background: transparent;")
        self._util_axis = self._figure.add_subplot(111)
        self._vram_axis = self._util_axis.twinx()
        for axis in (self._util_axis, self._vram_axis):
            axis.patch.set_alpha(0.0)
        layout.addWidget(self._canvas)

    def update_snapshot(self, snapshot: dict) -> None:
        if self._canvas is None or self._util_axis is None or self._vram_axis is None:
            return
        self._clocks.append(int(snapshot.get("clock", 0)))
        self._utilisations.append(float(snapshot.get("overall_utilization", 0.0)) * 100.0)
        vram_used = snapshot.get("vram", {}).get("used_bytes", 0)
        self._vram_mib.append(vram_used / 1024.0 / 1024.0)

        self._update_counter += 1
        if self._update_counter % self._redraw_every != 0:
            return
        self._util_axis.clear()
        self._vram_axis.clear()
        self._util_axis.plot(
            list(self._clocks), list(self._utilisations), color="#f0a040", linewidth=1.4
        )
        self._util_axis.set_ylim(0, 100)
        self._util_axis.set_xlabel("clock", color="#9ca0b0", fontsize=8)
        self._util_axis.set_ylabel("util %", color="#f0a040", fontsize=8)
        self._util_axis.tick_params(axis="x", colors="#9ca0b0", labelsize=7)
        self._util_axis.tick_params(axis="y", colors="#f0a040", labelsize=7)
        self._util_axis.grid(True, alpha=0.15)
        for spine in self._util_axis.spines.values():
            spine.set_color("#444a5a")

        self._vram_axis.plot(
            list(self._clocks), list(self._vram_mib), color="#78b4ff", linewidth=1.4
        )
        self._vram_axis.set_ylabel("VRAM MiB", color="#78b4ff", fontsize=8)
        self._vram_axis.tick_params(axis="y", colors="#78b4ff", labelsize=7)
        for spine in self._vram_axis.spines.values():
            spine.set_color("#444a5a")

        self._canvas.draw_idle()

    def reset(self) -> None:
        self._clocks.clear()
        self._utilisations.clear()
        self._vram_mib.clear()
        self._update_counter = 0
        if self._util_axis is not None and self._vram_axis is not None:
            self._util_axis.clear()
            self._vram_axis.clear()
            if self._canvas is not None:
                self._canvas.draw_idle()


# ---------------------------------------------------------------------------
# session history panel
# ---------------------------------------------------------------------------
class HistoryPanel(QWidget):
    """List of past sessions; emits signals when the user wants to act on one."""

    refresh_requested = Signal()
    replay_requested = Signal(int)
    export_requested = Signal(int, str)  # (session_id, "csv" | "json" | "markdown" | "png")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet(
            """
            QListWidget {
                background: rgba(20, 22, 30, 180);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(90, 100, 130, 120);
                border-radius: 4px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10px;
            }
            QListWidget::item { padding: 2px 4px; }
            QListWidget::item:selected { background: rgba(120, 180, 255, 120); }
            """
        )
        self._refresh_button = _styled_button(t("btn.refresh"))
        self._replay_button = _styled_button(t("btn.replay"))
        self._export_csv_button = _styled_button(t("btn.export_csv"))
        self._export_md_button = _styled_button(t("btn.export_md"))
        self._export_png_button = _styled_button(t("btn.export_png"))

        self._refresh_button.clicked.connect(self._emit_refresh)
        self._replay_button.clicked.connect(self._emit_replay)
        self._export_csv_button.clicked.connect(lambda: self._emit_export("csv"))
        self._export_md_button.clicked.connect(lambda: self._emit_export("markdown"))
        self._export_png_button.clicked.connect(lambda: self._emit_export("png"))

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(4)
        self._refresh_button.setToolTip("從資料庫重新載入歷史 session")
        self._replay_button.setToolTip("把選中的 session 在 Live 分頁重播一遍")
        button_row.addWidget(self._refresh_button)
        button_row.addWidget(self._replay_button)
        button_row.addStretch(1)
        export_label = QLabel("匯出:")
        export_label.setStyleSheet(
            f"color: rgba({TEXT_DIM.red()},{TEXT_DIM.green()},{TEXT_DIM.blue()},255);"
            "font-size: 10px;"
        )
        button_row.addWidget(export_label)
        button_row.addWidget(self._export_csv_button)
        button_row.addWidget(self._export_md_button)
        button_row.addWidget(self._export_png_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._list_widget, 1)
        layout.addLayout(button_row)

    def populate(self, sessions: list[SessionMeta]) -> None:
        self._list_widget.clear()
        for meta in sessions:
            item = QListWidgetItem(meta.pretty_label())
            item.setData(Qt.UserRole, meta.session_id)
            self._list_widget.addItem(item)

    def _selected_session_id(self) -> int | None:
        current = self._list_widget.currentItem()
        if current is None:
            return None
        session_id = current.data(Qt.UserRole)
        return int(session_id) if session_id is not None else None

    def _emit_refresh(self) -> None:
        self.refresh_requested.emit()

    def _emit_replay(self) -> None:
        session_id = self._selected_session_id()
        if session_id is not None:
            self.replay_requested.emit(session_id)

    def _emit_export(self, format_name: str) -> None:
        session_id = self._selected_session_id()
        if session_id is not None:
            self.export_requested.emit(session_id, format_name)


# ---------------------------------------------------------------------------
# real GPU panel
# ---------------------------------------------------------------------------
class RealGPUPanel(QFrame):
    """Shows the latest reading from the real GPU (when a backend is available)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            QFrame {
                background: rgba(22, 24, 34, 200);
                border: 1px solid rgba(120, 180, 255, 140);
                border-radius: 6px;
            }
            QLabel { color: rgba(220, 224, 236, 230); font-size: 10px; }
            QLabel[kind="key"] { color: rgba(150, 156, 176, 230); }
            """
        )
        self._backend_value = QLabel("—")
        self._name_value = QLabel("—")
        self._util_value = QLabel("—")
        self._memory_value = QLabel("—")
        self._temperature_value = QLabel("—")
        self._power_value = QLabel("—")

        grid = QGridLayout(self)
        grid.setContentsMargins(6, 4, 6, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)
        for column, (key, value_widget) in enumerate(
            (
                ("backend", self._backend_value),
                ("device", self._name_value),
                ("util", self._util_value),
                ("vram", self._memory_value),
                ("temp", self._temperature_value),
                ("power", self._power_value),
            )
        ):
            key_label = QLabel(key)
            key_label.setProperty("kind", "key")
            grid.addWidget(key_label, 0, column)
            grid.addWidget(value_widget, 1, column)

    def set_unavailable(self, reason: str = "no real GPU backend") -> None:
        self._backend_value.setText("none")
        self._name_value.setText(reason)
        for widget in (
            self._util_value,
            self._memory_value,
            self._temperature_value,
            self._power_value,
        ):
            widget.setText("—")

    def update_sample(self, sample) -> None:
        if sample is None:
            self._util_value.setText("—")
            return
        self._backend_value.setText(sample.backend)
        self._name_value.setText(sample.name)
        if sample.utilization_percent is not None:
            self._util_value.setText(f"{sample.utilization_percent:4.0f}%")
        else:
            self._util_value.setText("—")
        if sample.memory_used_bytes is not None and sample.memory_total_bytes:
            used_mib = sample.memory_used_bytes / 1024 / 1024
            total_mib = sample.memory_total_bytes / 1024 / 1024
            self._memory_value.setText(f"{used_mib:.0f}/{total_mib:.0f} MiB")
        else:
            self._memory_value.setText("—")
        if sample.temperature_celsius is not None:
            self._temperature_value.setText(f"{sample.temperature_celsius:3.0f}°C")
        else:
            self._temperature_value.setText("—")
        if sample.power_watts is not None:
            self._power_value.setText(f"{sample.power_watts:4.1f} W")
        else:
            self._power_value.setText("—")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Tiny8-full ↔ GPU side-by-side view
# ---------------------------------------------------------------------------
class Tiny8FullView(QWidget):
    """Side-by-side panel: full Tiny8 CPU state on the left, GPU on the right.

    Reads the bridge's history arrays (full register / memory / sreg
    snapshots) plus the GPU's snapshot dict to draw both sides at once.
    Painted by hand for a Tiny8-CLI feel + arrow showing the kernel
    flowing CPU → GPU when KLAUNCH fires.
    """

    MEMORY_DEFAULT_RANGE: tuple[int, int] = (0x60, 0x80)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._registers: tuple[int, ...] = tuple(0 for _ in range(32))
        self._previous_registers: tuple[int, ...] = self._registers
        self._memory: tuple[int, ...] = tuple(0 for _ in range(256))
        self._previous_memory: tuple[int, ...] = self._memory
        self._memory_start, self._memory_end = self.MEMORY_DEFAULT_RANGE
        self._sreg_text = "----"
        self._step = 0
        self._pc = 0
        self._instruction_text = "(尚未載入程式)"
        self._cpu_halted = False
        self._cpu_stalled = False
        self._kernel_arrow_active = False
        self._gpu_snapshot: dict | None = None

    def update_state(
        self,
        *,
        step: int,
        pc: int,
        instruction_text: str,
        sreg_text: str,
        registers: tuple[int, ...],
        memory: tuple[int, ...],
        previous_registers: tuple[int, ...] | None,
        previous_memory: tuple[int, ...] | None,
        cpu_halted: bool,
        cpu_stalled: bool,
        kernel_dispatched: bool,
        gpu_snapshot: dict,
    ) -> None:
        self._step = step
        self._pc = pc
        self._instruction_text = instruction_text
        self._sreg_text = sreg_text
        self._registers = registers
        self._previous_registers = previous_registers or registers
        self._memory = memory
        self._previous_memory = previous_memory or memory
        self._cpu_halted = cpu_halted
        self._cpu_stalled = cpu_stalled
        self._kernel_arrow_active = kernel_dispatched
        self._gpu_snapshot = gpu_snapshot
        self.update()

    def reset(self) -> None:
        self._registers = tuple(0 for _ in range(32))
        self._previous_registers = self._registers
        self._memory = tuple(0 for _ in range(256))
        self._previous_memory = self._memory
        self._sreg_text = "----"
        self._step = 0
        self._pc = 0
        self._instruction_text = "(尚未載入程式)"
        self._cpu_halted = False
        self._cpu_stalled = False
        self._kernel_arrow_active = False
        self._gpu_snapshot = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), DEBUG_BG)

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        line_height = metrics.height() + 2
        char_width = metrics.horizontalAdvance("0")

        total_width = self.width()
        cpu_width = int(total_width * 0.62)
        gpu_x = cpu_width + 6
        gpu_width = total_width - gpu_x - 4
        cursor_y = 6

        # Section headers
        painter.setPen(QPen(DEBUG_PC))
        painter.drawText(8, cursor_y + line_height - 4, "← Tiny8 完整版 CPU")
        painter.setPen(QPen(QColor(120, 220, 140)))
        painter.drawText(gpu_x, cursor_y + line_height - 4, "虛擬 GPU →")
        cursor_y += line_height + 4

        cursor_y = self._draw_status_line(painter, cursor_y, line_height, char_width, cpu_width)
        cursor_y += 4
        cursor_y = self._draw_register_grid(
            painter, cursor_y, line_height, char_width, max_x=cpu_width - 4
        )
        cursor_y += 4
        self._draw_memory_grid(painter, cursor_y, line_height, char_width, max_x=cpu_width - 4)

        # GPU side
        self._draw_gpu_panel(painter, gpu_x, gpu_width, line_height, char_width)

        # Arrow
        if self._kernel_arrow_active:
            self._draw_kernel_arrow(painter, cpu_width, gpu_x, line_height)

    # ------------------------------------------------------------------
    # painters
    # ------------------------------------------------------------------
    def _draw_status_line(
        self, painter: QPainter, y: int, line_height: int, char_width: int, max_x: int
    ) -> int:
        if self._cpu_halted and not self._cpu_stalled:
            indicator_color = QColor(255, 110, 110)
            indicator_text = t("status.halted_indicator")
        elif self._cpu_stalled:
            indicator_color = QColor(180, 200, 230)
            indicator_text = t("status.kwait_indicator")
        else:
            indicator_color = QColor(120, 220, 140)
            indicator_text = t("status.running_indicator")

        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, y + line_height - 4, "Step")
        painter.setPen(QPen(DEBUG_FG))
        painter.drawText(40, y + line_height - 4, f"{self._step:>5}")
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(96, y + line_height - 4, "PC")
        painter.setPen(QPen(DEBUG_PC))
        painter.drawText(120, y + line_height - 4, f"0x{self._pc:04X}")
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(168, y + line_height - 4, "SREG")
        painter.setPen(QPen(DEBUG_FG))
        painter.drawText(200, y + line_height - 4, self._sreg_text)
        painter.setPen(QPen(indicator_color))
        painter.drawText(max(240, max_x - 140), y + line_height - 4, indicator_text)

        instruction_y = y + line_height + 2
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, instruction_y + line_height - 4, "指令")
        painter.setPen(QPen(DEBUG_FG))
        instruction = self._instruction_text or ""
        max_chars = max(8, (max_x - 50) // char_width)
        painter.drawText(40, instruction_y + line_height - 4, instruction[:max_chars])
        return instruction_y + line_height

    def _draw_register_grid(
        self,
        painter: QPainter,
        y: int,
        line_height: int,
        char_width: int,
        max_x: int,
    ) -> int:
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, y + line_height - 4, "暫存器 R0–R31")
        y += line_height
        cols = 8
        rows = 4
        cell_width = max(char_width * 8, (max_x - 16) // cols)
        cell_height = line_height + 2
        margin_left = 8
        for row in range(rows):
            for col in range(cols):
                index = row * cols + col
                if index >= len(self._registers):
                    continue
                value = self._registers[index]
                previous_value = (
                    self._previous_registers[index]
                    if index < len(self._previous_registers)
                    else value
                )
                changed = value != previous_value
                cell_x = margin_left + col * cell_width
                cell_y = y + row * cell_height
                painter.setPen(QPen(DEBUG_BORDER))
                painter.setBrush(DEBUG_CHANGE if changed else DEBUG_BG)
                painter.drawRect(cell_x, cell_y, cell_width - 4, cell_height - 2)
                painter.setPen(QPen(DEBUG_BG if changed else DEBUG_DIM))
                painter.drawText(cell_x + 2, cell_y + line_height - 4, f"R{index:02}")
                painter.setPen(QPen(DEBUG_BG if changed else DEBUG_FG))
                painter.drawText(
                    cell_x + cell_width - char_width * 4,
                    cell_y + line_height - 4,
                    f"{value:3}",
                )
        return y + rows * cell_height

    def _draw_memory_grid(
        self,
        painter: QPainter,
        y: int,
        line_height: int,
        char_width: int,
        max_x: int,
    ) -> None:
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(
            8,
            y + line_height - 4,
            f"記憶體 0x{self._memory_start:02X}–0x{self._memory_end - 1:02X}",
        )
        y += line_height
        cols = 16
        cell_width = max(char_width * 3, (max_x - 38) // cols)
        cell_height = line_height + 2
        addresses = range(self._memory_start, self._memory_end)
        for offset, address in enumerate(addresses):
            row = offset // cols
            col = offset % cols
            if address >= len(self._memory):
                break
            value = self._memory[address]
            previous_value = (
                self._previous_memory[address]
                if address < len(self._previous_memory)
                else value
            )
            changed = value != previous_value
            cell_x = 38 + col * cell_width
            cell_y = y + row * cell_height
            painter.setPen(QPen(DEBUG_BORDER))
            painter.setBrush(DEBUG_CHANGE if changed else DEBUG_BG)
            painter.drawRect(cell_x, cell_y, cell_width - 2, cell_height - 2)
            painter.setPen(QPen(DEBUG_BG if changed else DEBUG_FG))
            painter.drawText(cell_x + 2, cell_y + line_height - 4, f"{value:02X}")
            if col == 0:
                painter.setPen(QPen(DEBUG_DIM))
                painter.drawText(8, cell_y + line_height - 4, f"0x{address:02X}")

    def _draw_gpu_panel(
        self, painter: QPainter, x: int, width: int, line_height: int, char_width: int
    ) -> None:
        if self._gpu_snapshot is None:
            painter.setPen(QPen(DEBUG_DIM))
            painter.drawText(x + 4, 30 + line_height - 4, "(尚未開始)")
            return
        snapshot = self._gpu_snapshot
        # SM heatmap (compact)
        sms = snapshot.get("sms", [])
        cols = 4
        rows = max(1, (len(sms) + cols - 1) // cols)
        cell_w = max(20, (width - 8) // cols)
        cell_h = line_height + 4
        start_y = 30
        painter.setPen(QPen(DEBUG_DIM))
        utilization_pct = snapshot.get("overall_utilization", 0.0) * 100
        painter.drawText(
            x + 4, start_y - 4, f"8 顆 SM(總利用率 {utilization_pct:.0f}%)"
        )
        for index, sm in enumerate(sms):
            row = index // cols
            col = index % cols
            cell_x = x + col * cell_w
            cell_y = start_y + row * (cell_h + 2)
            color = _heatmap_color(sm.get("utilization", 0.0))
            painter.setPen(QPen(QColor(0, 0, 0, 90), 1))
            painter.setBrush(color)
            painter.drawRoundedRect(cell_x, cell_y, cell_w - 2, cell_h, 3, 3)
            painter.setPen(QPen(QColor(20, 20, 20)))
            painter.drawText(cell_x + 4, cell_y + line_height - 4, f"SM{sm.get('sm_id', index)}")
            painter.drawText(
                cell_x + cell_w - char_width * 4 - 2,
                cell_y + line_height - 4,
                f"{sm.get('utilization', 0.0) * 100:3.0f}%",
            )

        # VRAM bar
        vram = snapshot.get("vram", {})
        vram_y = start_y + rows * (cell_h + 2) + 8
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(x + 4, vram_y - 2, "VRAM")
        bar_y = vram_y + 4
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(35, 38, 50))
        painter.drawRoundedRect(x, bar_y, width - 6, 16, 3, 3)
        utilization = vram.get("utilization", 0.0)
        painter.setBrush(_heatmap_color(utilization))
        painter.drawRoundedRect(x, bar_y, int((width - 6) * utilization), 16, 3, 3)
        painter.setPen(QPen(DEBUG_FG))
        used_mib = vram.get("used_bytes", 0) / 1024 / 1024
        total_mib = vram.get("capacity_bytes", 0) / 1024 / 1024
        painter.drawText(
            x + 4,
            bar_y + 12,
            f"{used_mib:5.1f} / {total_mib:5.1f} MiB",
        )

        # Stats line
        stats_y = bar_y + 30
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(
            x + 4,
            stats_y,
            f"已提交 {snapshot.get('kernels_submitted', 0)} · 已完成 {snapshot.get('kernels_completed', 0)}",
        )

    def _draw_kernel_arrow(
        self, painter: QPainter, cpu_right_x: int, gpu_x: int, line_height: int
    ) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF

        arrow_y = 30 + 12
        start = QPointF(cpu_right_x - 4, arrow_y)
        end = QPointF(gpu_x + 4, arrow_y)
        painter.setPen(QPen(QColor(255, 200, 100), 2))
        painter.drawLine(start, end)
        # arrowhead
        head = QPolygonF(
            [
                QPointF(end.x(), end.y()),
                QPointF(end.x() - 6, end.y() - 4),
                QPointF(end.x() - 6, end.y() + 4),
            ]
        )
        painter.setBrush(QColor(255, 200, 100))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(head)
        painter.setPen(QPen(QColor(255, 200, 100)))
        painter.drawText(int((start.x() + end.x()) / 2 - 16), arrow_y - 4, "kernel")


def _styled_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setStyleSheet(
        """
        QPushButton {
            background: rgba(50, 56, 74, 210);
            color: rgb(220, 224, 236);
            border: 1px solid rgba(120, 180, 255, 120);
            border-radius: 3px;
            padding: 2px 8px;
            font-size: 10px;
        }
        QPushButton:hover { background: rgba(70, 90, 140, 230); }
        QPushButton:pressed { background: rgba(90, 120, 170, 230); }
        """
    )
    return button


# ---------------------------------------------------------------------------
# trace table — Tiny8-style cycle-by-cycle CPU + GPU view
# ---------------------------------------------------------------------------
TRACE_COLUMNS: tuple[str, ...] = (
    "Cycle",
    "PC",
    "指令",
    "SREG",
    "暫存器變動",
    "GPU 階段",
)

CHANGE_HIGHLIGHT_COLOR = QColor(255, 210, 120, 90)  # warm cell background
STALL_FOREGROUND_COLOR = QColor(180, 180, 180)
HALT_FOREGROUND_COLOR = QColor(255, 110, 110)


# Colors used to tint trace rows by event kind (KLAUNCH / KWAIT / HALT / …).
EVENT_BACKGROUND_COLORS: dict[EventKind, QColor] = {
    EventKind.NORMAL: QColor(0, 0, 0, 0),
    EventKind.KLAUNCH: QColor(255, 170, 60, 70),       # 橘
    EventKind.KSTAT: QColor(180, 220, 110, 60),        # 淺綠
    EventKind.KWAIT: QColor(120, 180, 255, 80),        # 藍
    EventKind.KWAIT_STALL: QColor(120, 130, 150, 70),  # 灰
    EventKind.HALT: QColor(255, 110, 110, 90),         # 紅
    EventKind.JUMP: QColor(200, 160, 240, 60),         # 紫
    EventKind.BRANCH: QColor(220, 200, 100, 50),       # 黃
    EventKind.MEMORY: QColor(120, 220, 200, 50),       # 青
}


class TraceTable(QWidget):
    """Scrollable Tiny8-style table that displays one row per cycle.

    Each row is now color-coded by event kind (KLAUNCH / KWAIT / HALT…),
    and a ← badge in the rightmost column says what the event means.
    Rows are also clickable: selecting one fires :attr:`row_selected`,
    which the main widget uses for time-travel(全 view 同步顯示那一格).
    """

    row_selected = Signal(int)  # 1-based cycle index from the trace row

    EXTRA_COLUMN_LABEL = "事件 / 說明"

    def __init__(self, max_rows: int = 4096, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_rows = max_rows
        self._previous_row: TraceRow | None = None
        self._row_metadata: list[dict] = []  # one entry per visible row, used by row_selected
        column_labels = [*TRACE_COLUMNS, self.EXTRA_COLUMN_LABEL]
        self._table = QTableWidget(0, len(column_labels))
        self._table.setHorizontalHeaderLabels(column_labels)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(
            """
            QTableWidget {
                background: rgba(20, 22, 30, 200);
                color: rgb(220, 224, 236);
                gridline-color: rgba(80, 90, 110, 100);
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10px;
                border: 1px solid rgba(90, 100, 130, 120);
                border-radius: 4px;
            }
            QHeaderView::section {
                background: rgba(40, 46, 64, 220);
                color: rgb(200, 210, 230);
                padding: 2px 6px;
                border: none;
            }
            QTableWidget::item:selected {
                background: rgba(120, 180, 255, 110);
            }
            """
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # public mutations
    # ------------------------------------------------------------------
    def append_row(self, trace_row: TraceRow) -> None:
        row_index = self._table.rowCount()
        classification = classify_row(
            instruction_text=trace_row.instruction_text,
            port_writes=trace_row.port_writes,
            cpu_halted=trace_row.cpu_halted,
            cpu_stalled=trace_row.cpu_stalled,
        )
        self._table.insertRow(row_index)
        cells = self._format_cells(trace_row, classification)
        previous_cells = (
            self._format_cells(self._previous_row, None) if self._previous_row else None
        )
        background = EVENT_BACKGROUND_COLORS.get(classification.kind, QColor(0, 0, 0, 0))
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setTextAlignment(
                Qt.AlignCenter if column in (0, 1, 3) else Qt.AlignLeft | Qt.AlignVCenter
            )
            if (
                previous_cells is not None
                and column < len(previous_cells)
                and previous_cells[column] != text
                and column not in (0, len(cells) - 1)
            ):
                item.setBackground(QBrush(CHANGE_HIGHLIGHT_COLOR))
            elif background.alpha() > 0:
                item.setBackground(QBrush(background))
            if trace_row.cpu_stalled:
                item.setForeground(QBrush(STALL_FOREGROUND_COLOR))
            elif trace_row.cpu_halted:
                item.setForeground(QBrush(HALT_FOREGROUND_COLOR))
            self._table.setItem(row_index, column, item)
        self._table.scrollToBottom()
        self._previous_row = trace_row
        self._row_metadata.append(
            {
                "cycle": trace_row.cycle,
                "kind": classification.kind.value,
                "instruction": trace_row.instruction_text,
            }
        )
        excess_rows = self._table.rowCount() - self._max_rows
        for _ in range(max(0, excess_rows)):
            self._table.removeRow(0)
            if self._row_metadata:
                self._row_metadata.pop(0)

    def reset(self) -> None:
        self._table.setRowCount(0)
        self._previous_row = None
        self._row_metadata.clear()

    def row_count(self) -> int:
        return self._table.rowCount()

    def selected_cycle(self) -> int | None:
        row = self._table.currentRow()
        if 0 <= row < len(self._row_metadata):
            return self._row_metadata[row]["cycle"]
        return None

    def select_cycle(self, cycle: int) -> None:
        for row_index, meta in enumerate(self._row_metadata):
            if meta["cycle"] == cycle:
                self._table.selectRow(row_index)
                self._table.scrollToItem(self._table.item(row_index, 0))
                return

    def select_first(self) -> None:
        if self._row_metadata:
            self._table.selectRow(0)

    def select_last(self) -> None:
        last = self._table.rowCount() - 1
        if last >= 0:
            self._table.selectRow(last)
            self._table.scrollToItem(self._table.item(last, 0))

    def select_relative(self, delta: int) -> None:
        if not self._row_metadata:
            return
        current = self._table.currentRow()
        if current < 0:
            current = self._table.rowCount() - 1
        target = max(0, min(self._table.rowCount() - 1, current + delta))
        self._table.selectRow(target)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        cycle = self.selected_cycle()
        if cycle is not None:
            self.row_selected.emit(int(cycle))

    @staticmethod
    def _format_cells(
        trace_row: TraceRow, classification
    ) -> tuple[str, str, str, str, str, str, str]:
        register_changes_text = (
            ", ".join(f"R{index}={value}" for index, value in trace_row.register_changes)
            if trace_row.register_changes
            else "—"
        )
        badge = classification.badge_text if classification is not None else ""
        return (
            f"C{trace_row.cycle:04d}",
            f"{trace_row.pc:02X}",
            trace_row.instruction_text,
            trace_row.sreg_text,
            register_changes_text,
            trace_row.gpu_summary,
            badge,
        )


# ---------------------------------------------------------------------------
# asm input panel — write a tiny program, run on the bridge
# ---------------------------------------------------------------------------
DEFAULT_ASM_PROGRAM = """; Submit two GPU kernels then wait for them to finish.
; Kernel ids:  0=vector_add  1=interpolation  2=hash  3=texture_load
;              4=idle_compression  5=app_launch  6=page_nav

    ldi r16, 0          ; vector_add id
    klaunch r16
    klaunch r16
    ldi r17, 3          ; texture_load id
    klaunch r17
    kwait               ; CPU stalls until all kernels finish
    halt
"""


class AsmInputPanel(QWidget):
    """Tiny editor + Run / Step / Reset buttons for the CPU+GPU bridge."""

    run_requested = Signal(str)
    step_requested = Signal(str)
    reset_requested = Signal()
    load_example_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._editor = QPlainTextEdit()
        self._editor.setPlainText(DEFAULT_ASM_PROGRAM)
        self._editor.setStyleSheet(
            """
            QPlainTextEdit {
                background: rgba(15, 17, 24, 220);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(90, 100, 130, 120);
                border-radius: 4px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
            }
            """
        )
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self._editor.setFont(font)

        self._run_button = _styled_button(t("btn.run"))
        self._step_button = _styled_button(t("btn.step"))
        self._reset_button = _styled_button(t("btn.reset"))
        self._example_button = _styled_button(t("btn.load_example"))
        self._run_button.setToolTip(t("tooltip.run"))
        self._step_button.setToolTip(t("tooltip.step"))
        self._reset_button.setToolTip(t("tooltip.reset"))
        self._example_button.setToolTip(t("tooltip.load_example"))
        self._status_label = QLabel(t("status.ready"))
        self._status_label.setStyleSheet(
            f"color: rgba({TEXT_DIM.red()},{TEXT_DIM.green()},{TEXT_DIM.blue()},255);"
            "font-size: 10px;"
        )

        self._run_button.clicked.connect(self._emit_run)
        self._step_button.clicked.connect(self._emit_step)
        self._reset_button.clicked.connect(self.reset_requested.emit)
        self._example_button.clicked.connect(self.load_example_requested.emit)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(4)
        button_row.addWidget(self._run_button)
        button_row.addWidget(self._step_button)
        button_row.addWidget(self._reset_button)
        button_row.addStretch(1)
        button_row.addWidget(self._example_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._editor, 1)
        layout.addLayout(button_row)
        layout.addWidget(self._status_label)

    def set_status(self, message: str, *, error: bool = False) -> None:
        color = (
            QColor(255, 110, 110) if error else TEXT_DIM
        )
        self._status_label.setStyleSheet(
            f"color: rgba({color.red()},{color.green()},{color.blue()},255);"
            "font-size: 10px;"
        )
        self._status_label.setText(message)

    def set_program_text(self, text: str) -> None:
        self._editor.setPlainText(text)

    def program_text(self) -> str:
        return self._editor.toPlainText()

    def _emit_run(self) -> None:
        self.run_requested.emit(self.program_text())

    def _emit_step(self) -> None:
        self.step_requested.emit(self.program_text())


# ---------------------------------------------------------------------------
# Tiny8 CLI-style debugger view (black background, register grid, memory grid)
# ---------------------------------------------------------------------------
DEBUG_BG = QColor(0, 0, 0)
DEBUG_FG = QColor(220, 224, 236)
DEBUG_DIM = QColor(110, 116, 132)
DEBUG_CHANGE = QColor(255, 220, 100)
DEBUG_FLAG_SET = QColor(120, 220, 140)
DEBUG_BORDER = QColor(60, 70, 90)
DEBUG_PC = QColor(255, 180, 90)


class DebugView(QWidget):
    """Black-background curses-style register / memory dump.

    Reads the most recent :class:`~gpu_simulator.bridge.TraceRow` plus the
    bridge's :attr:`register_history` / :attr:`memory_history` to know
    the current full state.  Cells whose value differs from the
    previous cycle are rendered in the highlight colour.
    """

    MEMORY_DEFAULT_RANGE: tuple[int, int] = (0x60, 0x80)  # matches Tiny8 example

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._registers: tuple[int, ...] = tuple(0 for _ in range(32))
        self._previous_registers: tuple[int, ...] = self._registers
        self._memory: tuple[int, ...] = tuple(0 for _ in range(256))
        self._previous_memory: tuple[int, ...] = self._memory
        self._memory_start, self._memory_end = self.MEMORY_DEFAULT_RANGE
        self._sreg_text = "----"
        self._previous_sreg_text = "----"
        self._cycle = 0
        self._pc = 0
        self._instruction_text = "(no program)"
        self._cpu_halted = False
        self._cpu_stalled = False

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def update_state(
        self,
        *,
        cycle: int,
        pc: int,
        instruction_text: str,
        sreg_text: str,
        registers: tuple[int, ...],
        memory: tuple[int, ...],
        previous_registers: tuple[int, ...] | None,
        previous_memory: tuple[int, ...] | None,
        previous_sreg_text: str | None,
        cpu_halted: bool = False,
        cpu_stalled: bool = False,
    ) -> None:
        self._cycle = cycle
        self._pc = pc
        self._instruction_text = instruction_text
        self._sreg_text = sreg_text
        self._registers = registers
        self._previous_registers = previous_registers or registers
        self._memory = memory
        self._previous_memory = previous_memory or memory
        self._previous_sreg_text = previous_sreg_text or sreg_text
        self._cpu_halted = cpu_halted
        self._cpu_stalled = cpu_stalled
        self.update()

    def set_memory_window(self, start: int, end: int) -> None:
        self._memory_start = max(0, start)
        self._memory_end = min(len(self._memory), end)
        self.update()

    def reset(self) -> None:
        self._registers = tuple(0 for _ in range(32))
        self._previous_registers = self._registers
        self._memory = tuple(0 for _ in range(256))
        self._previous_memory = self._memory
        self._sreg_text = "----"
        self._previous_sreg_text = "----"
        self._cycle = 0
        self._pc = 0
        self._instruction_text = "(no program)"
        self._cpu_halted = False
        self._cpu_stalled = False
        self.update()

    # ------------------------------------------------------------------
    # painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), DEBUG_BG)

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        line_height = metrics.height() + 2
        char_width = metrics.horizontalAdvance("0")

        cursor_y = 6
        cursor_y = self._draw_status_line(painter, cursor_y, line_height)
        cursor_y += 4
        cursor_y = self._draw_sreg_strip(painter, cursor_y, line_height, char_width)
        cursor_y += 4
        cursor_y = self._draw_register_grid(painter, cursor_y, line_height, char_width)
        cursor_y += 4
        self._draw_memory_grid(painter, cursor_y, line_height, char_width)

    # ------------------------------------------------------------------
    # painting helpers
    # ------------------------------------------------------------------
    def _draw_status_line(self, painter: QPainter, y: int, line_height: int) -> int:
        if self._cpu_halted and not self._cpu_stalled:
            indicator_color = QColor(255, 110, 110)
            indicator_text = t("status.halted_indicator")
        elif self._cpu_stalled:
            indicator_color = QColor(180, 200, 230)
            indicator_text = t("status.kwait_indicator")
        else:
            indicator_color = QColor(120, 220, 140)
            indicator_text = t("status.running_indicator")

        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, y + line_height - 4, "Step")
        painter.setPen(QPen(DEBUG_FG))
        painter.drawText(40, y + line_height - 4, f"{self._cycle:>5}")

        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(96, y + line_height - 4, "PC")
        painter.setPen(QPen(DEBUG_PC))
        painter.drawText(120, y + line_height - 4, f"0x{self._pc:04X}")

        painter.setPen(QPen(indicator_color))
        painter.drawText(self.width() - 220, y + line_height - 4, indicator_text)

        instruction_y = y + line_height + 2
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, instruction_y + line_height - 4, "指令")
        painter.setPen(QPen(DEBUG_FG))
        painter.drawText(
            40,
            instruction_y + line_height - 4,
            self._instruction_text[: max(1, (self.width() - 60) // 8)],
        )
        return instruction_y + line_height

    def _draw_sreg_strip(
        self, painter: QPainter, y: int, line_height: int, char_width: int
    ) -> int:
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, y + line_height - 4, "SREG")
        flag_names = ("Z", "N", "C", "V")
        x = 50
        for index, flag_name in enumerate(flag_names):
            is_set = (
                index < len(self._sreg_text)
                and self._sreg_text[index] != "-"
            )
            was_set = (
                index < len(self._previous_sreg_text)
                and self._previous_sreg_text[index] != "-"
            )
            cell_width = char_width * 4
            cell_rect_color = (
                DEBUG_CHANGE if is_set != was_set else DEBUG_BORDER
            )
            painter.setPen(QPen(cell_rect_color))
            painter.setBrush(DEBUG_FLAG_SET if is_set else DEBUG_BG)
            painter.drawRect(x, y + 2, cell_width, line_height - 2)
            painter.setPen(QPen(DEBUG_BG if is_set else DEBUG_FG))
            painter.drawText(
                x + cell_width // 2 - char_width // 2,
                y + line_height - 4,
                flag_name,
            )
            x += cell_width + 4
        return y + line_height

    def _draw_register_grid(
        self, painter: QPainter, y: int, line_height: int, char_width: int
    ) -> int:
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, y + line_height - 4, "暫存器 R0–R31")
        y += line_height
        cols = 8
        rows = 4
        cell_width = char_width * 9
        cell_height = line_height + 2
        margin_left = 8
        for row in range(rows):
            for col in range(cols):
                index = row * cols + col
                if index >= len(self._registers):
                    continue
                value = self._registers[index]
                previous_value = (
                    self._previous_registers[index]
                    if index < len(self._previous_registers)
                    else value
                )
                changed = value != previous_value
                cell_x = margin_left + col * cell_width
                cell_y = y + row * cell_height
                painter.setPen(QPen(DEBUG_BORDER))
                painter.setBrush(DEBUG_CHANGE if changed else DEBUG_BG)
                painter.drawRect(cell_x, cell_y, cell_width - 4, cell_height - 2)
                painter.setPen(QPen(DEBUG_BG if changed else DEBUG_DIM))
                painter.drawText(cell_x + 4, cell_y + line_height - 4, f"R{index:02}")
                painter.setPen(QPen(DEBUG_BG if changed else DEBUG_FG))
                painter.drawText(
                    cell_x + cell_width - char_width * 4,
                    cell_y + line_height - 4,
                    f"{value:3}",
                )
        return y + rows * cell_height

    def _draw_memory_grid(
        self, painter: QPainter, y: int, line_height: int, char_width: int
    ) -> None:
        painter.setPen(QPen(DEBUG_DIM))
        title = (
            f"記憶體 0x{self._memory_start:02X}–0x{self._memory_end - 1:02X}"
        )
        painter.drawText(8, y + line_height - 4, title)
        y += line_height
        cols = 16
        margin_left = 8
        cell_width = char_width * 4
        cell_height = line_height + 2
        addresses = range(self._memory_start, self._memory_end)
        for offset, address in enumerate(addresses):
            row = offset // cols
            col = offset % cols
            value = self._memory[address] if address < len(self._memory) else 0
            previous_value = (
                self._previous_memory[address]
                if address < len(self._previous_memory)
                else value
            )
            changed = value != previous_value
            cell_x = margin_left + 30 + col * cell_width  # 30 px reserved for the row label
            cell_y = y + row * cell_height
            painter.setPen(QPen(DEBUG_BORDER))
            painter.setBrush(DEBUG_CHANGE if changed else DEBUG_BG)
            painter.drawRect(cell_x, cell_y, cell_width - 2, cell_height - 2)
            painter.setPen(QPen(DEBUG_BG if changed else DEBUG_FG))
            painter.drawText(cell_x + 2, cell_y + line_height - 4, f"{value:02X}")
            if col == 0:
                painter.setPen(QPen(DEBUG_DIM))
                painter.drawText(
                    margin_left,
                    cell_y + line_height - 4,
                    f"0x{address:02X}",
                )


# ---------------------------------------------------------------------------
# matplotlib heatmap view (Tiny8 animation style)
# ---------------------------------------------------------------------------
class HeatmapView(QWidget):
    """Three-layer Tiny8-animation-style heatmap rendered with matplotlib.

    The widget reads the bridge's snapshot histories and renders three
    stacked subplots:

    1. SREG flag strip across all recorded steps.
    2. Register heatmap (R0..R31 vs step, value as colour).
    3. Memory heatmap (default address window 0x60..0x7F vs step).
    """

    DEFAULT_MEMORY_RANGE: tuple[int, int] = (0x60, 0x80)
    REDRAW_EVERY: int = 4

    def __init__(
        self,
        memory_range: tuple[int, int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._memory_range = memory_range or self.DEFAULT_MEMORY_RANGE
        self._update_counter = 0
        self._title_label = QLabel("Step —, PC —, 指令 —")
        self._title_label.setStyleSheet(
            "color: rgba(220, 224, 236, 230); font-family: Consolas, monospace;"
            "font-size: 10px;"
        )
        self._canvas = None
        self._figure = None
        self._sreg_axis = None
        self._register_axis = None
        self._memory_axis = None
        self._error_label: QLabel | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title_label)

        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
        except ImportError:
            self._error_label = QLabel(
                "matplotlib is not installed — run `pip install matplotlib` "
                "to enable the heatmap view."
            )
            self._error_label.setWordWrap(True)
            self._error_label.setStyleSheet(
                f"color: rgba({TEXT_DIM.red()},{TEXT_DIM.green()},{TEXT_DIM.blue()},255);"
            )
            layout.addWidget(self._error_label)
            return

        self._figure = Figure(figsize=(5.0, 5.5), tight_layout=True, facecolor="#0a0c14")
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setStyleSheet("background: transparent;")
        self._sreg_axis = self._figure.add_subplot(3, 1, 1)
        self._register_axis = self._figure.add_subplot(3, 1, 2)
        self._memory_axis = self._figure.add_subplot(3, 1, 3)
        for axis in (self._sreg_axis, self._register_axis, self._memory_axis):
            axis.set_facecolor("#000000")
        layout.addWidget(self._canvas)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def update_history(
        self,
        register_history: list[tuple[int, ...]],
        memory_history: list[tuple[int, ...]],
        sreg_history: list[str],
        latest_pc: int,
        latest_instruction: str,
    ) -> None:
        if self._canvas is None or not register_history:
            return
        self._update_counter += 1
        if self._update_counter % self.REDRAW_EVERY != 0:
            return
        self._title_label.setText(
            f"Step {len(register_history)}, PC 0x{latest_pc:04X}, "
            f"指令 {latest_instruction[:40]}"
        )
        self._draw_sreg(sreg_history)
        self._draw_registers(register_history)
        self._draw_memory(memory_history)
        self._canvas.draw_idle()

    def reset(self) -> None:
        self._update_counter = 0
        if self._sreg_axis is not None:
            self._sreg_axis.clear()
        if self._register_axis is not None:
            self._register_axis.clear()
        if self._memory_axis is not None:
            self._memory_axis.clear()
        if self._canvas is not None:
            self._canvas.draw_idle()
        self._title_label.setText("Step —, PC —, 指令 —")

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def _draw_sreg(self, sreg_history: list[str]) -> None:
        import numpy as np

        flag_names = ("Z", "N", "C", "V")
        matrix = np.zeros((len(flag_names), max(1, len(sreg_history))), dtype=float)
        for column, text in enumerate(sreg_history):
            for row in range(len(flag_names)):
                if row < len(text) and text[row] != "-":
                    matrix[row, column] = 1.0
        axis = self._sreg_axis
        axis.clear()
        axis.set_facecolor("#000000")
        axis.imshow(matrix, aspect="auto", cmap="inferno", interpolation="nearest")
        axis.set_yticks(range(len(flag_names)))
        axis.set_yticklabels(flag_names, color="#cfd2dc", fontsize=7)
        axis.set_xticks([])
        axis.set_title("SREG 旗標", color="#cfd2dc", fontsize=8)
        for spine in axis.spines.values():
            spine.set_color("#3a3f4f")

    def _draw_registers(self, register_history: list[tuple[int, ...]]) -> None:
        import numpy as np

        matrix = np.array(register_history, dtype=float).T  # rows=registers, cols=steps
        axis = self._register_axis
        axis.clear()
        axis.set_facecolor("#000000")
        axis.imshow(matrix, aspect="auto", cmap="inferno", vmin=0, vmax=255, interpolation="nearest")
        axis.set_ylabel("暫存器", color="#cfd2dc", fontsize=8)
        axis.set_yticks(list(range(0, 32, 4)))
        axis.set_yticklabels([f"R{i}" for i in range(0, 32, 4)], color="#cfd2dc", fontsize=7)
        axis.tick_params(axis="x", colors="#cfd2dc", labelsize=7)
        for spine in axis.spines.values():
            spine.set_color("#3a3f4f")

    def _draw_memory(self, memory_history: list[tuple[int, ...]]) -> None:
        import numpy as np

        if not memory_history:
            return
        start, end = self._memory_range
        sliced = [snapshot[start:end] for snapshot in memory_history]
        matrix = np.array(sliced, dtype=float).T
        axis = self._memory_axis
        axis.clear()
        axis.set_facecolor("#000000")
        axis.imshow(matrix, aspect="auto", cmap="inferno", vmin=0, vmax=255, interpolation="nearest")
        axis.set_ylabel("記憶體", color="#cfd2dc", fontsize=8)
        tick_positions = list(range(0, end - start, 4))
        axis.set_yticks(tick_positions)
        axis.set_yticklabels(
            [f"0x{start + offset:02X}" for offset in tick_positions],
            color="#cfd2dc",
            fontsize=7,
        )
        axis.set_xlabel("Step(Cycle 數)", color="#cfd2dc", fontsize=8)
        axis.tick_params(axis="x", colors="#cfd2dc", labelsize=7)
        for spine in axis.spines.values():
            spine.set_color("#3a3f4f")


# ===========================================================================
# Live commentary panel — Chinese narration of every trace row
# ===========================================================================
class LiveCommentaryPanel(QFrame):
    """側欄,持續吐出每個 cycle 的中文白話解說。

    UI 接收 :class:`~gpu_simulator.bridge.TraceRow`,內部用
    :class:`~gpu_simulator.commentary.Commentator` 翻成中文後追加進
    QListWidget。也保留純文字 export 方法,給匯出 Markdown 報告用。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self._commentator = Commentator()
        self._list_widget = QListWidget(self)
        self._list_widget.setStyleSheet(
            """
            QListWidget {
                background: rgba(20, 22, 30, 200);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(120, 180, 255, 100);
                border-radius: 4px;
                font-size: 11px;
            }
            QListWidget::item { padding: 3px 6px; }
            """
        )
        title = QLabel("📖 中文導讀(自動產生)")
        title.setStyleSheet(
            "color: rgba(220, 224, 236, 230); font-weight: bold; font-size: 11px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(title)
        layout.addWidget(self._list_widget, 1)

    def append_row(self, trace_row: TraceRow) -> None:
        line = self._commentator.narrate(trace_row)
        item = QListWidgetItem(f"C{trace_row.cycle:04d}  {line}")
        # 同樣按事件類型染色,讓側欄與 trace 表呼應
        classification = classify_row(
            instruction_text=trace_row.instruction_text,
            port_writes=trace_row.port_writes,
            cpu_halted=trace_row.cpu_halted,
            cpu_stalled=trace_row.cpu_stalled,
        )
        bg = EVENT_BACKGROUND_COLORS.get(classification.kind, QColor(0, 0, 0, 0))
        if bg.alpha() > 0:
            item.setBackground(QBrush(bg))
        self._list_widget.addItem(item)
        self._list_widget.scrollToBottom()
        overflow = self._list_widget.count() - 400
        for _ in range(max(0, overflow)):
            self._list_widget.takeItem(0)

    def reset(self) -> None:
        self._commentator.reset()
        self._list_widget.clear()


# ===========================================================================
# Sequence diagram — UML-style CPU lane / GPU lane with KLAUNCH arrows
# ===========================================================================
@dataclass(frozen=True)
class SequenceEvent:
    """One marker on the sequence diagram."""

    cycle: int
    kind: EventKind
    label: str


class SequenceDiagramView(QWidget):
    """CPU 跟 GPU 兩條時間 lane,KLAUNCH / KWAIT / kernel-done 用箭頭呈現。

    讀的就是 trace rows + GPU snapshot,自畫出來。
    最近 N 個 cycle 在右側,往左是更早的歷史。
    """

    DEFAULT_WINDOW: int = 80  # 顯示最近多少 cycle
    LANE_HEIGHT: int = 36
    HEADER_HEIGHT: int = 30

    def __init__(self, window: int | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self._window = window or self.DEFAULT_WINDOW
        self._cpu_events: list[SequenceEvent] = []
        self._kernel_arrows: list[tuple[int, int, str]] = []  # (start_cycle, kernel_id, kernel_label)
        self._completion_arrows: list[int] = []  # cycle when GPU finished a kernel
        self._latest_cycle: int = 0
        self._highlighted_cycle: int | None = None
        self._previous_kernels_completed: int = 0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def append_row(self, trace_row: TraceRow, gpu_snapshot: dict | None = None) -> None:
        cycle = int(trace_row.cycle)
        classification = classify_row(
            instruction_text=trace_row.instruction_text,
            port_writes=trace_row.port_writes,
            cpu_halted=trace_row.cpu_halted,
            cpu_stalled=trace_row.cpu_stalled,
        )
        self._cpu_events.append(
            SequenceEvent(
                cycle=cycle,
                kind=classification.kind,
                label=trace_row.instruction_text or "",
            )
        )
        for port, value in trace_row.port_writes:
            if port == 0x40:
                kernel_idx = value & 0xFF
                kernel_id_text = f"id={kernel_idx}"
                self._kernel_arrows.append((cycle, kernel_idx, kernel_id_text))
        if gpu_snapshot is not None:
            now_completed = int(gpu_snapshot.get("kernels_completed", 0))
            for _ in range(self._previous_kernels_completed, now_completed):
                self._completion_arrows.append(cycle)
            self._previous_kernels_completed = now_completed
        self._latest_cycle = cycle
        self.update()

    def reset(self) -> None:
        self._cpu_events.clear()
        self._kernel_arrows.clear()
        self._completion_arrows.clear()
        self._latest_cycle = 0
        self._highlighted_cycle = None
        self._previous_kernels_completed = 0
        self.update()

    def highlight_cycle(self, cycle: int | None) -> None:
        self._highlighted_cycle = cycle
        self.update()

    # ------------------------------------------------------------------
    # painting
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(15, 17, 24, 230))
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        painter.setFont(font)

        width = self.width()
        height = self.height()
        # lanes
        cpu_lane_y = self.HEADER_HEIGHT + 14
        gpu_lane_y = cpu_lane_y + self.LANE_HEIGHT + 14

        # axis area
        margin_left = 60
        plot_width = max(20, width - margin_left - 12)
        if self._latest_cycle <= 0:
            painter.setPen(QPen(TEXT_DIM))
            painter.drawText(20, height // 2, "尚未執行 — 請從 Input 分頁載入範例並按執行")
            return

        start_cycle = max(0, self._latest_cycle - self._window)
        cycle_span = max(1, self._latest_cycle - start_cycle)

        def cycle_to_x(cycle: int) -> int:
            return margin_left + int(plot_width * (cycle - start_cycle) / cycle_span)

        # lane labels
        painter.setPen(QPen(QColor(255, 200, 100)))
        painter.drawText(8, cpu_lane_y - 16, "Tiny8 CPU")
        painter.setPen(QPen(QColor(120, 220, 140)))
        painter.drawText(8, gpu_lane_y - 16, "虛擬 GPU")

        # baseline lanes
        painter.setPen(QPen(QColor(80, 90, 110), 1, Qt.DashLine))
        painter.drawLine(margin_left, cpu_lane_y, width - 4, cpu_lane_y)
        painter.drawLine(margin_left, gpu_lane_y, width - 4, gpu_lane_y)

        # CPU events as small ticks
        for event_obj in self._cpu_events:
            if event_obj.cycle < start_cycle:
                continue
            x = cycle_to_x(event_obj.cycle)
            color = EVENT_BACKGROUND_COLORS.get(event_obj.kind, QColor(180, 200, 230))
            tick_color = QColor(color.red(), color.green(), color.blue(), 220)
            painter.setPen(QPen(tick_color, 2))
            painter.drawLine(x, cpu_lane_y - 6, x, cpu_lane_y + 6)

        # KLAUNCH arrows: down from CPU lane to GPU lane
        for cycle, kernel_id, _label in self._kernel_arrows:
            if cycle < start_cycle:
                continue
            x = cycle_to_x(cycle)
            painter.setPen(QPen(QColor(255, 200, 100), 1.4))
            painter.drawLine(x, cpu_lane_y + 4, x, gpu_lane_y - 4)
            # arrow head
            painter.setBrush(QColor(255, 200, 100))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(
                [
                    QPoint(x, gpu_lane_y - 4),
                    QPoint(x - 4, gpu_lane_y - 10),
                    QPoint(x + 4, gpu_lane_y - 10),
                ]
            )
            painter.setPen(QPen(QColor(255, 200, 100)))
            painter.drawText(x - 12, gpu_lane_y - 12, f"k{kernel_id}")

        # kernel completion arrows: up from GPU back to CPU
        for cycle in self._completion_arrows:
            if cycle < start_cycle:
                continue
            x = cycle_to_x(cycle)
            painter.setPen(QPen(QColor(120, 220, 140), 1.2, Qt.DotLine))
            painter.drawLine(x, gpu_lane_y - 4, x, cpu_lane_y + 4)
            painter.setBrush(QColor(120, 220, 140))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(
                [
                    QPoint(x, cpu_lane_y + 4),
                    QPoint(x - 4, cpu_lane_y + 10),
                    QPoint(x + 4, cpu_lane_y + 10),
                ]
            )

        # highlighted cycle (when user picked a row in Trace)
        if self._highlighted_cycle is not None and self._highlighted_cycle >= start_cycle:
            x = cycle_to_x(self._highlighted_cycle)
            painter.setPen(QPen(QColor(255, 240, 120, 200), 1.5))
            painter.drawLine(x, self.HEADER_HEIGHT, x, height - 12)

        # cycle scale at the bottom
        painter.setPen(QPen(TEXT_DIM))
        for marker in (start_cycle, (start_cycle + self._latest_cycle) // 2, self._latest_cycle):
            x = cycle_to_x(marker)
            painter.drawLine(x, gpu_lane_y + 14, x, gpu_lane_y + 18)
            painter.drawText(x - 16, gpu_lane_y + 30, f"C{marker:04d}")


# ===========================================================================
# Memory map — visual diagram of the 256-byte address space
# ===========================================================================
class MemoryMapView(QWidget):
    """畫整片 256 byte 記憶體地圖,標示 GPU 控制暫存器在哪裡。

    供使用者一眼看出:
    - 0x40 / 0x41 / 0xFF 是 GPU 控制(寫入會觸發 GPU 工作)
    - 0x60..0x7F 是「使用者資料區」(範例都用這段)
    - 其餘是一般 RAM
    """

    GPU_PORTS: tuple[tuple[int, str, QColor], ...] = (
        (0x40, "GPU.LAUNCH", QColor(255, 170, 60, 220)),
        (0x41, "GPU.HINT", QColor(180, 220, 110, 200)),
        (0xFF, "GPU.KWAIT", QColor(120, 180, 255, 220)),
    )
    USER_DATA_RANGE: tuple[int, int] = (0x60, 0x80)
    CELLS_PER_ROW: int = 16

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._memory: tuple[int, ...] = tuple(0 for _ in range(256))
        self._previous_memory: tuple[int, ...] = self._memory
        self._recently_accessed: dict[int, int] = {}  # address → recency counter

    def update_memory(
        self,
        memory: tuple[int, ...],
        previous_memory: tuple[int, ...] | None = None,
    ) -> None:
        prev = previous_memory if previous_memory is not None else self._memory
        self._previous_memory = prev
        self._memory = memory
        # decay recency
        for address in list(self._recently_accessed):
            self._recently_accessed[address] -= 1
            if self._recently_accessed[address] <= 0:
                del self._recently_accessed[address]
        # mark changed addresses as just-accessed
        for index, (current, before) in enumerate(zip(memory, prev, strict=False)):
            if current != before:
                self._recently_accessed[index] = 4
        self.update()

    def reset(self) -> None:
        self._memory = tuple(0 for _ in range(256))
        self._previous_memory = self._memory
        self._recently_accessed.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(15, 17, 24, 230))
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(8)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        char_width = metrics.horizontalAdvance("0")
        line_height = metrics.height() + 2

        title = "🗺️  記憶體地圖(共 256 byte)"
        painter.setPen(QPen(TEXT_PRIMARY))
        painter.drawText(8, line_height, title)
        legend_y = line_height
        legend_x = max(220, char_width * 28)
        for address, label, color in self.GPU_PORTS:
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRect(legend_x, legend_y - line_height + 4, 10, 10)
            painter.setPen(QPen(TEXT_PRIMARY))
            painter.drawText(legend_x + 14, legend_y, f"0x{address:02X} {label}")
            legend_x += char_width * 18

        margin_left = 36
        cell_width = max(char_width * 3, (self.width() - margin_left - 8) // self.CELLS_PER_ROW)
        cell_height = line_height + 4
        start_y = line_height * 2 + 6

        for index in range(min(256, len(self._memory))):
            row = index // self.CELLS_PER_ROW
            col = index % self.CELLS_PER_ROW
            cell_x = margin_left + col * cell_width
            cell_y = start_y + row * cell_height
            value = self._memory[index]
            base_color = self._cell_base_color(index)
            if index in self._recently_accessed:
                base_color = QColor(255, 220, 100, 220)
            painter.setBrush(base_color)
            painter.setPen(QPen(QColor(60, 70, 90), 1))
            painter.drawRect(cell_x, cell_y, cell_width - 1, cell_height - 1)
            painter.setPen(
                QPen(QColor(20, 20, 20))
                if base_color.alpha() > 120
                else QPen(QColor(220, 224, 236))
            )
            painter.drawText(cell_x + 2, cell_y + line_height - 2, f"{value:02X}")
            if col == 0:
                painter.setPen(QPen(TEXT_DIM))
                painter.drawText(4, cell_y + line_height - 2, f"0x{index:02X}")

    def _cell_base_color(self, address: int) -> QColor:
        for port_addr, _, color in self.GPU_PORTS:
            if address == port_addr:
                return color
        start, end = self.USER_DATA_RANGE
        if start <= address < end:
            return QColor(70, 100, 80, 130)
        return QColor(28, 32, 44, 200)


# Re-export QPoint here so the SequenceDiagramView paintEvent can use it
# without duplicating an import block at file top (matches existing style).
from PySide6.QtCore import QPoint  # noqa: E402  -- intentionally late import


# ===========================================================================
# 第八輪 · VRAM 區塊圖(每個 kernel 的 VRAM 佔用畫成有名字的方塊)
# ===========================================================================
class VRAMBlocksWidget(QWidget):
    """畫每個 kernel 在 VRAM 上佔的位元組,而不是只把 used / total 比例做成 bar。

    每塊矩形的寬度 ∝ 該 kernel 拿走的 byte 數;
    顏色按 owner 名稱算 hash 出來,讓不同 kernel 一眼可分;
    每塊裡寫上 owner 的 short name(去掉 # 後面的流水號)。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._vram: dict = {}

    def update_snapshot(self, snapshot: dict) -> None:
        self._vram = snapshot.get("vram", {})
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(20, 22, 30, 220))
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(8)
        painter.setFont(font)

        capacity = max(1, int(self._vram.get("capacity_bytes", 1)))
        used_bytes = int(self._vram.get("used_bytes", 0))
        utilization = used_bytes / capacity if capacity else 0.0
        width = self.width()
        height = self.height()
        bar_height = max(20, height - 22)
        title_y = 12

        painter.setPen(QPen(TEXT_DIM))
        painter.drawText(
            6,
            title_y,
            f"VRAM 區塊圖 — 共 {capacity / 1024 / 1024:.0f} MiB,"
            f"佔用 {used_bytes / 1024 / 1024:5.1f} MiB ({utilization * 100:4.1f}%)",
        )

        # 底色
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(35, 38, 50))
        painter.drawRoundedRect(6, title_y + 4, width - 12, bar_height, 4, 4)

        blocks = self._vram.get("blocks") or []
        if not blocks:
            painter.setPen(QPen(TEXT_DIM))
            painter.drawText(12, title_y + bar_height // 2 + 8, "(目前沒有 GPU kernel 佔用 VRAM)")
            return

        # 從左到右排,每塊寬度 ∝ size_bytes
        x_cursor = 6
        plot_width = width - 12
        for block in blocks:
            size_bytes = int(block.get("size_bytes", 0))
            owner = str(block.get("owner", ""))
            short_name = owner.split("#", 1)[0]
            block_width = max(8, int(plot_width * size_bytes / capacity))
            color = _color_for_label(short_name)
            painter.setBrush(color)
            painter.setPen(QPen(QColor(0, 0, 0, 60), 1))
            painter.drawRoundedRect(x_cursor, title_y + 4, block_width, bar_height, 3, 3)
            painter.setPen(QPen(QColor(20, 20, 20)))
            text_to_show = short_name
            metrics = painter.fontMetrics()
            if metrics.horizontalAdvance(text_to_show) <= block_width - 4:
                painter.drawText(
                    x_cursor + 4,
                    title_y + 4 + bar_height // 2 + 4,
                    text_to_show,
                )
            x_cursor += block_width


def _color_for_label(label: str) -> QColor:
    """Stable per-string hue;同一個 kernel 名永遠拿到同一顏色。"""
    accumulator = 0
    for char in label:
        accumulator = (accumulator * 131 + ord(char)) & 0xFFFFFFFF
    hue = accumulator % 360
    color = QColor.fromHsv(hue, 170, 230)
    color.setAlpha(220)
    return color


# ===========================================================================
# 第八輪 · Warp pipeline 動畫(5 個 F/D/E/M/W 小方塊跟著 stage 移動發光)
# ===========================================================================
PIPELINE_STAGE_LETTERS: tuple[str, ...] = ("F", "D", "E", "M", "W")
PIPELINE_STAGE_NAMES: tuple[str, ...] = (
    "Fetch", "Decode", "Execute", "Memory", "Writeback"
)


class WarpPipelineAnimationWidget(QWidget):
    """每個 SM 一條橫條,每條由 4 個 warp 子條組成,每個 warp 顯示 5 階 pipeline 燈。

    亮著的那一格就是該 warp 目前所在的 pipeline stage;
    其他四格是黯淡的 placeholder。沒被使用的 warp 整條全黯。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._sms: list[dict] = []

    def update_snapshot(self, snapshot: dict) -> None:
        self._sms = snapshot.get("sms", [])
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(15, 17, 24, 230))
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(8)
        painter.setFont(font)

        if not self._sms:
            painter.setPen(QPen(TEXT_DIM))
            painter.drawText(8, 18, "(尚未啟動 GPU)")
            return

        margin_left = 32
        sm_count = len(self._sms)
        row_height = max(18, (self.height() - 6) // max(1, sm_count))
        for sm_index, sm in enumerate(self._sms):
            sm_y = 4 + sm_index * row_height
            painter.setPen(QPen(TEXT_DIM))
            painter.drawText(4, sm_y + row_height - 6, f"SM{sm.get('sm_id', sm_index)}")
            warps = sm.get("warps") or []
            if not warps:
                continue
            warp_count = len(warps)
            available_width = self.width() - margin_left - 8
            warp_width = max(60, available_width // max(1, warp_count))
            for warp_index, warp in enumerate(warps):
                warp_x = margin_left + warp_index * warp_width
                self._draw_warp(painter, warp, warp_x, sm_y, warp_width - 4, row_height - 4)

    def _draw_warp(
        self,
        painter: QPainter,
        warp: dict,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        state = warp.get("state", "idle")
        kernel_name = (warp.get("kernel") or "").split(":")[0] or warp.get("kernel", "")
        active_stage = warp.get("stage")

        stage_count = len(PIPELINE_STAGE_LETTERS)
        # leave room on the right for kernel name
        stages_max_width = max(60, int(width * 0.62))
        cell_width = max(10, stages_max_width // stage_count)
        for stage_index, stage_letter in enumerate(PIPELINE_STAGE_LETTERS):
            cell_x = x + stage_index * cell_width
            stage_name = PIPELINE_STAGE_NAMES[stage_index].lower()
            is_active = (state != "idle") and active_stage == stage_name
            if is_active:
                color = _heatmap_color(0.85)
                painter.setPen(QPen(QColor(255, 220, 100), 1))
            else:
                color = QColor(50, 56, 72) if state == "idle" else QColor(80, 88, 110)
                painter.setPen(QPen(QColor(40, 50, 65), 1))
            painter.setBrush(color)
            painter.drawRoundedRect(cell_x, y + 2, cell_width - 2, height - 4, 3, 3)
            painter.setPen(
                QPen(QColor(20, 20, 20))
                if is_active
                else QPen(QColor(140, 156, 184))
            )
            painter.drawText(cell_x + cell_width // 2 - 4, y + height - 8, stage_letter)

        # kernel label (right of the 5 stage cells)
        label_x = x + stages_max_width + 4
        label_width = width - stages_max_width - 4
        if label_width > 6:
            painter.setPen(QPen(TEXT_DIM if state == "idle" else TEXT_PRIMARY))
            label = (
                "閒置"
                if state == "idle"
                else (kernel_name or warp.get("kernel", "?"))
            )
            painter.drawText(label_x, y + height - 8, _truncate(label, label_width // 6))


# ===========================================================================
# 第八輪 · Cycle Cinema 同步劇場
# ===========================================================================
class CycleCinemaView(QWidget):
    """同框看 CPU + GPU 在每個 cycle 的合作狀況。

    上半:Tiny8 完整版 CPU 狀態(暫存器網格 + SREG)+ 左側源碼面板,目前指令高亮
    中間:KLAUNCH / KWAIT 旗標 + kernel 流向箭頭
    下半:8 顆 SM 的 warp pipeline 動畫(每 warp F/D/E/M/W 小方塊)
    最底:VCR 控制 — ⏮ ◀ 步進文字 ▶ ⏭ + 滑桿 + 播放速度

    使用方式::

        cinema.set_program(asm_source)
        cinema.set_history(register_history, memory_history, sreg_history,
                           trace_rows, gpu_snapshots)
        cinema.show_step(latest_index)
    """

    REGISTER_GRID_COLS = 8
    REGISTER_GRID_ROWS = 4

    step_changed = Signal(int)  # 1-based step number

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._program_lines: list[str] = []
        self._line_for_step: list[int] = []  # parallel to trace_rows; -1 if unknown
        self._trace_rows: list = []
        self._register_history: list[tuple[int, ...]] = []
        self._memory_history: list[tuple[int, ...]] = []
        self._sreg_history: list[str] = []
        self._gpu_snapshots: list[dict] = []
        self._current_index: int = 0  # 0-based into history
        self._is_playing: bool = False

        # ---- top: source viewer (left) + register/SREG panel (right)
        self._source_list = QListWidget()
        self._source_list.setStyleSheet(
            """
            QListWidget {
                background: rgba(12, 14, 20, 240);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(120, 180, 255, 90);
                border-radius: 4px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10px;
            }
            QListWidget::item { padding: 2px 6px; }
            QListWidget::item:selected { background: rgba(255, 220, 120, 140); color: rgb(20, 20, 20); }
            """
        )
        self._cpu_panel = _CinemaCPUPanel(self)
        top_split = QHBoxLayout()
        top_split.setContentsMargins(0, 0, 0, 0)
        top_split.setSpacing(4)
        top_split.addWidget(self._source_list, 4)
        top_split.addWidget(self._cpu_panel, 5)

        self._flow_label = QLabel("CPU ⇄ GPU 沒有資料流")
        self._flow_label.setStyleSheet(
            "color: rgba(220, 224, 236, 230); padding: 2px 4px;"
            "font-family: Consolas, monospace; font-size: 10px;"
        )

        self._warp_pipeline_widget = WarpPipelineAnimationWidget(self)

        # ---- VCR controls
        self._first_button = _styled_button("⏮ 首")
        self._prev_button = _styled_button("◀ 上一步")
        self._play_button = _styled_button("▶ 自動播放")
        self._next_button = _styled_button("下一步 ▶")
        self._last_button = _styled_button("末 ⏭")
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._step_label = QLabel("Step 0 / 0")
        self._step_label.setStyleSheet(
            "color: rgba(220, 224, 236, 230); padding: 0 6px; font-size: 10px;"
        )
        self._first_button.clicked.connect(self._goto_first)
        self._prev_button.clicked.connect(self._goto_prev)
        self._next_button.clicked.connect(self._goto_next)
        self._last_button.clicked.connect(self._goto_last)
        self._play_button.clicked.connect(self._toggle_play)

        from PySide6.QtCore import QTimer

        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(280)
        self._auto_timer.timeout.connect(self._auto_advance)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(4)
        controls.addWidget(self._first_button)
        controls.addWidget(self._prev_button)
        controls.addWidget(self._play_button)
        controls.addWidget(self._next_button)
        controls.addWidget(self._last_button)
        controls.addWidget(self._step_label)
        controls.addWidget(self._slider, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addLayout(top_split, 5)
        layout.addWidget(self._flow_label)
        layout.addWidget(self._warp_pipeline_widget, 4)
        layout.addLayout(controls)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def set_program(self, source_text: str) -> None:
        """匯入 ASM 原始碼,左側 source list 重新填入。"""
        self._source_list.clear()
        self._program_lines = source_text.splitlines() or [""]
        for line_number, line in enumerate(self._program_lines, start=1):
            item = QListWidgetItem(f"{line_number:>3}  {line}")
            self._source_list.addItem(item)

    def set_history(
        self,
        *,
        trace_rows: list,
        register_history: list[tuple[int, ...]],
        memory_history: list[tuple[int, ...]],
        sreg_history: list[str],
        gpu_snapshots: list[dict],
        line_for_step: list[int] | None = None,
    ) -> None:
        self._trace_rows = list(trace_rows)
        self._register_history = list(register_history)
        self._memory_history = list(memory_history)
        self._sreg_history = list(sreg_history)
        self._gpu_snapshots = list(gpu_snapshots)
        self._line_for_step = list(line_for_step) if line_for_step is not None else []
        max_index = max(0, len(self._trace_rows) - 1)
        self._slider.blockSignals(True)
        self._slider.setMaximum(max_index)
        if self._current_index > max_index:
            self._current_index = max_index
        self._slider.setValue(self._current_index)
        self._slider.blockSignals(False)
        self._render_current()

    def append_one(
        self,
        *,
        trace_row,
        registers: tuple[int, ...],
        memory: tuple[int, ...],
        sreg: str,
        gpu_snapshot: dict,
        source_line_index: int = -1,
    ) -> None:
        self._trace_rows.append(trace_row)
        self._register_history.append(registers)
        self._memory_history.append(memory)
        self._sreg_history.append(sreg)
        self._gpu_snapshots.append(gpu_snapshot)
        self._line_for_step.append(source_line_index)
        max_index = max(0, len(self._trace_rows) - 1)
        self._slider.blockSignals(True)
        self._slider.setMaximum(max_index)
        if self._is_playing or self._current_index == max_index - 1:
            self._current_index = max_index
            self._slider.setValue(self._current_index)
        self._slider.blockSignals(False)
        self._render_current()

    def reset(self) -> None:
        self._auto_timer.stop()
        self._is_playing = False
        self._play_button.setText("▶ 自動播放")
        self._trace_rows.clear()
        self._register_history.clear()
        self._memory_history.clear()
        self._sreg_history.clear()
        self._gpu_snapshots.clear()
        self._line_for_step.clear()
        self._current_index = 0
        self._slider.blockSignals(True)
        self._slider.setMaximum(0)
        self._slider.setValue(0)
        self._slider.blockSignals(False)
        self._step_label.setText("Step 0 / 0")
        self._flow_label.setText("CPU ⇄ GPU 沒有資料流")
        self._cpu_panel.clear_state()
        self._source_list.clear()

    def show_step(self, index: int) -> None:
        if not self._trace_rows:
            return
        self._current_index = max(0, min(len(self._trace_rows) - 1, index))
        self._slider.blockSignals(True)
        self._slider.setValue(self._current_index)
        self._slider.blockSignals(False)
        self._render_current()

    # ------------------------------------------------------------------
    # internal: VCR + slider
    # ------------------------------------------------------------------
    def _goto_first(self) -> None:
        self.show_step(0)

    def _goto_prev(self) -> None:
        self.show_step(self._current_index - 1)

    def _goto_next(self) -> None:
        self.show_step(self._current_index + 1)

    def _goto_last(self) -> None:
        self.show_step(len(self._trace_rows) - 1)

    def _toggle_play(self) -> None:
        if self._is_playing:
            self._auto_timer.stop()
            self._is_playing = False
            self._play_button.setText("▶ 自動播放")
        else:
            self._is_playing = True
            self._play_button.setText("⏸ 暫停")
            self._auto_timer.start()

    def _auto_advance(self) -> None:
        if self._current_index >= len(self._trace_rows) - 1:
            self._auto_timer.stop()
            self._is_playing = False
            self._play_button.setText("▶ 自動播放")
            return
        self.show_step(self._current_index + 1)

    def _on_slider_changed(self, value: int) -> None:
        self.show_step(int(value))

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def _render_current(self) -> None:
        total = len(self._trace_rows)
        if total == 0:
            self._step_label.setText("Step 0 / 0")
            return
        index = self._current_index
        row = self._trace_rows[index]
        registers = self._register_history[index] if index < len(self._register_history) else ()
        memory = self._memory_history[index] if index < len(self._memory_history) else ()
        sreg = self._sreg_history[index] if index < len(self._sreg_history) else "----"
        gpu_snapshot = (
            self._gpu_snapshots[index]
            if index < len(self._gpu_snapshots)
            else {}
        )
        previous_registers = (
            self._register_history[index - 1] if index >= 1 else None
        )
        previous_memory = (
            self._memory_history[index - 1]
            if index >= 1 and index - 1 < len(self._memory_history)
            else None
        )

        self._step_label.setText(f"Step {index + 1} / {total}")
        self._cpu_panel.update_state(
            row=row,
            registers=registers,
            memory=memory,
            sreg=sreg,
            previous_registers=previous_registers,
            previous_memory=previous_memory,
        )
        self._warp_pipeline_widget.update_snapshot(gpu_snapshot)

        # source line highlight
        line_index = (
            self._line_for_step[index] if index < len(self._line_for_step) else -1
        )
        if 0 <= line_index < self._source_list.count():
            self._source_list.setCurrentRow(line_index)
            self._source_list.scrollToItem(self._source_list.item(line_index))

        # flow label
        flow_text = self._build_flow_text(row, gpu_snapshot)
        self._flow_label.setText(flow_text)
        self.step_changed.emit(index + 1)

    @staticmethod
    def _build_flow_text(row, gpu_snapshot: dict) -> str:
        port_writes = list(getattr(row, "port_writes", []))
        for port, value in port_writes:
            if port == 0x40:
                kernel_idx = value & 0xFF
                kernel_names = (
                    "vector_add", "interpolation", "hash", "texture_load",
                    "idle_compression", "app_launch", "page_nav",
                )
                kernel = kernel_names[kernel_idx % len(kernel_names)]
                return f"🚀 KLAUNCH:CPU 把 kernel id={kernel_idx} ({kernel}) 推給 GPU"
            if port == 0xFF:
                return "⏳ KWAIT:CPU 卡住,等 GPU 把所有 kernel 跑完"
            if port == 0x41:
                return f"🎯 HINT:CPU 設定下一顆 kernel 的提示值 = {value}"
        if getattr(row, "cpu_stalled", False):
            outstanding = (
                gpu_snapshot.get("kernels_submitted", 0)
                - gpu_snapshot.get("kernels_completed", 0)
            )
            return f"⏸ CPU 仍在等待…GPU 還有 {outstanding} 顆 kernel 沒跑完"
        if getattr(row, "cpu_halted", False):
            return "🏁 CPU 結束。完整流程跑完了"
        completed = gpu_snapshot.get("kernels_completed", 0)
        submitted = gpu_snapshot.get("kernels_submitted", 0)
        return f"GPU 進度:{completed} / {submitted} kernels"


# ---- helper panel for the cinema's CPU half (header + register grid) ------
class _CinemaCPUPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._row = None
        self._registers: tuple[int, ...] = tuple(0 for _ in range(32))
        self._previous_registers: tuple[int, ...] = self._registers
        self._sreg = "----"

    def update_state(
        self,
        *,
        row,
        registers: tuple[int, ...],
        memory: tuple[int, ...],  # noqa: ARG002 -- reserved for future use
        sreg: str,
        previous_registers: tuple[int, ...] | None,
        previous_memory: tuple[int, ...] | None,  # noqa: ARG002
    ) -> None:
        self._row = row
        self._registers = registers
        self._previous_registers = previous_registers or registers
        self._sreg = sreg
        self.update()

    def clear_state(self) -> None:
        self._row = None
        self._registers = tuple(0 for _ in range(32))
        self._previous_registers = self._registers
        self._sreg = "----"
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), DEBUG_BG)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(8)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        line_height = metrics.height() + 2
        char_width = metrics.horizontalAdvance("0")

        if self._row is None:
            painter.setPen(QPen(TEXT_DIM))
            painter.drawText(8, line_height, "(尚無資料 — 請先在 ASM 編輯器執行一支程式)")
            return

        # header
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, line_height, "Step")
        painter.setPen(QPen(DEBUG_FG))
        painter.drawText(40, line_height, f"{getattr(self._row, 'cycle', 0):>5}")
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(96, line_height, "PC")
        painter.setPen(QPen(DEBUG_PC))
        painter.drawText(120, line_height, f"0x{getattr(self._row, 'pc', 0):04X}")
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(168, line_height, "SREG")
        painter.setPen(QPen(DEBUG_FG))
        painter.drawText(200, line_height, self._sreg)

        instruction_y = line_height * 2 + 2
        painter.setPen(QPen(DEBUG_DIM))
        painter.drawText(8, instruction_y, "指令")
        painter.setPen(QPen(DEBUG_FG))
        painter.drawText(
            40, instruction_y, getattr(self._row, "instruction_text", "")[:60]
        )

        # 32 register grid
        grid_y = instruction_y + line_height
        cols = 8
        rows = 4
        cell_w = max(char_width * 8, (self.width() - 16) // cols)
        cell_h = line_height + 4
        for row_index in range(rows):
            for col_index in range(cols):
                index = row_index * cols + col_index
                if index >= len(self._registers):
                    continue
                value = self._registers[index]
                previous_value = (
                    self._previous_registers[index]
                    if index < len(self._previous_registers)
                    else value
                )
                changed = value != previous_value
                cell_x = 8 + col_index * cell_w
                cell_y = grid_y + row_index * cell_h
                painter.setPen(QPen(DEBUG_BORDER))
                painter.setBrush(DEBUG_CHANGE if changed else DEBUG_BG)
                painter.drawRect(cell_x, cell_y, cell_w - 4, cell_h - 2)
                painter.setPen(QPen(DEBUG_BG if changed else DEBUG_DIM))
                painter.drawText(cell_x + 4, cell_y + line_height - 2, f"R{index:02}")
                painter.setPen(QPen(DEBUG_BG if changed else DEBUG_FG))
                painter.drawText(
                    cell_x + cell_w - char_width * 4 - 4,
                    cell_y + line_height - 2,
                    f"{value:3}",
                )


# Late imports for QSlider (used only by Cinema)
from PySide6.QtWidgets import QSlider  # noqa: E402  -- intentionally late import


# ===========================================================================
# 第九輪 #2 · 等距 3D GPU 視圖(QPainter 自繪,沒 OpenGL)
# ===========================================================================
class GPU3DView(QWidget):
    """把 8 顆 SM 畫成 4×2 格的等距(isometric)立方體。

    每顆 SM 的高度 ∝ 利用率(0% = 平地、100% = 高塔),
    顏色用 heatmap 漸變;當 KLAUNCH 進來時頂上會有橘色「光球」浮現。
    """

    BLOCK_BASE_WIDTH = 64  # 每塊頂面寬
    BLOCK_BASE_DEPTH = 32  # 每塊頂面深(縱向縮短模擬透視)
    MAX_HEIGHT = 80
    GRID_COLS = 4
    GRID_ROWS = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._sms: list[dict] = []
        self._kernel_pulse: float = 0.0  # 0..1, 提交一顆 kernel 時被推到 1,自動衰減
        self._previous_kernels_submitted: int = 0

    def update_snapshot(self, snapshot: dict) -> None:
        self._sms = snapshot.get("sms", [])
        submitted = int(snapshot.get("kernels_submitted", 0))
        if submitted > self._previous_kernels_submitted:
            self._kernel_pulse = 1.0  # 一顆新 kernel → pulse 拉滿
        else:
            self._kernel_pulse = max(0.0, self._kernel_pulse - 0.1)
        self._previous_kernels_submitted = submitted
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(15, 17, 24, 240))

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QPen(TEXT_DIM))
        painter.drawText(8, 14, "🏗️ 3D GPU 視圖(等距投影 · 高塔 = 高利用率)")

        if not self._sms:
            painter.drawText(self.width() // 2 - 60, self.height() // 2, "(尚未啟動)")
            return

        # 棋盤式排,從遠到近(右下到左上),這樣前面遮後面才合理
        center_x = self.width() // 2
        baseline_y = self.height() - 50
        block_w = self.BLOCK_BASE_WIDTH
        block_d = self.BLOCK_BASE_DEPTH
        offset_x = block_w // 2  # 每排相鄰塊水平 gap
        offset_y = block_d // 2  # 每排相鄰塊垂直 gap

        rendering_order = []
        for row in range(self.GRID_ROWS):
            for col in range(self.GRID_COLS):
                index = row * self.GRID_COLS + col
                if index >= len(self._sms):
                    continue
                rendering_order.append((row, col, self._sms[index]))
        # 由後往前(row 大、col 小)畫
        rendering_order.sort(key=lambda triple: (-triple[0], -triple[1]))

        for row, col, sm in rendering_order:
            utilization = float(sm.get("utilization", 0.0))
            height_pixels = int(self.MAX_HEIGHT * utilization)
            origin_x = (
                center_x
                - (self.GRID_COLS - 1) * offset_x // 2
                + col * offset_x
                - row * offset_x // 2
            )
            origin_y = baseline_y - col * offset_y // 2 - row * offset_y
            self._draw_block(
                painter,
                origin_x=origin_x,
                origin_y=origin_y,
                width=block_w,
                depth=block_d,
                height=height_pixels,
                base_color=_heatmap_color(utilization),
                label=f"SM{sm.get('sm_id', '?')}",
                kernel_pulse=self._kernel_pulse if utilization > 0 else 0.0,
            )

    def _draw_block(
        self,
        painter: QPainter,
        *,
        origin_x: int,
        origin_y: int,
        width: int,
        depth: int,
        height: int,
        base_color: QColor,
        label: str,
        kernel_pulse: float,
    ) -> None:
        # 等距投影的三個面:頂面、左側、右側
        from PySide6.QtGui import QPolygon

        top_color = base_color
        left_color = QColor(
            max(0, base_color.red() - 40),
            max(0, base_color.green() - 40),
            max(0, base_color.blue() - 40),
        )
        right_color = QColor(
            max(0, base_color.red() - 70),
            max(0, base_color.green() - 70),
            max(0, base_color.blue() - 70),
        )

        # base 4 corners:左下、右下、右上、左上(等距)
        corner_left = QPoint(origin_x - width // 2, origin_y)
        corner_front = QPoint(origin_x, origin_y + depth // 2)
        corner_right = QPoint(origin_x + width // 2, origin_y)
        corner_back = QPoint(origin_x, origin_y - depth // 2)

        # top 4 corners(在 base 上方 height 像素)
        top_left = QPoint(corner_left.x(), corner_left.y() - height)
        top_front = QPoint(corner_front.x(), corner_front.y() - height)
        top_right = QPoint(corner_right.x(), corner_right.y() - height)
        top_back = QPoint(corner_back.x(), corner_back.y() - height)

        painter.setPen(QPen(QColor(0, 0, 0, 100), 1))

        # 左側面
        polygon = QPolygon([corner_left, corner_front, top_front, top_left])
        painter.setBrush(left_color)
        painter.drawPolygon(polygon)
        # 右側面
        polygon = QPolygon([corner_front, corner_right, top_right, top_front])
        painter.setBrush(right_color)
        painter.drawPolygon(polygon)
        # 頂面
        polygon = QPolygon([top_left, top_front, top_right, top_back])
        painter.setBrush(top_color)
        painter.drawPolygon(polygon)

        # 中文標籤
        painter.setPen(QPen(QColor(20, 20, 20)))
        painter.drawText(top_back.x() - 12, top_back.y() + 4, label)

        # KLAUNCH pulse 光球(在頂面)
        if kernel_pulse > 0:
            glow_radius = int(8 + 18 * kernel_pulse)
            color = QColor(255, 200, 80, int(180 * kernel_pulse))
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(
                top_back.x() - glow_radius // 2,
                top_back.y() - glow_radius - 4,
                glow_radius,
                glow_radius,
            )

    def reset(self) -> None:
        self._sms = []
        self._kernel_pulse = 0.0
        self._previous_kernels_submitted = 0
        self.update()


# ===========================================================================
# 第九輪 #1 · ASM 遊戲機(Conway's Life)widget
# ===========================================================================
class LifeBoardWidget(QWidget):
    """8x8 棋盤,點選格子可手動切換生死(Reset 後);跑時純顯示。"""

    cell_toggled = Signal(int, int)  # row, col

    GRID_SIZE = 8
    CELL_PADDING = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._cells: list[list[int]] = [[0] * self.GRID_SIZE for _ in range(self.GRID_SIZE)]
        self._editable = False

    def set_cells(self, cells: list[list[int]]) -> None:
        self._cells = [list(row) for row in cells]
        self.update()

    def set_editable(self, editable: bool) -> None:
        self._editable = editable

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._editable:
            return
        size = self._cell_size()
        if size <= 0:
            return
        offset_x = (self.width() - size * self.GRID_SIZE) // 2
        offset_y = (self.height() - size * self.GRID_SIZE) // 2
        local_x = event.position().x() - offset_x
        local_y = event.position().y() - offset_y
        if local_x < 0 or local_y < 0:
            return
        col = int(local_x // size)
        row = int(local_y // size)
        if 0 <= row < self.GRID_SIZE and 0 <= col < self.GRID_SIZE:
            self._cells[row][col] = 1 - self._cells[row][col]
            self.cell_toggled.emit(row, col)
            self.update()

    def _cell_size(self) -> int:
        side = min(self.width(), self.height())
        return max(8, side // (self.GRID_SIZE + 1))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(15, 17, 24, 240))
        size = self._cell_size()
        offset_x = (self.width() - size * self.GRID_SIZE) // 2
        offset_y = (self.height() - size * self.GRID_SIZE) // 2
        for row in range(self.GRID_SIZE):
            for col in range(self.GRID_SIZE):
                rect_x = offset_x + col * size
                rect_y = offset_y + row * size
                alive = self._cells[row][col] == 1
                color = QColor(255, 200, 80) if alive else QColor(28, 32, 44)
                painter.setBrush(color)
                painter.setPen(QPen(QColor(60, 70, 90), 1))
                painter.drawRect(
                    rect_x + self.CELL_PADDING,
                    rect_y + self.CELL_PADDING,
                    size - self.CELL_PADDING * 2,
                    size - self.CELL_PADDING * 2,
                )


# ===========================================================================
# 第九輪 #8 · Warp 發散 + 記憶體 coalescing 視圖
# ===========================================================================
class DivergenceView(QWidget):
    """以 32 格網格畫出 warp 分支發散與記憶體存取兩種模式。

    上半畫每條 thread 走哪條 path(顏色 = path id);
    下半畫每條 thread 讀哪條 cache line(顏色 = line id);
    旁邊 + 底下顯示中文摘要分析。
    """

    THREADS_PER_ROW = 8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(260)
        self._divergence_decisions: tuple[int, ...] = tuple(0 for _ in range(32))
        self._coalescing_addresses: tuple[int, ...] = tuple(range(32))
        self._summary_text: str = "(尚未指定模式)"

    def set_divergence_pattern(self, decisions: tuple[int, ...]) -> None:
        self._divergence_decisions = tuple(decisions)
        self.update()

    def set_coalescing_pattern(self, addresses: tuple[int, ...]) -> None:
        self._coalescing_addresses = tuple(addresses)
        self.update()

    def set_summary(self, text: str) -> None:
        self._summary_text = text
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(15, 17, 24, 240))

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(9)
        painter.setFont(font)

        cell_size = max(20, (self.width() - 60) // (self.THREADS_PER_ROW + 1))

        # Divergence(上半)
        painter.setPen(QPen(TEXT_DIM))
        painter.drawText(8, 16, "Warp 分支發散(顏色=path id)")
        self._draw_thread_grid(
            painter,
            self._divergence_decisions,
            cell_size=cell_size,
            origin_x=8,
            origin_y=22,
            value_to_color=lambda v: QColor.fromHsv((v * 67) % 360, 180, 230),
            label_format=lambda v: f"P{v}",
        )

        # Coalescing(下半)
        bottom_y = 22 + cell_size * 4 + 16
        painter.setPen(QPen(TEXT_DIM))
        painter.drawText(8, bottom_y - 4, "記憶體存取(顏色=cache line id)")
        line_ids = tuple(addr // 32 for addr in self._coalescing_addresses)
        self._draw_thread_grid(
            painter,
            line_ids,
            cell_size=cell_size,
            origin_x=8,
            origin_y=bottom_y,
            value_to_color=lambda v: QColor.fromHsv((v * 137) % 360, 200, 240),
            label_format=lambda v: f"L{v}",
        )

        # 中文摘要
        summary_y = bottom_y + cell_size * 4 + 18
        painter.setPen(QPen(TEXT_PRIMARY))
        painter.drawText(8, summary_y, self._summary_text)

    def _draw_thread_grid(
        self,
        painter: QPainter,
        values: tuple[int, ...],
        *,
        cell_size: int,
        origin_x: int,
        origin_y: int,
        value_to_color,
        label_format,
    ) -> None:
        for thread_id in range(min(32, len(values))):
            row = thread_id // self.THREADS_PER_ROW
            col = thread_id % self.THREADS_PER_ROW
            cell_x = origin_x + col * cell_size
            cell_y = origin_y + row * cell_size
            color = value_to_color(values[thread_id])
            painter.setBrush(color)
            painter.setPen(QPen(QColor(0, 0, 0, 80), 1))
            painter.drawRect(cell_x, cell_y, cell_size - 2, cell_size - 2)
            painter.setPen(QPen(QColor(20, 20, 20)))
            painter.drawText(
                cell_x + 2, cell_y + cell_size - 6, label_format(values[thread_id])
            )
