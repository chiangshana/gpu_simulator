"""Glue layer that runs the :class:`~gpu_simulator.cpu.CPU` and the virtual
:class:`~gpu_simulator.core.GPU` in lock-step and produces one
:class:`TraceRow` per simulated cycle.

The bridge wires three I/O ports into the CPU:

==========  ===============================================================
port        meaning
==========  ===============================================================
``0x40``    OUT — submit kernel by id (Rr value).  IN — read GPU status:
            ``0`` if all submitted kernels have finished, otherwise number
            of outstanding kernels (clamped to 0xFF).
``0x41``    OUT — supply an integer hint for the next kernel (used by
            ``hash`` / ``texture_load`` etc).  IN — number of completed
            kernels modulo 256.
``0xFF``    OUT — KWAIT marker; the bridge stalls the CPU until the GPU
            queue empties.
==========  ===============================================================

A real GPU pipeline obviously does much more, but these three ports
give the user a complete CPU-to-GPU interaction story for the trace tab.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from gpu_simulator.core import GPU
from gpu_simulator.cpu import CPU, GPU_PORT_HINT, GPU_PORT_LAUNCH, CycleResult, Instruction
from gpu_simulator.kernel import KernelLibrary

GPU_PORT_KWAIT = 0xFF

KERNEL_BY_ID: tuple[str, ...] = (
    "vector_add",
    "interpolation",
    "hash",
    "texture_load",
    "idle_compression",
    "app_launch",
    "page_nav",
)


def kernel_name_for_id(kernel_id: int) -> str:
    """Map an 8-bit kernel id to a kernel-library name (modulo table size)."""
    return KERNEL_BY_ID[kernel_id % len(KERNEL_BY_ID)]


@dataclass(frozen=True)
class TraceRow:
    """One row of the Tiny8-style execution table.

    Every field is a primitive so the row is trivial to serialise into
    SQLite / JSON / CSV.  ``register_changes`` is intentionally a list
    of (index, value) tuples rather than a dict — it preserves order
    and is JSON-friendly.
    """

    cycle: int
    pc: int
    instruction_text: str
    sreg_text: str
    register_changes: tuple[tuple[int, int], ...]
    gpu_summary: str
    cpu_halted: bool
    cpu_stalled: bool
    port_writes: tuple[tuple[int, int], ...]
    port_reads: tuple[tuple[int, int], ...]

    def to_dict(self) -> dict:
        return {
            "cycle": self.cycle,
            "pc": self.pc,
            "instruction": self.instruction_text,
            "sreg": self.sreg_text,
            "register_changes": [list(pair) for pair in self.register_changes],
            "gpu_summary": self.gpu_summary,
            "cpu_halted": self.cpu_halted,
            "cpu_stalled": self.cpu_stalled,
            "port_writes": [list(pair) for pair in self.port_writes],
            "port_reads": [list(pair) for pair in self.port_reads],
        }


@dataclass
class TraceLog:
    """Bounded ring buffer of :class:`TraceRow` rows."""

    capacity: int = 4096
    rows: deque[TraceRow] = field(default_factory=lambda: deque(maxlen=4096))

    def __post_init__(self) -> None:
        self.rows = deque(maxlen=self.capacity)

    def append(self, row: TraceRow) -> None:
        self.rows.append(row)

    def clear(self) -> None:
        self.rows.clear()

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)


# ---------------------------------------------------------------------------
# bridge
# ---------------------------------------------------------------------------
class CPUGPUBridge:
    """Owns one CPU and one GPU; advances them together one cycle at a time.

    The bridge is a stateful object so the UI can :meth:`reset` between
    program runs without re-creating the GPU (which is expensive when
    the user has accumulated session-store state).
    """

    def __init__(
        self,
        cpu: CPU | None = None,
        gpu: GPU | None = None,
        trace_capacity: int = 4096,
    ) -> None:
        self._cpu = cpu or CPU()
        self._gpu = gpu or GPU()
        self._cpu.port_in_handler = self._handle_port_in
        self._cpu.port_out_handler = self._handle_port_out
        self.trace = TraceLog(capacity=trace_capacity)
        self._history_capacity = trace_capacity
        # snapshot histories: index N = state at end of cycle N (per-step snapshots)
        self.register_history: list[tuple[int, ...]] = []
        self.memory_history: list[tuple[int, ...]] = []
        self.sreg_history: list[str] = []
        self._pending_hint: int = 0
        self._kernels_completed_seen: int = 0

    # ------------------------------------------------------------------
    # accessors
    # ------------------------------------------------------------------
    @property
    def cpu(self) -> CPU:
        return self._cpu

    @property
    def gpu(self) -> GPU:
        return self._gpu

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def load_program(self, instructions: list[Instruction]) -> None:
        self._cpu.load_program(instructions)
        self._pending_hint = 0
        self._kernels_completed_seen = self._gpu.kernels_completed
        self.trace.clear()
        self.register_history.clear()
        self.memory_history.clear()
        self.sreg_history.clear()

    def step(self) -> TraceRow:
        """Advance CPU + GPU one cycle and return the resulting trace row."""
        cpu_result = self._cpu.step()
        self._gpu.tick()
        row = self._build_trace_row(cpu_result)
        self.trace.append(row)
        self._record_snapshot()
        return row

    def run_until_halt(self, max_cycles: int = 5000) -> int:
        """Step until the CPU halts or ``max_cycles`` is reached.

        Returns the number of cycles actually executed.
        """
        cycles_executed = 0
        while cycles_executed < max_cycles:
            row = self.step()
            cycles_executed += 1
            if row.cpu_halted and not row.cpu_stalled:
                break
        return cycles_executed

    def reset(self) -> None:
        """Wipe trace + reset CPU; leaves the GPU instance alone."""
        self.trace.clear()
        self.register_history.clear()
        self.memory_history.clear()
        self.sreg_history.clear()
        self._cpu.load_program([])

    def _record_snapshot(self) -> None:
        """Append current register / memory / SREG to the histories."""
        self.register_history.append(tuple(self._cpu.registers))
        self.memory_history.append(tuple(self._cpu.memory))
        self.sreg_history.append(self._cpu.sreg.to_text())
        # cap each history at the trace log capacity to bound memory
        capacity = self._history_capacity
        for buffer in (self.register_history, self.memory_history, self.sreg_history):
            overflow = len(buffer) - capacity
            if overflow > 0:
                del buffer[:overflow]

    # ------------------------------------------------------------------
    # I/O port handlers — the heart of the CPU↔GPU contract
    # ------------------------------------------------------------------
    def _handle_port_in(self, port: int) -> int:
        if port == GPU_PORT_LAUNCH:
            outstanding = self._gpu.kernels_submitted - self._gpu.kernels_completed
            return min(max(outstanding, 0), 0xFF)
        if port == GPU_PORT_HINT:
            return self._gpu.kernels_completed & 0xFF
        return 0

    def _handle_port_out(self, port: int, value: int) -> None:
        if port == GPU_PORT_LAUNCH:
            kernel_name = kernel_name_for_id(value)
            kernel = KernelLibrary.build(
                kernel_name,
                trigger=f"asm:KLAUNCH({value})",
                hint=str(self._pending_hint) if self._pending_hint else "",
            )
            self._gpu.submit_kernel(kernel)
            self._pending_hint = 0
            return
        if port == GPU_PORT_HINT:
            self._pending_hint = value
            return
        if port == GPU_PORT_KWAIT:
            self._cpu.stall_until(self._gpu_busy)
            return

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _gpu_busy(self) -> bool:
        return self._gpu.kernels_submitted > self._gpu.kernels_completed

    def _build_trace_row(self, cpu_result: CycleResult) -> TraceRow:
        instruction_text = (
            cpu_result.instruction.source_text if cpu_result.instruction else "(end)"
        )
        return TraceRow(
            cycle=cpu_result.cycle,
            pc=cpu_result.pc_before,
            instruction_text=instruction_text,
            sreg_text=cpu_result.flag_text,
            register_changes=tuple(cpu_result.register_changes.items()),
            gpu_summary=self._summarise_gpu(),
            cpu_halted=cpu_result.halted,
            cpu_stalled=cpu_result.stalled,
            port_writes=tuple(cpu_result.port_writes),
            port_reads=tuple(cpu_result.port_reads),
        )

    def _summarise_gpu(self) -> str:
        """Produce a Tiny8-style short string like ``SM0.W0=F SM1.W0=D``."""
        parts: list[str] = []
        snapshot = self._gpu.snapshot()
        for sm in snapshot["sms"]:
            for warp in sm["warps"]:
                if warp["state"] == "idle":
                    continue
                stage_letter = warp["stage"][0].upper()
                parts.append(f"SM{sm['sm_id']}.W{warp['warp_id']}={stage_letter}")
                if len(parts) >= 4:  # keep the row narrow
                    parts.append("…")
                    return " ".join(parts)
        if not parts:
            return "idle"
        return " ".join(parts)
