"""雙 GPU + NVLink 模擬。

設計:兩顆獨立的 :class:`~gpu_simulator.core.GPU`,加一個 NVLink 通道
模擬「跨卡記憶體傳輸」— 寫到任一邊的特定 magic 位址即觸發跨卡 copy。

教學意義:讓使用者直觀理解
1. 為什麼兩顆 GPU 的 VRAM 不共享(必須 explicit copy)
2. NVLink 帶寬有限(我們用「每次跨卡 transfer 要花 N cycle」呈現)
3. 同步難題(等對面跑完才能繼續)

本系統等級的設計:**純資料模型**,沒有 Qt;UI 端用 :class:`MultiGPUDashboard` 在
visualizer.py 側顯示。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from gpu_simulator.core import GPU, GPUConfig
from gpu_simulator.kernel import Kernel


# ---------------------------------------------------------------------------
# NVLink 通道
# ---------------------------------------------------------------------------
@dataclass
class NVLinkTransfer:
    """正在進行中的跨卡傳輸。"""

    source_gpu_id: int           # 0 / 1
    destination_gpu_id: int      # 0 / 1
    bytes_remaining: int
    total_bytes: int
    label: str

    @property
    def progress(self) -> float:
        if self.total_bytes == 0:
            return 1.0
        return 1.0 - self.bytes_remaining / self.total_bytes


@dataclass
class NVLinkChannel:
    """單向頻寬:每個 cycle 可以搬 ``bandwidth_bytes_per_cycle`` byte。"""

    bandwidth_bytes_per_cycle: int = 256 * 1024  # 預設 256 KB / cycle
    pending: deque[NVLinkTransfer] = field(default_factory=deque)
    completed: int = 0

    def schedule(
        self,
        source_gpu_id: int,
        destination_gpu_id: int,
        size_bytes: int,
        label: str,
    ) -> NVLinkTransfer:
        transfer = NVLinkTransfer(
            source_gpu_id=source_gpu_id,
            destination_gpu_id=destination_gpu_id,
            bytes_remaining=size_bytes,
            total_bytes=size_bytes,
            label=label,
        )
        self.pending.append(transfer)
        return transfer

    def tick(self) -> list[NVLinkTransfer]:
        """前進一個 cycle;回傳這 cycle 完成的 transfer。"""
        finished: list[NVLinkTransfer] = []
        if not self.pending:
            return finished
        active = self.pending[0]
        active.bytes_remaining -= self.bandwidth_bytes_per_cycle
        if active.bytes_remaining <= 0:
            active.bytes_remaining = 0
            finished.append(active)
            self.pending.popleft()
            self.completed += 1
        return finished


# ---------------------------------------------------------------------------
# Multi-GPU 系統
# ---------------------------------------------------------------------------
@dataclass
class MultiGPUConfig:
    gpu_count: int = 2
    per_gpu_config: GPUConfig = field(default_factory=GPUConfig)
    nvlink_bandwidth_bytes_per_cycle: int = 256 * 1024


class MultiGPUSystem:
    """主協調者:兩顆 GPU + 一條 NVLink。

    用法::

        system = MultiGPUSystem()
        system.submit_kernel_to(0, KernelLibrary.vector_add())
        system.submit_kernel_to(1, KernelLibrary.hash_kernel("a"))
        system.transfer_between(0, 1, 4 * 1024 * 1024, "result")
        for _ in range(60):
            system.tick()
        snapshot = system.snapshot()
    """

    def __init__(self, config: MultiGPUConfig | None = None) -> None:
        self.config = config or MultiGPUConfig()
        self.gpus: list[GPU] = [
            GPU(self.config.per_gpu_config) for _ in range(self.config.gpu_count)
        ]
        self.nvlink = NVLinkChannel(
            bandwidth_bytes_per_cycle=self.config.nvlink_bandwidth_bytes_per_cycle
        )
        self.cycle_count: int = 0
        self.cross_gpu_completions: int = 0

    # ------------------------------------------------------------------
    # public ops
    # ------------------------------------------------------------------
    def submit_kernel_to(self, gpu_index: int, kernel: Kernel) -> bool:
        if not 0 <= gpu_index < len(self.gpus):
            return False
        return self.gpus[gpu_index].submit_kernel(kernel)

    def transfer_between(
        self, source: int, destination: int, size_bytes: int, label: str = ""
    ) -> NVLinkTransfer | None:
        if source == destination:
            return None
        if not (
            0 <= source < len(self.gpus) and 0 <= destination < len(self.gpus)
        ):
            return None
        return self.nvlink.schedule(source, destination, size_bytes, label or "data")

    def tick(self) -> None:
        self.cycle_count += 1
        for gpu in self.gpus:
            gpu.tick()
        finished = self.nvlink.tick()
        self.cross_gpu_completions += len(finished)

    def reset(self) -> None:
        self.gpus = [GPU(self.config.per_gpu_config) for _ in range(self.config.gpu_count)]
        self.nvlink = NVLinkChannel(
            bandwidth_bytes_per_cycle=self.config.nvlink_bandwidth_bytes_per_cycle
        )
        self.cycle_count = 0
        self.cross_gpu_completions = 0

    # ------------------------------------------------------------------
    # snapshot for UI
    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        return {
            "cycle": self.cycle_count,
            "gpus": [gpu.snapshot() for gpu in self.gpus],
            "nvlink": {
                "bandwidth_bytes_per_cycle": self.nvlink.bandwidth_bytes_per_cycle,
                "pending_transfers": [
                    {
                        "source": t.source_gpu_id,
                        "destination": t.destination_gpu_id,
                        "progress": t.progress,
                        "bytes_remaining": t.bytes_remaining,
                        "label": t.label,
                    }
                    for t in self.nvlink.pending
                ],
                "completed": self.nvlink.completed,
            },
            "cross_gpu_completions": self.cross_gpu_completions,
        }
