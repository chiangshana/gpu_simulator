"""Bridge between the **full** Tiny8 CPU and the virtual GPU.

The third-round bridge in :mod:`gpu_simulator.bridge` uses our minimal
in-tree CPU.  This module instead drives the **vendored upstream
Tiny8** so that the entire 60+ instruction ISA is available — `MUL`,
`DIV`, `LSL`, `ROL`, `BRGE`, `RJMP`, `CALL`/`RET`, `PUSH`/`POP`, etc.

The GPU is wired in via Tiny8's natural I/O path: every ``OUT port,
Rr`` invokes :meth:`tiny8.cpu.CPU.write_ram`.  We subclass CPU and
intercept writes to three magic addresses:

==========  ==================================================================
address     meaning
==========  ==================================================================
``0x40``    submit a kernel by id (just like the subset bridge)
``0x41``    set an integer hint for the next kernel
``0xFF``    KWAIT — stall the CPU until the GPU drains its queue
==========  ==================================================================

That means user assembly code can talk to the GPU using ``OUT 0x40,
R0`` / ``OUT 0xFF, R0`` and gets full Tiny8 in return.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from gpu_simulator.bridge import (
    GPU_PORT_KWAIT,
    kernel_name_for_id,
)
from gpu_simulator.core import GPU
from gpu_simulator.cpu import GPU_PORT_HINT, GPU_PORT_LAUNCH
from gpu_simulator.kernel import KernelLibrary
from gpu_simulator.tiny8_full import CPU as Tiny8CPU
from gpu_simulator.tiny8_full import Memory as Tiny8Memory
from gpu_simulator.tiny8_full import assemble as tiny8_assemble
from gpu_simulator.tiny8_full.cpu import SREG_C, SREG_N, SREG_V, SREG_Z


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def sreg_text(cpu: Tiny8CPU) -> str:
    """Return a Tiny8-style 4-char SREG snapshot (Z N C V)."""
    return "".join(
        (
            "Z" if cpu.get_flag(SREG_Z) else "-",
            "N" if cpu.get_flag(SREG_N) else "-",
            "C" if cpu.get_flag(SREG_C) else "-",
            "V" if cpu.get_flag(SREG_V) else "-",
        )
    )


# ---------------------------------------------------------------------------
# trace row (separate from gpu_simulator.bridge.TraceRow because the upstream CPU
# expresses instructions slightly differently)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FullTraceRow:
    """One per-step trace entry for the full-Tiny8 bridge."""

    step: int
    pc: int
    instruction_text: str
    sreg_text: str
    register_changes: tuple[tuple[int, int], ...]
    memory_changes: tuple[tuple[int, int], ...]
    gpu_summary: str
    cpu_halted: bool
    cpu_stalled: bool
    port_writes: tuple[tuple[int, int], ...]


# ---------------------------------------------------------------------------
# CPU subclass that talks to the GPU
# ---------------------------------------------------------------------------
class FullTiny8CPU(Tiny8CPU):
    """Tiny8 CPU with three magic RAM addresses wired to the virtual GPU.

    Writes to ``0x40`` / ``0x41`` / ``0xFF`` are intercepted *before*
    falling through to the underlying Memory, so the GPU sees the value
    but the address is also still a normal RAM cell (and thus shows up
    in the existing Tiny8 memory trace machinery).
    """

    GPU_PORTS: frozenset[int] = frozenset(
        {GPU_PORT_LAUNCH, GPU_PORT_HINT, GPU_PORT_KWAIT}
    )

    def __init__(self, memory: Tiny8Memory | None = None) -> None:
        super().__init__(memory)
        self._port_writer = None  # type: callable | None
        self._port_reader = None  # type: callable | None

    def attach_port_handlers(self, *, on_write, on_read) -> None:
        self._port_writer = on_write
        self._port_reader = on_read

    # ------------------------------------------------------------------
    # overridden hooks
    # ------------------------------------------------------------------
    def write_ram(self, addr: int, val: int) -> None:
        super().write_ram(addr, val)
        if addr in self.GPU_PORTS and self._port_writer is not None:
            self._port_writer(addr, val & 0xFF)

    def read_ram(self, addr: int) -> int:
        if addr in self.GPU_PORTS and self._port_reader is not None:
            value = self._port_reader(addr)
            # mirror back into RAM so subsequent IN instructions stay consistent
            super().write_ram(addr, value & 0xFF)
            return value & 0xFF
        return super().read_ram(addr)


# ---------------------------------------------------------------------------
# Bridge — pairs FullTiny8CPU with a virtual GPU
# ---------------------------------------------------------------------------
@dataclass
class FullTraceLog:
    """Bounded ring buffer for :class:`FullTraceRow`."""

    capacity: int = 4096
    rows: deque[FullTraceRow] = field(
        default_factory=lambda: deque(maxlen=4096)
    )

    def __post_init__(self) -> None:
        self.rows = deque(maxlen=self.capacity)

    def append(self, row: FullTraceRow) -> None:
        self.rows.append(row)

    def clear(self) -> None:
        self.rows.clear()

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)


class FullCPUGPUBridge:
    """Drive a vendored Tiny8 CPU and a virtual GPU together, one step at a time.

    The bridge keeps full register and memory snapshots per step so the
    UI can render Tiny8-style heatmaps over the entire run.
    """

    DEFAULT_HISTORY_CAPACITY: int = 4096

    def __init__(
        self,
        cpu: FullTiny8CPU | None = None,
        gpu: GPU | None = None,
        history_capacity: int | None = None,
    ) -> None:
        self._gpu = gpu or GPU()
        self._cpu = cpu or FullTiny8CPU()
        self._cpu.attach_port_handlers(
            on_write=self._on_port_write, on_read=self._on_port_read
        )
        self._capacity = history_capacity or self.DEFAULT_HISTORY_CAPACITY
        self.trace: FullTraceLog = FullTraceLog(capacity=self._capacity)
        self.register_history: list[tuple[int, ...]] = []
        self.memory_history: list[tuple[int, ...]] = []
        self.sreg_history: list[str] = []
        self._pending_hint: int = 0
        self._stall_active: bool = False
        self._latest_port_writes: list[tuple[int, int]] = []
        self._previous_registers: tuple[int, ...] | None = None
        self._previous_memory: tuple[int, ...] | None = None

    # ------------------------------------------------------------------
    # accessors
    # ------------------------------------------------------------------
    @property
    def cpu(self) -> FullTiny8CPU:
        return self._cpu

    @property
    def gpu(self) -> GPU:
        return self._gpu

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def load_source(self, source: str) -> None:
        program = tiny8_assemble(source)
        self._cpu.load_program(program)
        self.trace.clear()
        self.register_history.clear()
        self.memory_history.clear()
        self.sreg_history.clear()
        self._pending_hint = 0
        self._stall_active = False
        self._previous_registers = tuple(self._cpu.regs)
        self._previous_memory = self._snapshot_memory_window()

    def step(self) -> FullTraceRow:
        """Advance CPU + GPU by one step and return the resulting row."""
        pc_before = self._cpu.pc
        instruction_text = self._format_instruction_at(pc_before)
        self._latest_port_writes = []

        if self._stall_active:
            # CPU is held during KWAIT — only the GPU advances.
            self._gpu.tick()
            if not self._gpu_busy():
                self._stall_active = False
            row = self._make_row(
                pc=pc_before,
                instruction_text="; KWAIT (stalled)",
                cpu_halted=False,
                cpu_stalled=True,
                executed=False,
            )
            self.trace.append(row)
            self._record_history()
            return row

        executed = self._cpu.step()
        self._gpu.tick()

        row = self._make_row(
            pc=pc_before,
            instruction_text=instruction_text if executed else "(end)",
            cpu_halted=not executed,
            cpu_stalled=False,
            executed=executed,
        )
        self.trace.append(row)
        self._record_history()
        return row

    def run_until_halt(self, max_steps: int = 5000) -> int:
        steps_executed = 0
        while steps_executed < max_steps:
            row = self.step()
            steps_executed += 1
            if row.cpu_halted and not row.cpu_stalled:
                break
        return steps_executed

    def reset(self) -> None:
        self.trace.clear()
        self.register_history.clear()
        self.memory_history.clear()
        self.sreg_history.clear()
        self._pending_hint = 0
        self._stall_active = False
        # rebuild a fresh CPU to wipe trace lists
        self._cpu = FullTiny8CPU()
        self._cpu.attach_port_handlers(
            on_write=self._on_port_write, on_read=self._on_port_read
        )

    # ------------------------------------------------------------------
    # I/O port handlers
    # ------------------------------------------------------------------
    def _on_port_write(self, port: int, value: int) -> None:
        self._latest_port_writes.append((port, value))
        if port == GPU_PORT_LAUNCH:
            kernel_name = kernel_name_for_id(value)
            kernel = KernelLibrary.build(
                kernel_name,
                trigger=f"tiny8:OUT 0x40 ({value})",
                hint=str(self._pending_hint) if self._pending_hint else "",
            )
            self._gpu.submit_kernel(kernel)
            self._pending_hint = 0
            return
        if port == GPU_PORT_HINT:
            self._pending_hint = value
            return
        if port == GPU_PORT_KWAIT:
            self._stall_active = self._gpu_busy()

    def _on_port_read(self, port: int) -> int:
        if port == GPU_PORT_LAUNCH:
            outstanding = self._gpu.kernels_submitted - self._gpu.kernels_completed
            return min(max(outstanding, 0), 0xFF)
        if port == GPU_PORT_HINT:
            return self._gpu.kernels_completed & 0xFF
        return 0

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _gpu_busy(self) -> bool:
        return self._gpu.kernels_submitted > self._gpu.kernels_completed

    def _format_instruction_at(self, pc: int) -> str:
        if pc < 0 or pc >= len(self._cpu.program):
            return "(end)"
        mnemonic, operands = self._cpu.program[pc]
        formatted_operands = []
        for operand in operands:
            if isinstance(operand, tuple) and len(operand) == 2 and operand[0] == "reg":
                formatted_operands.append(f"R{operand[1]}")
            else:
                formatted_operands.append(str(operand))
        return f"{mnemonic.upper()} {', '.join(formatted_operands)}".strip()

    def _snapshot_memory_window(self, start: int = 0, end: int = 256) -> tuple[int, ...]:
        return tuple(self._cpu.read_ram(addr) for addr in range(start, end))

    def _make_row(
        self,
        *,
        pc: int,
        instruction_text: str,
        cpu_halted: bool,
        cpu_stalled: bool,
        executed: bool,
    ) -> FullTraceRow:
        registers = tuple(self._cpu.regs)
        memory_window = self._snapshot_memory_window()
        register_changes: list[tuple[int, int]] = []
        memory_changes: list[tuple[int, int]] = []
        if self._previous_registers is not None:
            for index, (current, before) in enumerate(
                zip(registers, self._previous_registers, strict=False)
            ):
                if current != before:
                    register_changes.append((index, current))
        if self._previous_memory is not None:
            for index, (current, before) in enumerate(
                zip(memory_window, self._previous_memory, strict=False)
            ):
                if current != before:
                    memory_changes.append((index, current))
        self._previous_registers = registers
        self._previous_memory = memory_window
        return FullTraceRow(
            step=self._cpu.step_count if executed else self._cpu.step_count + 1,
            pc=pc,
            instruction_text=instruction_text,
            sreg_text=sreg_text(self._cpu),
            register_changes=tuple(register_changes),
            memory_changes=tuple(memory_changes),
            gpu_summary=self._summarise_gpu(),
            cpu_halted=cpu_halted,
            cpu_stalled=cpu_stalled,
            port_writes=tuple(self._latest_port_writes),
        )

    def _summarise_gpu(self) -> str:
        """Same lightweight one-line GPU snapshot as the subset bridge."""
        snapshot = self._gpu.snapshot()
        parts: list[str] = []
        for sm in snapshot["sms"]:
            for warp in sm["warps"]:
                if warp["state"] == "idle":
                    continue
                stage_letter = warp["stage"][0].upper()
                parts.append(f"SM{sm['sm_id']}.W{warp['warp_id']}={stage_letter}")
                if len(parts) >= 4:
                    parts.append("…")
                    return " ".join(parts)
        if not parts:
            return "idle"
        return " ".join(parts)

    def _record_history(self) -> None:
        self.register_history.append(tuple(self._cpu.regs))
        self.memory_history.append(self._snapshot_memory_window())
        self.sreg_history.append(sreg_text(self._cpu))
        for buffer in (self.register_history, self.memory_history, self.sreg_history):
            overflow = len(buffer) - self._capacity
            if overflow > 0:
                del buffer[:overflow]


# ---------------------------------------------------------------------------
# convenience entry point
# ---------------------------------------------------------------------------
def assemble_file(path: Path | str) -> str:
    """Load the source text of a vendored Tiny8 .asm file."""
    return Path(path).read_text(encoding="utf-8")
