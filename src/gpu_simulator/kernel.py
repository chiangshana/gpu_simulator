"""Kernel definitions and a small library of canned workloads.

A :class:`Kernel` is a plain dataclass describing *how* a simulated
workload will behave on the GPU rather than its actual instructions;
for a visualization toy this is more useful than a real shader ISA.

:class:`KernelLibrary` turns concrete user actions (mouse clicks,
keyboard events, focus changes, idle ticks) into kernels whose size,
duration, and profile match the "feel" of each action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorkloadProfile(Enum):
    """Abstract description of what the kernel stresses."""

    COMPUTE = "compute"      # ALU-bound
    MEMORY = "memory"        # bandwidth-bound
    MIXED = "mixed"          # balanced
    LIGHT = "light"          # minimal utilization


@dataclass(frozen=True)
class Kernel:
    """An abstract GPU workload ready to be dispatched.

    Attributes
    ----------
    name:
        Human-readable label shown in the event log.
    grid_size:
        Number of blocks in the grid. Larger grid → more SMs engaged.
    block_size:
        Threads per block (must be a multiple of ``warp_size`` in
        real CUDA; we simply split it into warps of 32).
    duration_ticks:
        Simulation ticks a single warp spends finishing this kernel.
    vram_bytes:
        Device memory temporarily reserved while the kernel runs.
    profile:
        High-level behavior tag used by the visualizer.
    trigger:
        Free-form description of the user action that spawned it.
    """

    name: str
    grid_size: int
    block_size: int
    duration_ticks: int
    vram_bytes: int
    profile: WorkloadProfile
    trigger: str = ""

    @property
    def total_threads(self) -> int:
        return self.grid_size * self.block_size


class KernelLibrary:
    """Factories that map user actions to representative kernels.

    All factory methods are classmethods so they can be used without
    instantiating the library.  The numbers are chosen to produce
    lively — but not overwhelming — visual feedback when used with
    the default :class:`~gpu_simulator.core.GPU` configuration.
    """

    WARP_SIZE = 32

    @classmethod
    def vector_add(cls, trigger: str = "mouse_click") -> Kernel:
        return Kernel(
            name="vector_add",
            grid_size=4,
            block_size=cls.WARP_SIZE * 2,
            duration_ticks=14,
            vram_bytes=2 * 1024 * 1024,
            profile=WorkloadProfile.COMPUTE,
            trigger=trigger,
        )

    @classmethod
    def interpolation(cls, trigger: str = "mouse_move") -> Kernel:
        return Kernel(
            name="interpolation",
            grid_size=2,
            block_size=cls.WARP_SIZE,
            duration_ticks=6,
            vram_bytes=512 * 1024,
            profile=WorkloadProfile.LIGHT,
            trigger=trigger,
        )

    @classmethod
    def hash_kernel(cls, key_repr: str, trigger: str = "keyboard") -> Kernel:
        return Kernel(
            name=f"hash({key_repr})",
            grid_size=3,
            block_size=cls.WARP_SIZE * 2,
            duration_ticks=10,
            vram_bytes=1 * 1024 * 1024,
            profile=WorkloadProfile.MIXED,
            trigger=trigger,
        )

    @classmethod
    def texture_load(cls, app_name: str, trigger: str = "focus_change") -> Kernel:
        return Kernel(
            name=f"texture_load:{app_name}",
            grid_size=8,
            block_size=cls.WARP_SIZE * 4,
            duration_ticks=22,
            vram_bytes=16 * 1024 * 1024,
            profile=WorkloadProfile.MEMORY,
            trigger=trigger,
        )

    @classmethod
    def idle_compression(cls, trigger: str = "idle") -> Kernel:
        return Kernel(
            name="idle_compression",
            grid_size=1,
            block_size=cls.WARP_SIZE,
            duration_ticks=30,
            vram_bytes=128 * 1024,
            profile=WorkloadProfile.LIGHT,
            trigger=trigger,
        )

    @classmethod
    def app_launch(cls, app_name: str, trigger: str = "app_launch") -> Kernel:
        """Emitted when a brand-new OS process appears.

        Simulates the burst of driver / shader / texture uploads that
        typically accompany an application start-up: long, memory-heavy,
        engages many SMs.
        """
        return Kernel(
            name=f"app_launch:{app_name}",
            grid_size=16,
            block_size=cls.WARP_SIZE * 4,
            duration_ticks=30,
            vram_bytes=24 * 1024 * 1024,
            profile=WorkloadProfile.MEMORY,
            trigger=trigger,
        )

    @classmethod
    def page_nav(cls, page_hint: str, trigger: str = "page_nav") -> Kernel:
        """Emitted when the foreground window title changes (e.g. a new URL).

        Simulates the DOM → texture → composition work of rendering a
        new web page; balanced compute + memory profile.
        """
        return Kernel(
            name=f"page_nav:{page_hint}",
            grid_size=6,
            block_size=cls.WARP_SIZE * 2,
            duration_ticks=16,
            vram_bytes=6 * 1024 * 1024,
            profile=WorkloadProfile.MIXED,
            trigger=trigger,
        )

    # ------------------------------------------------------------------
    # dispatcher used by EventListener + AppConfig trigger mapping
    # ------------------------------------------------------------------
    @classmethod
    def build(cls, kernel_name: str, *, trigger: str = "", hint: str = "") -> Kernel:
        """Build the named kernel; ``hint`` feeds the per-kernel label.

        Raises ``ValueError`` for unknown names so config validation
        can surface a clear error.
        """
        factories = {
            "vector_add": lambda: cls.vector_add(trigger=trigger or "mouse_click"),
            "interpolation": lambda: cls.interpolation(trigger=trigger or "mouse_move"),
            "hash": lambda: cls.hash_kernel(
                key_repr=hint or "?", trigger=trigger or "keyboard"
            ),
            "texture_load": lambda: cls.texture_load(
                app_name=hint or "app", trigger=trigger or "focus_change"
            ),
            "idle_compression": lambda: cls.idle_compression(
                trigger=trigger or "idle"
            ),
            "app_launch": lambda: cls.app_launch(
                app_name=hint or "app", trigger=trigger or "app_launch"
            ),
            "page_nav": lambda: cls.page_nav(
                page_hint=hint or "page", trigger=trigger or "page_nav"
            ),
        }
        if kernel_name not in factories:
            raise ValueError(
                f"unknown kernel {kernel_name!r}; "
                f"valid choices: {sorted(factories)}"
            )
        return factories[kernel_name]()
