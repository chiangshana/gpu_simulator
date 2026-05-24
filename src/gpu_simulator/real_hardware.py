"""真實硬體取樣 — 看自己機器當下的多核 CPU 跟 GPU 在做什麼。

這支模組是專題的「第三支柱」:把模擬器 + 真實硬體並排顯示,讓學生可以
**用同一個工具,既看模擬的 GPU 8 顆 SM,也看自己機器物理上的 N 顆 CPU 核心**。

設計重點:
* CPU 取樣用 :mod:`psutil`(我們既有的相依,可移植 Windows / macOS / Linux)。
* GPU 取樣轉用既有的 :class:`gpu_simulator.real_gpu.RealGPUSampler`,
  不重複造輪子。
* 純資料層 :class:`RealHardwareSample` 是 dataclass,可單獨測試。
* Qt widget :func:`build_real_hardware_panel` 把每顆核心畫成一條 bar,
  畫面上方一行顯示 CPU 名稱 / 頻率 / 核心數,旁邊獨立區塊放 GPU。
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

from gpu_simulator.real_gpu import RealGPUSample, RealGPUSampler


@dataclass(frozen=True)
class CPUSample:
    """一次 CPU 取樣的結果 — 每核心一個百分比。"""

    per_core_percent: tuple[float, ...]
    overall_percent: float
    logical_count: int
    physical_count: int
    frequency_mhz: float | None
    process_count: int

    @property
    def hottest_core_index(self) -> int:
        if not self.per_core_percent:
            return -1
        return max(range(len(self.per_core_percent)), key=lambda i: self.per_core_percent[i])

    def summary(self) -> str:
        freq = f"{self.frequency_mhz:.0f}MHz" if self.frequency_mhz else "?MHz"
        return (
            f"{self.logical_count} 邏輯核心(實體 {self.physical_count})"
            f" · {freq} · 整體 {self.overall_percent:.0f}%"
            f" · {self.process_count} 個處理程序"
        )


@dataclass(frozen=True)
class RealHardwareSample:
    """整合 CPU + GPU 一筆讀數,timestamp 由呼叫端附加。"""

    cpu: CPUSample
    gpu: RealGPUSample | None
    extra_notes: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------
class RealHardwareSampler:
    """取樣 CPU per-core + GPU。

    用法:

        sampler = RealHardwareSampler()
        sample = sampler.sample()
        for i, pct in enumerate(sample.cpu.per_core_percent):
            print(f"core {i}: {pct:.0f}%")
    """

    def __init__(self, *, gpu_backend: str = "auto") -> None:
        self._gpu = RealGPUSampler(preferred_backend=gpu_backend)
        # psutil 第一次呼叫 cpu_percent 需要 prime 一下
        self._primed = False
        with contextlib.suppress(Exception):
            import psutil

            psutil.cpu_percent(percpu=True)
            self._primed = True

    def sample(self) -> RealHardwareSample:
        cpu = self._sample_cpu()
        gpu = None
        with contextlib.suppress(Exception):
            gpu = self._gpu.sample()
        return RealHardwareSample(cpu=cpu, gpu=gpu)

    def gpu_available(self) -> bool:
        return self._gpu.available()

    def gpu_backend_name(self) -> str:
        return self._gpu.backend_name

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._gpu.close()

    # ------------------------------------------------------------------
    # 內部:CPU 取樣
    # ------------------------------------------------------------------
    def _sample_cpu(self) -> CPUSample:
        try:
            import psutil
        except ImportError:
            return CPUSample(
                per_core_percent=(),
                overall_percent=0.0,
                logical_count=0,
                physical_count=0,
                frequency_mhz=None,
                process_count=0,
            )
        per_core = tuple(float(x) for x in psutil.cpu_percent(percpu=True))
        overall = float(psutil.cpu_percent())
        logical = psutil.cpu_count(logical=True) or len(per_core)
        physical = psutil.cpu_count(logical=False) or logical
        freq = None
        with contextlib.suppress(Exception):
            f = psutil.cpu_freq()
            if f is not None:
                freq = float(f.current)
        process_count = 0
        with contextlib.suppress(Exception):
            process_count = len(psutil.pids())
        return CPUSample(
            per_core_percent=per_core,
            overall_percent=overall,
            logical_count=int(logical),
            physical_count=int(physical),
            frequency_mhz=freq,
            process_count=process_count,
        )


# ---------------------------------------------------------------------------
# Per-core utilisation 顏色映射 — 從綠到紅
# ---------------------------------------------------------------------------
def utilization_to_color(percent: float) -> str:
    """0..100 → CSS rgb 字串(綠 → 黃 → 橘 → 紅)。"""
    p = max(0.0, min(100.0, percent))
    if p < 30:
        return "rgb(80, 200, 110)"   # 綠
    if p < 60:
        return "rgb(220, 200, 80)"   # 黃
    if p < 85:
        return "rgb(230, 150, 60)"   # 橘
    return "rgb(230, 80, 80)"        # 紅


def bin_per_core(per_core: tuple[float, ...]) -> dict[str, int]:
    """把每核心讀數依負載分箱 — 教學報告用。"""
    bins = {"idle (<10%)": 0, "light (10-40%)": 0, "busy (40-80%)": 0, "hot (>=80%)": 0}
    for pct in per_core:
        if pct < 10:
            bins["idle (<10%)"] += 1
        elif pct < 40:
            bins["light (10-40%)"] += 1
        elif pct < 80:
            bins["busy (40-80%)"] += 1
        else:
            bins["hot (>=80%)"] += 1
    return bins


# ---------------------------------------------------------------------------
# Qt panel
# ---------------------------------------------------------------------------
def build_real_hardware_panel(parent=None):
    """建一個分頁:標頭 + N 條 CPU 核心 bar + GPU 區塊;每秒自動更新。"""
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QFrame,
        QGridLayout,
        QLabel,
        QProgressBar,
        QVBoxLayout,
        QWidget,
    )

    sampler = RealHardwareSampler()

    box = QWidget(parent)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    title = QLabel("💻 <b>真實硬體即時監測</b> — 你電腦的多核 CPU + 真實 GPU 現在在幹嘛")
    title.setStyleSheet("color: rgba(220,230,240,240); font-size: 11pt;")
    layout.addWidget(title)

    cpu_summary = QLabel("(讀取中…)", box)
    cpu_summary.setStyleSheet(
        "color: rgba(220,220,230,240); font-family: monospace; font-size: 10pt;"
    )
    layout.addWidget(cpu_summary)

    cores_frame = QFrame(box)
    cores_frame.setStyleSheet(
        "QFrame { background: rgba(20,22,28,200); border-radius: 6px; padding: 4px; }"
    )
    cores_grid = QGridLayout(cores_frame)
    cores_grid.setContentsMargins(8, 8, 8, 8)
    cores_grid.setHorizontalSpacing(8)
    cores_grid.setVerticalSpacing(4)
    layout.addWidget(cores_frame, 1)

    bars: dict[int, QProgressBar] = {}
    labels: dict[int, QLabel] = {}

    gpu_frame = QFrame(box)
    gpu_frame.setStyleSheet(
        "QFrame { background: rgba(20,22,28,200); border-radius: 6px; padding: 6px; }"
    )
    gpu_layout = QVBoxLayout(gpu_frame)
    gpu_title = QLabel("🎮 真實 GPU", gpu_frame)
    gpu_title.setStyleSheet("color: rgba(240,220,140,240); font-size: 11pt;")
    gpu_layout.addWidget(gpu_title)
    gpu_summary = QLabel("(讀取中或無 NVIDIA GPU)", gpu_frame)
    gpu_summary.setStyleSheet("color: rgba(220,220,230,235); font-family: monospace; font-size: 10pt;")
    gpu_summary.setWordWrap(True)
    gpu_layout.addWidget(gpu_summary)
    layout.addWidget(gpu_frame)

    def ensure_bars(n: int) -> None:
        """有 n 個核心就確保有 n 條 bar(grid 為 2 欄)。"""
        for i in range(len(bars), n):
            label = QLabel(f"核 {i:2d}", cores_frame)
            label.setStyleSheet("color: rgba(220,220,230,230); font-family: monospace; font-size: 9pt;")
            label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            bar = QProgressBar(cores_frame)
            bar.setRange(0, 100)
            bar.setTextVisible(True)
            bar.setFormat("%p%")
            bar.setFixedHeight(16)
            row = i // 2
            col = (i % 2) * 2
            cores_grid.addWidget(label, row, col)
            cores_grid.addWidget(bar, row, col + 1)
            labels[i] = label
            bars[i] = bar

    def refresh() -> None:
        sample = sampler.sample()
        cpu = sample.cpu
        cpu_summary.setText(cpu.summary())
        ensure_bars(len(cpu.per_core_percent))
        for idx, pct in enumerate(cpu.per_core_percent):
            bar = bars[idx]
            bar.setValue(int(round(pct)))
            color = utilization_to_color(pct)
            bar.setStyleSheet(
                f"QProgressBar {{ background: rgba(40,40,50,200); border: 1px solid rgba(80,80,100,200);"
                f" border-radius: 3px; text-align: center; color: white; font-size: 9pt; }} "
                f"QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}"
            )
        # GPU
        gpu = sample.gpu
        if gpu is None:
            if sampler.gpu_available():
                gpu_summary.setText("(取樣失敗,稍後重試…)")
            else:
                gpu_summary.setText(
                    "未偵測到支援的 GPU 後端。\n"
                    "NVIDIA 用戶可 `pip install gpu_simulator[realgpu]` 啟用 pynvml + GPUtil。\n"
                    "(其他廠牌目前用模擬 GPU 體驗即可)"
                )
        else:
            mem_used_mb = (gpu.memory_used_bytes or 0) / 1024 / 1024
            mem_total_mb = (gpu.memory_total_bytes or 0) / 1024 / 1024
            temp = f"{gpu.temperature_celsius:.0f}°C" if gpu.temperature_celsius else "?"
            power = f"{gpu.power_watts:.1f}W" if gpu.power_watts else "?"
            util = f"{gpu.utilization_percent:.0f}%" if gpu.utilization_percent is not None else "?"
            gpu_summary.setText(
                f"{gpu.name}  ·  backend: {gpu.backend}\n"
                f"利用率 {util}  ·  記憶體 {mem_used_mb:.0f}/{mem_total_mb:.0f} MiB\n"
                f"溫度 {temp}  ·  功耗 {power}"
            )

    refresh_timer = QTimer(box)
    refresh_timer.setInterval(1000)
    refresh_timer.timeout.connect(refresh)
    refresh_timer.start()
    QTimer.singleShot(150, refresh)  # 第一筆讀數,不要等 1 秒

    box._real_hw_sampler = sampler  # type: ignore[attr-defined]
    box._real_hw_timer = refresh_timer  # type: ignore[attr-defined]
    return box
