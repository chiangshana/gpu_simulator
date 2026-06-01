"""🪞 對照鏡(Comparison Mirror)— 本專案的核心論述具象化在一個分頁。

把「模擬 GPU」跟「你電腦的真實 CPU + GPU」**並排**畫在同一個視窗,讓使用者
親眼看到兩個世界的對應關係:

* 左半:虛擬 GPU 8 顆 SM 的即時利用率
* 右半:真實機器 N 顆邏輯 CPU 核心的即時利用率
* 下方:真實 GPU 的利用率 / 記憶體 / 溫度 / 功耗(如果偵測到 NVIDIA)
* 一顆按鈕「▶️ 觸發模擬工作負載」 — 按下去左邊跳起來、右邊**幾乎不動**,
  讓學生瞬間理解「這是模擬出來的」這件事

資料層 :class:`ComparisonSnapshot` + :func:`compose_snapshot` 完全沒 Qt 相依,
可單獨測試對齊邏輯。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from gpu_simulator.real_hardware import CPUSample, RealHardwareSample, utilization_to_color


@dataclass(frozen=True)
class SimulatedSMSummary:
    """單顆模擬 SM 的快取資料 — 從 :meth:`GPU.snapshot` 萃取出來。"""

    sm_id: int
    utilization_percent: float
    active_warps: int

    @property
    def label(self) -> str:
        return f"SM{self.sm_id}"


@dataclass(frozen=True)
class ComparisonSnapshot:
    """一次「左右兩邊」的對照讀數,UI 直接 render。"""

    simulated_sms: tuple[SimulatedSMSummary, ...]
    simulated_overall_percent: float
    simulated_clock: int
    real_cpu: CPUSample
    real_gpu_summary: str
    extra_notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def simulated_count(self) -> int:
        return len(self.simulated_sms)

    @property
    def real_count(self) -> int:
        return len(self.real_cpu.per_core_percent)

    def alignment(self) -> tuple[int, int]:
        """左右兩邊各畫幾條 bar — 兩邊**獨立**,不強制等量。"""
        return (self.simulated_count, self.real_count)


# ---------------------------------------------------------------------------
# 純資料層:把模擬 GPU snapshot + 真實硬體 sample 合併
# ---------------------------------------------------------------------------
def compose_snapshot(
    sim_snapshot: dict,
    real_sample: RealHardwareSample,
) -> ComparisonSnapshot:
    """:meth:`GPU.snapshot()` + :class:`RealHardwareSample` → :class:`ComparisonSnapshot`."""
    sms = []
    raw_sms = sim_snapshot.get("sms", [])
    for sm in raw_sms:
        warps = sm.get("warps", [])
        active = sum(1 for w in warps if w.get("state", "idle") != "idle")
        # SM 利用率粗略 = active warps / total warps
        total = max(1, len(warps))
        util = (active / total) * 100.0
        sms.append(
            SimulatedSMSummary(
                sm_id=int(sm.get("sm_id", 0)),
                utilization_percent=float(util),
                active_warps=active,
            )
        )
    overall = float(sim_snapshot.get("overall_utilization", 0.0)) * 100.0
    clock = int(sim_snapshot.get("clock", 0))
    gpu_text = _format_real_gpu_line(real_sample)
    return ComparisonSnapshot(
        simulated_sms=tuple(sms),
        simulated_overall_percent=overall,
        simulated_clock=clock,
        real_cpu=real_sample.cpu,
        real_gpu_summary=gpu_text,
    )


def _format_real_gpu_line(real_sample: RealHardwareSample) -> str:
    gpu = real_sample.gpu
    if gpu is None:
        return "(未偵測到 NVIDIA GPU — 看右邊 CPU 即可)"
    mem_used = (gpu.memory_used_bytes or 0) / 1024 / 1024
    mem_total = (gpu.memory_total_bytes or 0) / 1024 / 1024
    util = f"{gpu.utilization_percent:.0f}%" if gpu.utilization_percent is not None else "?"
    temp = f"{gpu.temperature_celsius:.0f}°C" if gpu.temperature_celsius else "?"
    power = f"{gpu.power_watts:.1f}W" if gpu.power_watts else "?"
    return (
        f"{gpu.name} · {gpu.backend} · 利用率 {util} · "
        f"{mem_used:.0f}/{mem_total:.0f} MiB · {temp} · {power}"
    )


def divergence_score(snapshot: ComparisonSnapshot) -> float:
    """「模擬 vs 真實」的差距分數(0..100) — 教學用,讓學生看數字理解。

    定義:|模擬整體 - 真實 CPU 整體|。0 = 兩邊一模一樣;100 = 一邊滿一邊閒。
    """
    if not snapshot.simulated_sms:
        return 0.0
    diff = abs(snapshot.simulated_overall_percent - snapshot.real_cpu.overall_percent)
    return min(100.0, max(0.0, diff))


# ---------------------------------------------------------------------------
# Qt 分頁
# ---------------------------------------------------------------------------
def build_mirror_dashboard(
    parent,
    snapshot_provider: Callable[[], ComparisonSnapshot],
    on_trigger_workload: Callable[[], None] | None = None,
):
    """建立 🪞 對照鏡分頁。``snapshot_provider`` 每秒呼叫一次。"""
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    box = QWidget(parent)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    header = QLabel(
        "🪞 <b>對照鏡 — 模擬 GPU vs 真實電腦</b>"
        "  ·  左邊是這個專案模擬出來的 8 個運算單元(SM,GPU 的計算核心),"
        "右邊是你電腦真實的每一顆 CPU 核心。"
    )
    header.setStyleSheet("color: rgba(220,230,240,240); font-size: 11pt;")
    header.setWordWrap(True)
    layout.addWidget(header)

    columns = QHBoxLayout()
    layout.addLayout(columns, 1)

    # 左:模擬 GPU
    left = QFrame(box)
    left.setStyleSheet(
        "QFrame { background: rgba(28,22,40,210); border-radius: 8px; padding: 6px; }"
    )
    left_layout = QVBoxLayout(left)
    left_title = QLabel("🎮 <b>模擬 GPU</b>(這個專題寫程式做出來的)", left)
    left_title.setStyleSheet("color: rgba(200,180,250,240); font-size: 11pt;")
    left_layout.addWidget(left_title)
    left_summary = QLabel("(讀取中…)", left)
    left_summary.setStyleSheet(
        "color: rgba(220,220,230,235); font-family: monospace; font-size: 9pt;"
    )
    left_layout.addWidget(left_summary)
    left_grid_frame = QFrame(left)
    left_grid = QGridLayout(left_grid_frame)
    left_grid.setContentsMargins(6, 6, 6, 6)
    left_grid.setVerticalSpacing(3)
    left_layout.addWidget(left_grid_frame, 1)
    columns.addWidget(left, 1)

    # 右:真實 CPU
    right = QFrame(box)
    right.setStyleSheet(
        "QFrame { background: rgba(22,28,40,210); border-radius: 8px; padding: 6px; }"
    )
    right_layout = QVBoxLayout(right)
    right_title = QLabel("💻 <b>真實 CPU</b>(你這台機器)", right)
    right_title.setStyleSheet("color: rgba(180,230,250,240); font-size: 11pt;")
    right_layout.addWidget(right_title)
    right_summary = QLabel("(讀取中…)", right)
    right_summary.setStyleSheet(
        "color: rgba(220,220,230,235); font-family: monospace; font-size: 9pt;"
    )
    right_layout.addWidget(right_summary)
    right_grid_frame = QFrame(right)
    right_grid = QGridLayout(right_grid_frame)
    right_grid.setContentsMargins(6, 6, 6, 6)
    right_grid.setVerticalSpacing(3)
    right_layout.addWidget(right_grid_frame, 1)
    columns.addWidget(right, 1)

    # 下方:真實 GPU + 對照分數
    bottom_frame = QFrame(box)
    bottom_frame.setStyleSheet(
        "QFrame { background: rgba(20,22,28,210); border-radius: 8px; padding: 6px; }"
    )
    bottom_layout = QVBoxLayout(bottom_frame)
    gpu_title = QLabel("🎮 真實 GPU(只有 NVIDIA 顯卡用戶看得到)", bottom_frame)
    gpu_title.setStyleSheet("color: rgba(240,220,140,240); font-size: 10pt;")
    bottom_layout.addWidget(gpu_title)
    gpu_text = QLabel("(讀取中…)", bottom_frame)
    gpu_text.setStyleSheet("color: rgba(220,220,230,235); font-family: monospace; font-size: 9pt;")
    gpu_text.setWordWrap(True)
    bottom_layout.addWidget(gpu_text)
    divergence_label = QLabel("差距分數:--", bottom_frame)
    divergence_label.setStyleSheet(
        "color: rgba(250,200,180,240); font-family: monospace; font-size: 10pt;"
    )
    bottom_layout.addWidget(divergence_label)
    layout.addWidget(bottom_frame)

    # 按鈕列
    button_row = QHBoxLayout()
    trigger_btn = QPushButton("▶️ 派工作給模擬 GPU(看左邊跳起來,右邊真實 CPU 不會動)", box)
    trigger_btn.setStyleSheet(
        "QPushButton { background: rgba(80,100,180,220); color: white; "
        "border-radius: 6px; padding: 6px 14px; font-size: 10pt; } "
        "QPushButton:hover { background: rgba(110,140,220,240); }"
    )
    if on_trigger_workload is not None:
        trigger_btn.clicked.connect(on_trigger_workload)
    else:
        trigger_btn.setEnabled(False)
        trigger_btn.setToolTip("沒接 callback,僅顯示用")
    button_row.addWidget(trigger_btn)
    button_row.addStretch(1)
    layout.addLayout(button_row)

    # 內部 bar 容器
    sim_bars: dict[int, QProgressBar] = {}
    sim_labels: dict[int, QLabel] = {}
    real_bars: dict[int, QProgressBar] = {}
    real_labels: dict[int, QLabel] = {}

    def _ensure_bar_grid(
        grid: QGridLayout,
        bar_dict: dict[int, QProgressBar],
        label_dict: dict[int, QLabel],
        n: int,
        prefix: str,
    ) -> None:
        for i in range(len(bar_dict), n):
            label = QLabel(f"{prefix}{i:2d}", grid.parentWidget())
            label.setStyleSheet(
                "color: rgba(220,220,230,230); font-family: monospace; font-size: 9pt;"
            )
            label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            label.setFixedWidth(46)
            bar = QProgressBar(grid.parentWidget())
            bar.setRange(0, 100)
            bar.setTextVisible(True)
            bar.setFormat("%p%")
            bar.setFixedHeight(14)
            grid.addWidget(label, i, 0)
            grid.addWidget(bar, i, 1)
            label_dict[i] = label
            bar_dict[i] = bar

    def _paint_bar(bar: QProgressBar, percent: float) -> None:
        bar.setValue(int(round(percent)))
        color = utilization_to_color(percent)
        bar.setStyleSheet(
            "QProgressBar { background: rgba(35,35,45,200); "
            "border: 1px solid rgba(80,80,100,200); border-radius: 3px; "
            "text-align: center; color: white; font-size: 8pt; } "
            f"QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}"
        )

    def refresh() -> None:
        try:
            snap = snapshot_provider()
        except Exception:
            return
        # 左 — 模擬 SM
        _ensure_bar_grid(left_grid, sim_bars, sim_labels, snap.simulated_count, "SM")
        for sm in snap.simulated_sms:
            bar = sim_bars.get(sm.sm_id)
            if bar is not None:
                _paint_bar(bar, sm.utilization_percent)
        left_summary.setText(
            f"整體 {snap.simulated_overall_percent:.0f}% · "
            f"clock {snap.simulated_clock} · "
            f"{snap.simulated_count} 顆 SM"
        )
        # 右 — 真實 CPU
        _ensure_bar_grid(right_grid, real_bars, real_labels, snap.real_count, "核")
        for idx, pct in enumerate(snap.real_cpu.per_core_percent):
            bar = real_bars.get(idx)
            if bar is not None:
                _paint_bar(bar, pct)
        right_summary.setText(snap.real_cpu.summary())
        # 下
        gpu_text.setText(snap.real_gpu_summary)
        diff = divergence_score(snap)
        divergence_label.setText(
            f"差距分數:{diff:.0f} / 100  "
            f"(0 = 兩邊一樣忙;按上面那顆藍色按鈕就會看到差距瞬間飆高)"
        )

    timer = QTimer(box)
    timer.setInterval(1000)
    timer.timeout.connect(refresh)
    timer.start()
    QTimer.singleShot(200, refresh)

    box._mirror_timer = timer  # type: ignore[attr-defined]
    return box
