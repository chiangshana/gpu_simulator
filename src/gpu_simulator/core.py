"""Core GPU model — SMs, warps, threads, and the simulation loop.

A virtual :class:`GPU` is composed of a fixed number of
:class:`StreamingMultiprocessor` units.  Each SM owns a pool of
:class:`Warp` objects that walk through a simple 5-stage pipeline.

The :meth:`GPU.tick` method advances the whole system by one simulated
clock — the UI thread calls it from a timer to produce animation.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from gpu_simulator.exceptions import KernelSubmissionError, VRAMOverflowError
from gpu_simulator.kernel import Kernel, WorkloadProfile
from gpu_simulator.memory import VRAM, RegisterFile, SharedMemory
from gpu_simulator.scheduler import (
    PIPELINE_ORDER,
    DispatchRecord,
    PipelineStage,
    WarpScheduler,
    next_stage,
)


class WarpState(Enum):
    """Lifecycle state of an individual warp."""

    IDLE = "idle"
    RUNNING = "running"
    STALLED = "stalled"


@dataclass
class Warp:
    """A group of threads executing in lockstep.

    Real GPUs use warps of 32 threads; we allow the count to be
    configured so tests can shrink them.
    """

    warp_id: int
    thread_count: int = 32
    state: WarpState = WarpState.IDLE
    pipeline_stage: PipelineStage = PipelineStage.FETCH
    active_mask: int = 0xFFFFFFFF
    current_block: DispatchRecord | None = None
    ticks_remaining: int = 0

    @property
    def is_busy(self) -> bool:
        return self.state is not WarpState.IDLE

    @property
    def kernel_name(self) -> str:
        return self.current_block.kernel.name if self.current_block else ""

    def assign(self, block: DispatchRecord) -> None:
        """Start executing ``block`` on this warp."""
        self.current_block = block
        self.ticks_remaining = block.kernel.duration_ticks
        self.state = WarpState.RUNNING
        self.pipeline_stage = PipelineStage.FETCH

    def reset(self) -> None:
        self.current_block = None
        self.ticks_remaining = 0
        self.state = WarpState.IDLE
        self.pipeline_stage = PipelineStage.FETCH

    def tick(self) -> bool:
        """Advance this warp one cycle.  Returns ``True`` if it just finished."""
        if self.state is not WarpState.RUNNING:
            return False
        self.pipeline_stage = next_stage(self.pipeline_stage)
        self.ticks_remaining -= 1
        if self.ticks_remaining <= 0:
            self.reset()
            return True
        return False

    def snapshot(self) -> dict:
        return {
            "warp_id": self.warp_id,
            "state": self.state.value,
            "stage": self.pipeline_stage.value,
            "kernel": self.kernel_name,
            "ticks_remaining": self.ticks_remaining,
        }


@dataclass
class StreamingMultiprocessor:
    """One SM: owns warps, shared memory and a register file."""

    sm_id: int
    warps: list[Warp] = field(default_factory=list)
    shared_memory: SharedMemory = field(default_factory=SharedMemory)
    register_file: RegisterFile = field(default_factory=RegisterFile)
    completed_warps: int = 0

    @property
    def warp_count(self) -> int:
        return len(self.warps)

    @property
    def busy_warps(self) -> int:
        return sum(1 for warp in self.warps if warp.is_busy)

    @property
    def utilization(self) -> float:
        if not self.warps:
            return 0.0
        return self.busy_warps / self.warp_count

    def idle_warp(self) -> Warp | None:
        for warp in self.warps:
            if not warp.is_busy:
                return warp
        return None

    def tick(self) -> int:
        """Tick every warp; return number of warps that finished this cycle."""
        finished = 0
        for warp in self.warps:
            if warp.tick():
                finished += 1
                self.completed_warps += 1
        return finished

    def snapshot(self) -> dict:
        return {
            "sm_id": self.sm_id,
            "utilization": self.utilization,
            "busy_warps": self.busy_warps,
            "warp_count": self.warp_count,
            "shared_memory": self.shared_memory.snapshot(),
            "register_file": self.register_file.snapshot(),
            "warps": [warp.snapshot() for warp in self.warps],
            "completed_warps": self.completed_warps,
        }


@dataclass
class GPUConfig:
    """Tunable parameters for a :class:`GPU` instance."""

    num_sms: int = 8
    warps_per_sm: int = 4
    threads_per_warp: int = 32
    vram_capacity_bytes: int = 256 * 1024 * 1024
    shared_memory_per_sm_bytes: int = 48 * 1024
    registers_per_thread: int = 64
    event_log_size: int = 32


@dataclass
class EventLogEntry:
    """A one-line record of activity, used by the UI event log."""

    clock: int
    message: str


class GPU:
    """The whole virtual GPU.

    Typical usage::

        gpu = GPU()
        gpu.submit_kernel(KernelLibrary.vector_add())
        for _ in range(20):
            gpu.tick()
        snapshot = gpu.snapshot()  # hand to the UI
    """

    def __init__(self, config: GPUConfig | None = None) -> None:
        self.config = config or GPUConfig()
        self.clock: int = 0
        self.kernels_submitted: int = 0
        self.kernels_completed: int = 0
        self.vram = VRAM(capacity_bytes=self.config.vram_capacity_bytes)
        self.scheduler = WarpScheduler()
        self.sms: list[StreamingMultiprocessor] = [
            self._build_sm(sm_id) for sm_id in range(self.config.num_sms)
        ]
        self._event_log: deque[EventLogEntry] = deque(maxlen=self.config.event_log_size)
        self._kernel_block_counts: dict[str, int] = {}
        self._last_kernel_id: int = 0

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------
    def _build_sm(self, sm_id: int) -> StreamingMultiprocessor:
        shared_memory = SharedMemory(capacity_bytes=self.config.shared_memory_per_sm_bytes)
        register_file = RegisterFile(
            registers_per_thread=self.config.registers_per_thread,
            thread_count=self.config.threads_per_warp,
        )
        warps = [
            Warp(warp_id=warp_id, thread_count=self.config.threads_per_warp)
            for warp_id in range(self.config.warps_per_sm)
        ]
        return StreamingMultiprocessor(
            sm_id=sm_id,
            warps=warps,
            shared_memory=shared_memory,
            register_file=register_file,
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def submit_kernel(self, kernel: Kernel) -> bool:
        """Queue ``kernel`` for execution, returning ``False`` on VRAM pressure.

        This is the forgiving variant used by the UI loop.  For a strict
        variant that raises :class:`~gpu_simulator.exceptions.VRAMOverflowError`
        use :meth:`submit_kernel_strict`.
        """
        try:
            self.submit_kernel_strict(kernel)
            return True
        except VRAMOverflowError:
            self._log(f"dropped {kernel.name}: VRAM full")
            return False

    def submit_kernel_strict(self, kernel: Kernel) -> None:
        """Queue ``kernel`` or raise a descriptive exception."""
        if kernel.grid_size <= 0 or kernel.block_size <= 0:
            raise KernelSubmissionError(
                f"kernel {kernel.name!r} has non-positive grid/block size"
            )
        tag = self._tagged_name(kernel)
        if not self.vram.allocate(
            owner_kernel=tag,
            size_bytes=kernel.vram_bytes,
            lifetime_ticks=kernel.duration_ticks + 4,
        ):
            raise VRAMOverflowError(
                requested_bytes=kernel.vram_bytes,
                free_bytes=self.vram.free_bytes,
            )
        self.scheduler.submit(kernel)
        self.kernels_submitted += 1
        self._kernel_block_counts[tag] = kernel.grid_size
        self._log(
            f"submit {kernel.name} (grid={kernel.grid_size}, "
            f"profile={kernel.profile.value}, trigger={kernel.trigger or 'n/a'})"
        )

    def tick(self) -> None:
        """Advance the simulation by one clock cycle."""
        self.clock += 1
        self._dispatch_blocks()
        finished_blocks: list[str] = []
        for sm in self.sms:
            finished = sm.tick()
            if finished:
                finished_blocks.extend([""] * finished)
        self.vram.tick()
        self._account_for_finished_blocks(len(finished_blocks))

    def reset(self) -> None:
        """Return the GPU to a pristine state — useful in tests."""
        self.__init__(self.config)

    def snapshot(self) -> dict:
        """A fully-detached view suitable for rendering."""
        busy_warps = sum(sm.busy_warps for sm in self.sms)
        total_warps = sum(sm.warp_count for sm in self.sms)
        return {
            "clock": self.clock,
            "kernels_submitted": self.kernels_submitted,
            "kernels_completed": self.kernels_completed,
            "overall_utilization": busy_warps / total_warps if total_warps else 0.0,
            "sms": [sm.snapshot() for sm in self.sms],
            "vram": self.vram.snapshot(),
            "scheduler": self.scheduler.snapshot(),
            "event_log": [
                {"clock": entry.clock, "message": entry.message}
                for entry in self._event_log
            ],
        }

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _tagged_name(self, kernel: Kernel) -> str:
        """A unique allocation tag per submission (handles repeat names)."""
        self._last_kernel_id += 1
        return f"{kernel.name}#{self._last_kernel_id}"

    def _dispatch_blocks(self) -> None:
        """Hand queued blocks to idle warps in a round-robin fashion."""
        if self.scheduler.pending_blocks == 0:
            return
        made_progress = True
        while made_progress and self.scheduler.pending_blocks > 0:
            made_progress = False
            for sm in self.sms:
                warp = sm.idle_warp()
                if warp is None:
                    continue
                block = self.scheduler.pop_ready()
                if block is None:
                    return
                warp.assign(block)
                if block.kernel.profile is WorkloadProfile.MEMORY:
                    sm.shared_memory.reserve(min(8 * 1024, sm.shared_memory.capacity_bytes))
                sm.register_file.reserve(
                    self.config.registers_per_thread * self.config.threads_per_warp // 2
                )
                made_progress = True

    def _account_for_finished_blocks(self, finished_count: int) -> None:
        """Update completion counters and release per-SM resources."""
        if finished_count == 0:
            # Release half the per-SM scratch each tick to fake decay.
            for sm in self.sms:
                sm.shared_memory.release(sm.shared_memory.used_bytes // 8)
            return
        remaining = finished_count
        for tag in list(self._kernel_block_counts):
            while remaining > 0 and self._kernel_block_counts[tag] > 0:
                self._kernel_block_counts[tag] -= 1
                remaining -= 1
                if self._kernel_block_counts[tag] == 0:
                    self.kernels_completed += 1
                    self.scheduler.completed_kernels += 1
                    short_name = tag.split("#", 1)[0]
                    self._log(f"done   {short_name}")
                    del self._kernel_block_counts[tag]
                    break
            if remaining == 0:
                break
        for sm in self.sms:
            if sm.busy_warps == 0:
                sm.register_file.release_all()

    def _log(self, message: str) -> None:
        self._event_log.append(EventLogEntry(clock=self.clock, message=message))

    # expose read-only pipeline order for UIs
    @staticmethod
    def pipeline_stages() -> tuple[PipelineStage, ...]:
        return PIPELINE_ORDER
