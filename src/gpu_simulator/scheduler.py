"""Warp scheduler and pipeline stage definitions.

The scheduler takes :class:`~gpu_simulator.kernel.Kernel` submissions off a
queue and assigns their blocks to free warps on the streaming
multiprocessors.  A real GPU has several sophisticated policies; for
educational purposes we implement a simple round-robin FIFO.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from gpu_simulator.kernel import Kernel


class PipelineStage(Enum):
    """Classic 5-stage pipeline used for visualization."""

    FETCH = "fetch"
    DECODE = "decode"
    EXECUTE = "execute"
    MEMORY = "memory"
    WRITEBACK = "writeback"


PIPELINE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.FETCH,
    PipelineStage.DECODE,
    PipelineStage.EXECUTE,
    PipelineStage.MEMORY,
    PipelineStage.WRITEBACK,
)


def next_stage(stage: PipelineStage) -> PipelineStage:
    """Return the stage that follows ``stage``, wrapping to FETCH."""
    index = PIPELINE_ORDER.index(stage)
    return PIPELINE_ORDER[(index + 1) % len(PIPELINE_ORDER)]


@dataclass
class DispatchRecord:
    """A pending chunk of work — one block of a submitted kernel."""

    kernel: Kernel
    block_index: int

    def snapshot(self) -> dict:
        return {
            "kernel": self.kernel.name,
            "block_index": self.block_index,
            "profile": self.kernel.profile.value,
        }


@dataclass
class WarpScheduler:
    """FIFO scheduler: blocks dispatched in submission order.

    The scheduler itself does not know about SMs — it simply hands out
    the next ready block.  The :class:`~gpu_simulator.core.GPU` loop is
    responsible for asking the scheduler whenever a warp frees up.
    """

    queue: deque[DispatchRecord] = field(default_factory=deque)
    completed_kernels: int = 0

    def submit(self, kernel: Kernel) -> None:
        """Expand ``kernel`` into per-block :class:`DispatchRecord`s."""
        for block_index in range(kernel.grid_size):
            self.queue.append(DispatchRecord(kernel=kernel, block_index=block_index))

    def pop_ready(self) -> DispatchRecord | None:
        if not self.queue:
            return None
        return self.queue.popleft()

    @property
    def pending_blocks(self) -> int:
        return len(self.queue)

    def snapshot(self) -> dict:
        return {
            "pending_blocks": self.pending_blocks,
            "completed_kernels": self.completed_kernels,
            "head": self.queue[0].snapshot() if self.queue else None,
        }
