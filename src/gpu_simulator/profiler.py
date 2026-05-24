"""效能分析器 — 給 trace 一條一條看,算每顆 kernel 跑了多久、算佔用率(occupancy)、IPC。

教學重點:讓使用者看到「同一支 program 執行時間花在哪」,挑出瓶頸 kernel。
靈感來自 NVIDIA Nsight / nvprof,簡化到讀本系統 trace 即可。

提供:

- :class:`KernelStats`     一支 kernel 的效能數據
- :class:`SessionProfile`  整段執行的彙整
- :func:`profile_session`  從 trace + bridge 計算上面兩者
- :func:`roofline_points`  產生 Roofline 圖的 (operational intensity, perf) 點

無 Qt 相依;UI 端 :class:`ProfilerView` 在 :mod:`gpu_simulator.visualizer`(下游)
畫 bar chart + Roofline 散點。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 資料結構
# ---------------------------------------------------------------------------
@dataclass
class KernelStats:
    """一個 kernel name 在這 session 的彙整。"""

    kernel_name: str
    submissions: int = 0
    estimated_cycles: int = 0  # 該種 kernel 占用 GPU 的 cycle 預估
    bytes_touched: int = 0     # 該種 kernel 在 VRAM 佔用的 byte 累計
    triggers: Counter = field(default_factory=Counter)

    @property
    def operational_intensity(self) -> float:
        """每個 byte 換取的 cycle(教學版 OI;低 = memory-bound、高 = compute-bound)。"""
        if self.bytes_touched == 0:
            return 0.0
        return self.estimated_cycles / self.bytes_touched


@dataclass
class SessionProfile:
    """一整段 trace 的效能彙整。"""

    total_cycles: int
    total_kernels: int
    stalled_cycles: int
    cpu_busy_cycles: int
    avg_occupancy: float    # 0..1,平均跑滿幾個 SM
    instructions_per_cycle: float
    kernel_stats: list[KernelStats]

    def to_dict(self) -> dict:
        return {
            "total_cycles": self.total_cycles,
            "total_kernels": self.total_kernels,
            "stalled_cycles": self.stalled_cycles,
            "cpu_busy_cycles": self.cpu_busy_cycles,
            "avg_occupancy": self.avg_occupancy,
            "instructions_per_cycle": self.instructions_per_cycle,
            "kernels": [
                {
                    "kernel": k.kernel_name,
                    "submissions": k.submissions,
                    "cycles": k.estimated_cycles,
                    "bytes": k.bytes_touched,
                    "operational_intensity": k.operational_intensity,
                }
                for k in self.kernel_stats
            ],
        }


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
KERNEL_NAMES_BY_ID: tuple[str, ...] = (
    "vector_add",
    "interpolation",
    "hash",
    "texture_load",
    "idle_compression",
    "app_launch",
    "page_nav",
)


# 我們 KernelLibrary 內建的 cycle / VRAM(對應 kernel.py 裡的常數)。
# 這份表只給 profiler 算「估計 cycle」用,不影響真正執行。
DEFAULT_KERNEL_COST: dict[str, tuple[int, int]] = {
    # name → (per-block duration_ticks, vram_bytes)
    "vector_add":      (14, 2 * 1024 * 1024),
    "interpolation":   (6, 512 * 1024),
    "hash":            (10, 1 * 1024 * 1024),
    "texture_load":    (22, 16 * 1024 * 1024),
    "idle_compression": (30, 128 * 1024),
    "app_launch":      (30, 24 * 1024 * 1024),
    "page_nav":        (16, 6 * 1024 * 1024),
}


def profile_session(
    trace_rows: Sequence,
    *,
    sm_count: int = 8,
    warps_per_sm: int = 4,
) -> SessionProfile:
    """從一連串 trace row 統計效能。

    ``trace_rows`` 元素需要有 ``cpu_stalled`` / ``cpu_halted`` / ``port_writes``
    /``instruction_text`` 屬性;subset bridge 跟 full bridge 的 row 都符合。
    """
    total_cycles = len(trace_rows)
    if total_cycles == 0:
        return SessionProfile(
            total_cycles=0, total_kernels=0, stalled_cycles=0, cpu_busy_cycles=0,
            avg_occupancy=0.0, instructions_per_cycle=0.0, kernel_stats=[],
        )

    stalled_cycles = sum(1 for row in trace_rows if getattr(row, "cpu_stalled", False))
    halted_cycles = sum(1 for row in trace_rows if getattr(row, "cpu_halted", False))
    cpu_busy_cycles = total_cycles - stalled_cycles - halted_cycles

    kernel_counter: Counter[str] = Counter()
    trigger_per_kernel: dict[str, Counter] = {}
    for row in trace_rows:
        for port, value in getattr(row, "port_writes", []):
            if port == 0x40:
                kernel_id = value & 0xFF
                kernel_name = KERNEL_NAMES_BY_ID[kernel_id % len(KERNEL_NAMES_BY_ID)]
                kernel_counter[kernel_name] += 1
                trigger_per_kernel.setdefault(kernel_name, Counter())[
                    f"port_{port:02x}"
                ] += 1

    total_kernels = sum(kernel_counter.values())
    kernel_stats: list[KernelStats] = []
    estimated_compute_cycles_total = 0
    for kernel_name, count in kernel_counter.most_common():
        per_block_cycles, vram_bytes = DEFAULT_KERNEL_COST.get(
            kernel_name, (10, 1 * 1024 * 1024)
        )
        # 我們把「總執行 cycles」估成 (count × per_block_cycles),
        # 因為每次 KLAUNCH 大致等於跑一個 block。
        cycles = count * per_block_cycles
        estimated_compute_cycles_total += cycles
        kernel_stats.append(
            KernelStats(
                kernel_name=kernel_name,
                submissions=count,
                estimated_cycles=cycles,
                bytes_touched=count * vram_bytes,
                triggers=trigger_per_kernel.get(kernel_name, Counter()),
            )
        )

    # occupancy:GPU 在 stalled cycles 期間還在跑;
    # 用 (estimated_compute_cycles_total / (sm_count * warps_per_sm * total_cycles))
    # 做一個 0..1 比例,代表平均利用率。
    capacity = sm_count * warps_per_sm * max(1, total_cycles)
    avg_occupancy = min(1.0, estimated_compute_cycles_total / capacity)

    instructions_per_cycle = cpu_busy_cycles / total_cycles if total_cycles else 0.0

    return SessionProfile(
        total_cycles=total_cycles,
        total_kernels=total_kernels,
        stalled_cycles=stalled_cycles,
        cpu_busy_cycles=cpu_busy_cycles,
        avg_occupancy=avg_occupancy,
        instructions_per_cycle=instructions_per_cycle,
        kernel_stats=kernel_stats,
    )


# ---------------------------------------------------------------------------
# Roofline 散點 — 給 UI 畫圖
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RooflinePoint:
    label: str
    operational_intensity: float
    achieved_cycles: int


def roofline_points(profile: SessionProfile) -> list[RooflinePoint]:
    return [
        RooflinePoint(
            label=k.kernel_name,
            operational_intensity=k.operational_intensity,
            achieved_cycles=k.estimated_cycles,
        )
        for k in profile.kernel_stats
    ]
