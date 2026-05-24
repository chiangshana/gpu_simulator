"""A small Tiny8-flavoured CPU with a built-in assembler.

This module is self-contained: it does not import the upstream
``tiny8`` package because we want the project to keep working on
brand-new Python releases that may not have a ``tiny8`` wheel yet,
and we also need to bolt on a few GPU-bridge mnemonics
(:data:`KLAUNCH` / :data:`KWAIT` / :data:`KSTAT`) that Tiny8 itself
does not ship.

The ISA is a subset of Tiny8 / AVR:

==========  ====================================================
mnemonic    behaviour
==========  ====================================================
LDI Rd, K   Rd ← K (8-bit immediate, 0–255)
MOV Rd, Rr  Rd ← Rr
ADD Rd, Rr  Rd ← Rd + Rr  (updates Z, N, C, V)
SUB Rd, Rr  Rd ← Rd − Rr  (updates Z, N, C, V)
INC Rd      Rd ← Rd + 1   (updates Z, N, V)
DEC Rd      Rd ← Rd − 1   (updates Z, N, V)
CP  Rd, Rr  flags ← Rd − Rr (Rd unchanged)
CPI Rd, K   flags ← Rd − K  (Rd unchanged)
JMP label   PC ← label
BRNE label  PC ← label if Z = 0
BREQ label  PC ← label if Z = 1
NOP         no operation
HALT        stop the CPU
IN  Rd, p   Rd ← read_port(p)         — handler is supplied by the bridge
OUT p,  Rr  write_port(p, Rr)         — handler is supplied by the bridge
KLAUNCH Rr  alias for OUT 0x40, Rr    (kernel id in Rr)
KWAIT       alias for poll(IN 0x40)   until status == 0
KSTAT Rd    alias for IN  Rd, 0x40
==========  ====================================================

Flags live in :class:`StatusRegister` and are updated only by the
arithmetic / compare instructions, mirroring Tiny8.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from gpu_simulator.exceptions import GPUVizError

NUM_REGISTERS = 32
MEMORY_SIZE = 256  # 256-byte flat data memory (Tiny8 ships 2 KiB; we shrink to keep heatmaps readable)
GPU_PORT_LAUNCH = 0x40
GPU_PORT_HINT = 0x41


class AssemblerError(GPUVizError):
    """Raised when source code cannot be assembled."""

    def __init__(self, line_number: int, message: str) -> None:
        self.line_number = line_number
        super().__init__(f"line {line_number}: {message}")


class CPUExecutionError(GPUVizError):
    """Raised when the CPU encounters an illegal runtime condition."""


# ---------------------------------------------------------------------------
# status register
# ---------------------------------------------------------------------------
@dataclass
class StatusRegister:
    """SREG with the four flags this subset exercises (Z, N, C, V)."""

    zero: bool = False
    negative: bool = False
    carry: bool = False
    overflow: bool = False

    def update_logic(self, result: int) -> None:
        masked = result & 0xFF
        self.zero = masked == 0
        self.negative = bool(masked & 0x80)

    def update_arithmetic(self, lhs: int, rhs: int, result: int, *, is_subtraction: bool) -> None:
        masked = result & 0xFF
        self.zero = masked == 0
        self.negative = bool(masked & 0x80)
        if is_subtraction:
            self.carry = lhs < rhs
            self.overflow = (
                ((lhs ^ rhs) & 0x80) != 0 and ((lhs ^ masked) & 0x80) != 0
            )
        else:
            self.carry = result > 0xFF
            self.overflow = (
                ((lhs ^ rhs) & 0x80) == 0 and ((lhs ^ masked) & 0x80) != 0
            )

    def to_text(self) -> str:
        return "".join(
            (
                "Z" if self.zero else "-",
                "N" if self.negative else "-",
                "C" if self.carry else "-",
                "V" if self.overflow else "-",
            )
        )


# ---------------------------------------------------------------------------
# instructions
# ---------------------------------------------------------------------------
class Opcode(Enum):
    LDI = "LDI"
    MOV = "MOV"
    ADD = "ADD"
    SUB = "SUB"
    INC = "INC"
    DEC = "DEC"
    CP = "CP"
    CPI = "CPI"
    JMP = "JMP"
    BRNE = "BRNE"
    BREQ = "BREQ"
    NOP = "NOP"
    HALT = "HALT"
    IN = "IN"
    OUT = "OUT"
    LD = "LD"
    ST = "ST"
    LDS = "LDS"
    STS = "STS"


@dataclass(frozen=True)
class Instruction:
    """One assembled instruction.

    ``operands`` interpretation depends on the opcode:

    - LDI / CPI:   (Rd, immediate)
    - MOV / ADD / SUB / CP: (Rd, Rr)
    - INC / DEC:   (Rd,)
    - JMP / BRNE / BREQ: (target_pc,)
    - IN:          (Rd, port)
    - OUT:         (port, Rr)
    - NOP / HALT:  ()
    """

    opcode: Opcode
    operands: tuple[int, ...]
    source_text: str
    line_number: int


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------
@dataclass
class CycleResult:
    """What changed during the most recent :meth:`CPU.step` call."""

    cycle: int
    pc_before: int
    pc_after: int
    instruction: Instruction | None
    register_changes: dict[int, int] = field(default_factory=dict)
    memory_changes: dict[int, int] = field(default_factory=dict)
    flag_text: str = "----"
    halted: bool = False
    stalled: bool = False
    port_writes: list[tuple[int, int]] = field(default_factory=list)
    port_reads: list[tuple[int, int]] = field(default_factory=list)


class CPU:
    """Tiny8-subset 8-bit CPU with pluggable I/O port handlers.

    The CPU does not know anything about the GPU.  The bridge wires
    :attr:`port_in_handler` and :attr:`port_out_handler` to translate
    `IN`/`OUT` into kernel submissions.
    """

    def __init__(self) -> None:
        self.registers: list[int] = [0] * NUM_REGISTERS
        self.memory: list[int] = [0] * MEMORY_SIZE
        self.sreg = StatusRegister()
        self.pc: int = 0
        self.cycle: int = 0
        self.halted: bool = False
        self.stalled: bool = False
        self.program: list[Instruction] = []
        # bridge hooks — defaults that just return 0 / do nothing
        self.port_in_handler = self._default_port_in
        self.port_out_handler = self._default_port_out
        # the bridge can ask the CPU to spin on a port until a predicate
        # holds — used to implement KWAIT without modifying the ISA
        self._wait_predicate = None

    # ------------------------------------------------------------------
    # program loading
    # ------------------------------------------------------------------
    def load_program(self, instructions: list[Instruction]) -> None:
        self.program = list(instructions)
        self.pc = 0
        self.cycle = 0
        self.halted = False
        self.stalled = False
        self.registers = [0] * NUM_REGISTERS
        self.memory = [0] * MEMORY_SIZE
        self.sreg = StatusRegister()
        self._wait_predicate = None

    # ------------------------------------------------------------------
    # execution
    # ------------------------------------------------------------------
    def step(self) -> CycleResult:
        """Advance the CPU by one cycle and report what changed."""
        pc_before = self.pc
        if self.halted or self.pc >= len(self.program):
            self.cycle += 1
            return CycleResult(
                cycle=self.cycle,
                pc_before=pc_before,
                pc_after=self.pc,
                instruction=None,
                halted=True,
            )

        if self._wait_predicate is not None:
            if self._wait_predicate():
                self.cycle += 1
                return CycleResult(
                    cycle=self.cycle,
                    pc_before=pc_before,
                    pc_after=self.pc,
                    instruction=Instruction(Opcode.NOP, (), "; KWAIT (stalled)", 0),
                    flag_text=self.sreg.to_text(),
                    stalled=True,
                )
            self._wait_predicate = None
            self.stalled = False

        instruction = self.program[self.pc]
        register_snapshot_before = list(self.registers)
        memory_snapshot_before = list(self.memory)
        port_writes: list[tuple[int, int]] = []
        port_reads: list[tuple[int, int]] = []

        try:
            self._execute(instruction, port_writes, port_reads)
        except CPUExecutionError:
            self.halted = True
            raise

        register_changes = {
            index: self.registers[index]
            for index in range(NUM_REGISTERS)
            if self.registers[index] != register_snapshot_before[index]
        }
        memory_changes = {
            address: self.memory[address]
            for address in range(MEMORY_SIZE)
            if self.memory[address] != memory_snapshot_before[address]
        }
        self.cycle += 1
        return CycleResult(
            cycle=self.cycle,
            pc_before=pc_before,
            pc_after=self.pc,
            instruction=instruction,
            register_changes=register_changes,
            memory_changes=memory_changes,
            flag_text=self.sreg.to_text(),
            halted=self.halted,
            stalled=self.stalled,
            port_writes=port_writes,
            port_reads=port_reads,
        )

    # ------------------------------------------------------------------
    # bridge helpers
    # ------------------------------------------------------------------
    def stall_until(self, predicate) -> None:
        """Make the CPU spin (cycle-by-cycle) while ``predicate()`` is true.

        The bridge calls this from inside an ``OUT`` handler to model
        ``KWAIT`` as a busy-wait without inventing a new opcode.
        """
        self._wait_predicate = predicate
        self.stalled = True

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------
    def _execute(
        self,
        instruction: Instruction,
        port_writes: list[tuple[int, int]],
        port_reads: list[tuple[int, int]],
    ) -> None:
        opcode = instruction.opcode
        operands = instruction.operands
        next_pc = self.pc + 1

        if opcode is Opcode.LDI:
            destination, immediate = operands
            self.registers[destination] = immediate & 0xFF
        elif opcode is Opcode.MOV:
            destination, source = operands
            self.registers[destination] = self.registers[source]
        elif opcode is Opcode.ADD:
            destination, source = operands
            lhs = self.registers[destination]
            rhs = self.registers[source]
            result = lhs + rhs
            self.registers[destination] = result & 0xFF
            self.sreg.update_arithmetic(lhs, rhs, result, is_subtraction=False)
        elif opcode is Opcode.SUB:
            destination, source = operands
            lhs = self.registers[destination]
            rhs = self.registers[source]
            result = lhs - rhs
            self.registers[destination] = result & 0xFF
            self.sreg.update_arithmetic(lhs, rhs, result, is_subtraction=True)
        elif opcode is Opcode.INC:
            (destination,) = operands
            lhs = self.registers[destination]
            result = lhs + 1
            self.registers[destination] = result & 0xFF
            self.sreg.update_arithmetic(lhs, 1, result, is_subtraction=False)
        elif opcode is Opcode.DEC:
            (destination,) = operands
            lhs = self.registers[destination]
            result = lhs - 1
            self.registers[destination] = result & 0xFF
            self.sreg.update_arithmetic(lhs, 1, result, is_subtraction=True)
        elif opcode is Opcode.CP:
            destination, source = operands
            lhs = self.registers[destination]
            rhs = self.registers[source]
            self.sreg.update_arithmetic(lhs, rhs, lhs - rhs, is_subtraction=True)
        elif opcode is Opcode.CPI:
            destination, immediate = operands
            lhs = self.registers[destination]
            self.sreg.update_arithmetic(lhs, immediate, lhs - immediate, is_subtraction=True)
        elif opcode is Opcode.JMP:
            (target,) = operands
            next_pc = target
        elif opcode is Opcode.BRNE:
            (target,) = operands
            if not self.sreg.zero:
                next_pc = target
        elif opcode is Opcode.BREQ:
            (target,) = operands
            if self.sreg.zero:
                next_pc = target
        elif opcode is Opcode.NOP:
            pass
        elif opcode is Opcode.HALT:
            self.halted = True
        elif opcode is Opcode.IN:
            destination, port = operands
            value = int(self.port_in_handler(port)) & 0xFF
            self.registers[destination] = value
            port_reads.append((port, value))
        elif opcode is Opcode.OUT:
            port, source = operands
            value = self.registers[source] & 0xFF
            port_writes.append((port, value))
            self.port_out_handler(port, value)
        elif opcode is Opcode.LD:
            destination, address_register = operands
            address = self.registers[address_register] & (MEMORY_SIZE - 1)
            self.registers[destination] = self.memory[address]
        elif opcode is Opcode.ST:
            address_register, source = operands
            address = self.registers[address_register] & (MEMORY_SIZE - 1)
            self.memory[address] = self.registers[source] & 0xFF
        elif opcode is Opcode.LDS:
            destination, address = operands
            self.registers[destination] = self.memory[address & (MEMORY_SIZE - 1)]
        elif opcode is Opcode.STS:
            address, source = operands
            self.memory[address & (MEMORY_SIZE - 1)] = self.registers[source] & 0xFF
        else:  # pragma: no cover - exhaustive
            raise CPUExecutionError(f"unimplemented opcode {opcode}")

        # The OUT instruction itself completed successfully even when its
        # handler asks the CPU to start busy-waiting; the wait is observed
        # on the NEXT call to step(), so PC must advance now.
        if not self.halted:
            self.pc = next_pc

    def _default_port_in(self, port: int) -> int:  # noqa: ARG002
        return 0

    def _default_port_out(self, port: int, value: int) -> None:  # noqa: ARG002
        return None


# ---------------------------------------------------------------------------
# assembler
# ---------------------------------------------------------------------------
_REGISTER_PATTERN = re.compile(r"^[Rr](\d{1,2})$")
_LABEL_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$")
_NUMBER_PATTERN = re.compile(
    r"^(?:0[xX][0-9A-Fa-f]+|0[bB][01]+|\$[0-9A-Fa-f]+|-?\d+)$"
)


def _parse_register(token: str, line_number: int) -> int:
    match = _REGISTER_PATTERN.match(token)
    if not match:
        raise AssemblerError(line_number, f"expected register, got {token!r}")
    index = int(match.group(1))
    if not 0 <= index < NUM_REGISTERS:
        raise AssemblerError(line_number, f"register out of range: {token!r}")
    return index


def _parse_immediate(token: str, line_number: int) -> int:
    if not _NUMBER_PATTERN.match(token):
        raise AssemblerError(line_number, f"expected number, got {token!r}")
    if token.startswith("$"):
        return int(token[1:], 16)
    return int(token, 0)


def _strip_comment(line: str) -> str:
    semicolon = line.find(";")
    if semicolon != -1:
        line = line[:semicolon]
    return line.strip()


def _normalise_aliases(operation: str, operands: list[str]) -> tuple[str, list[str]]:
    """Translate KLAUNCH / KWAIT / KSTAT into IN/OUT pairs."""
    op = operation.upper()
    if op == "KLAUNCH":
        if len(operands) != 1:
            raise AssemblerError(0, "KLAUNCH takes one operand (Rr)")
        return "OUT", [hex(GPU_PORT_LAUNCH), operands[0]]
    if op == "KSTAT":
        if len(operands) != 1:
            raise AssemblerError(0, "KSTAT takes one operand (Rd)")
        return "IN", [operands[0], hex(GPU_PORT_LAUNCH)]
    if op == "KWAIT":
        if operands:
            raise AssemblerError(0, "KWAIT takes no operands")
        # KWAIT becomes "OUT 0xFF, R0" — the bridge recognises 0xFF as
        # "stall the CPU until the GPU is idle" without touching R0.
        return "OUT", ["0xFF", "R0"]
    return operation, operands


def assemble(source: str) -> list[Instruction]:
    """Assemble ``source`` into a list of :class:`Instruction`."""
    raw_lines = source.splitlines()
    label_to_pc: dict[str, int] = {}
    pending: list[tuple[int, str, list[str], str]] = []  # (line_no, op, operands, raw)

    instruction_index = 0
    for line_number, raw_line in enumerate(raw_lines, start=1):
        stripped = _strip_comment(raw_line)
        if not stripped:
            continue
        label_match = _LABEL_PATTERN.match(stripped)
        if label_match:
            label = label_match.group(1)
            if label in label_to_pc:
                raise AssemblerError(line_number, f"duplicate label {label!r}")
            label_to_pc[label] = instruction_index
            continue
        # split operation and operands
        head, _, tail = stripped.partition(" ")
        operands_text = tail.strip()
        operands = (
            [token.strip() for token in operands_text.split(",")]
            if operands_text
            else []
        )
        try:
            operation, operands = _normalise_aliases(head, operands)
        except AssemblerError as exc:
            raise AssemblerError(line_number, str(exc).split(": ", 1)[-1]) from exc
        pending.append((line_number, operation.upper(), operands, stripped))
        instruction_index += 1

    instructions: list[Instruction] = []
    for line_number, operation, operands, raw in pending:
        try:
            instructions.append(
                _build_instruction(line_number, operation, operands, raw, label_to_pc)
            )
        except AssemblerError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise AssemblerError(line_number, f"internal error: {exc}") from exc
    return instructions


def _build_instruction(
    line_number: int,
    operation: str,
    operands: list[str],
    raw: str,
    label_to_pc: dict[str, int],
) -> Instruction:
    if operation == "LDI":
        _expect_arity(operation, operands, 2, line_number)
        destination = _parse_register(operands[0], line_number)
        immediate = _parse_immediate(operands[1], line_number) & 0xFF
        return Instruction(Opcode.LDI, (destination, immediate), raw, line_number)
    if operation in {"MOV", "ADD", "SUB", "CP"}:
        _expect_arity(operation, operands, 2, line_number)
        destination = _parse_register(operands[0], line_number)
        source = _parse_register(operands[1], line_number)
        return Instruction(Opcode[operation], (destination, source), raw, line_number)
    if operation == "CPI":
        _expect_arity(operation, operands, 2, line_number)
        destination = _parse_register(operands[0], line_number)
        immediate = _parse_immediate(operands[1], line_number) & 0xFF
        return Instruction(Opcode.CPI, (destination, immediate), raw, line_number)
    if operation in {"INC", "DEC"}:
        _expect_arity(operation, operands, 1, line_number)
        destination = _parse_register(operands[0], line_number)
        return Instruction(Opcode[operation], (destination,), raw, line_number)
    if operation in {"JMP", "BRNE", "BREQ"}:
        _expect_arity(operation, operands, 1, line_number)
        target_token = operands[0]
        target = label_to_pc.get(target_token)
        if target is None:
            target = _parse_immediate(target_token, line_number)
        return Instruction(Opcode[operation], (target,), raw, line_number)
    if operation == "NOP":
        _expect_arity(operation, operands, 0, line_number)
        return Instruction(Opcode.NOP, (), raw, line_number)
    if operation == "HALT":
        _expect_arity(operation, operands, 0, line_number)
        return Instruction(Opcode.HALT, (), raw, line_number)
    if operation == "IN":
        _expect_arity(operation, operands, 2, line_number)
        destination = _parse_register(operands[0], line_number)
        port = _parse_immediate(operands[1], line_number) & 0xFF
        return Instruction(Opcode.IN, (destination, port), raw, line_number)
    if operation == "OUT":
        _expect_arity(operation, operands, 2, line_number)
        port = _parse_immediate(operands[0], line_number) & 0xFF
        source = _parse_register(operands[1], line_number)
        return Instruction(Opcode.OUT, (port, source), raw, line_number)
    if operation == "LD":
        _expect_arity(operation, operands, 2, line_number)
        destination = _parse_register(operands[0], line_number)
        address_register = _parse_register(operands[1], line_number)
        return Instruction(Opcode.LD, (destination, address_register), raw, line_number)
    if operation == "ST":
        _expect_arity(operation, operands, 2, line_number)
        address_register = _parse_register(operands[0], line_number)
        source = _parse_register(operands[1], line_number)
        return Instruction(Opcode.ST, (address_register, source), raw, line_number)
    if operation == "LDS":
        _expect_arity(operation, operands, 2, line_number)
        destination = _parse_register(operands[0], line_number)
        address = _parse_immediate(operands[1], line_number) & (MEMORY_SIZE - 1)
        return Instruction(Opcode.LDS, (destination, address), raw, line_number)
    if operation == "STS":
        _expect_arity(operation, operands, 2, line_number)
        address = _parse_immediate(operands[0], line_number) & (MEMORY_SIZE - 1)
        source = _parse_register(operands[1], line_number)
        return Instruction(Opcode.STS, (address, source), raw, line_number)
    raise AssemblerError(line_number, f"unknown opcode {operation!r}")


def _expect_arity(operation: str, operands: list[str], expected: int, line_number: int) -> None:
    if len(operands) != expected:
        raise AssemblerError(
            line_number,
            f"{operation} expects {expected} operand(s), got {len(operands)}",
        )
