"""Unit tests for gpu_simulator.cpu — CPU semantics + assembler."""

import pytest

from gpu_simulator.cpu import (
    CPU,
    NUM_REGISTERS,
    AssemblerError,
    Instruction,
    Opcode,
    StatusRegister,
    assemble,
)


# ---------------------------------------------------------------------------
# StatusRegister
# ---------------------------------------------------------------------------
def test_zero_flag_set_after_subtraction_to_zero():
    sreg = StatusRegister()
    sreg.update_arithmetic(7, 7, 0, is_subtraction=True)
    assert sreg.zero is True
    assert sreg.negative is False
    assert sreg.carry is False


def test_carry_flag_after_borrow():
    sreg = StatusRegister()
    sreg.update_arithmetic(2, 5, -3, is_subtraction=True)
    assert sreg.carry is True


def test_sreg_text_layout():
    sreg = StatusRegister(zero=True, negative=False, carry=True, overflow=False)
    assert sreg.to_text() == "Z-C-"


# ---------------------------------------------------------------------------
# assembler
# ---------------------------------------------------------------------------
def test_assemble_basic_program():
    program = assemble("""
        ldi r16, 5
        ldi r17, 3
        add r16, r17
        halt
    """)
    opcodes = [instr.opcode for instr in program]
    assert opcodes == [Opcode.LDI, Opcode.LDI, Opcode.ADD, Opcode.HALT]
    assert program[0].operands == (16, 5)
    assert program[1].operands == (17, 3)
    assert program[2].operands == (16, 17)


def test_assemble_resolves_labels():
    program = assemble("""
        ldi r16, 3
    loop:
        dec r16
        brne loop
        halt
    """)
    branch_instruction = program[2]
    assert branch_instruction.opcode is Opcode.BRNE
    # label resolves to PC of the dec instruction (index 1)
    assert branch_instruction.operands == (1,)


def test_assemble_klaunch_alias_expands_to_out():
    program = assemble("""
        ldi r16, 0
        klaunch r16
        halt
    """)
    out_instruction = program[1]
    assert out_instruction.opcode is Opcode.OUT
    assert out_instruction.operands == (0x40, 16)


def test_assemble_kwait_alias_expands_to_out_ff():
    program = assemble("kwait\nhalt\n")
    assert program[0].opcode is Opcode.OUT
    port, _ = program[0].operands
    assert port == 0xFF


def test_assemble_kstat_alias_expands_to_in():
    program = assemble("kstat r5\nhalt\n")
    assert program[0].opcode is Opcode.IN
    assert program[0].operands == (5, 0x40)


def test_assemble_rejects_unknown_opcode():
    with pytest.raises(AssemblerError):
        assemble("bogus r1, r2\nhalt\n")


def test_assemble_rejects_out_of_range_register():
    with pytest.raises(AssemblerError):
        assemble("ldi r99, 5\nhalt\n")


def test_assemble_supports_hex_and_binary_immediates():
    program = assemble("""
        ldi r0, 0xFF
        ldi r1, 0b00001111
        ldi r2, $A0
        halt
    """)
    assert program[0].operands == (0, 0xFF)
    assert program[1].operands == (1, 0x0F)
    assert program[2].operands == (2, 0xA0)


# ---------------------------------------------------------------------------
# CPU semantics
# ---------------------------------------------------------------------------
def test_ldi_writes_register_and_reports_change():
    cpu = CPU()
    cpu.load_program(assemble("ldi r16, 42\nhalt\n"))
    result = cpu.step()
    assert cpu.registers[16] == 42
    assert result.register_changes == {16: 42}


def test_add_sets_zero_flag_when_result_is_zero():
    cpu = CPU()
    cpu.load_program(assemble("""
        ldi r16, 1
        ldi r17, 255
        add r16, r17
        halt
    """))
    for _ in range(3):
        cpu.step()
    assert cpu.registers[16] == 0
    assert cpu.sreg.zero is True
    assert cpu.sreg.carry is True


def test_brne_loops_until_register_zero():
    cpu = CPU()
    cpu.load_program(assemble("""
        ldi r16, 3
    loop:
        dec r16
        brne loop
        halt
    """))
    for _ in range(50):
        cpu.step()
        if cpu.halted:
            break
    assert cpu.halted is True
    assert cpu.registers[16] == 0


def test_halt_stops_further_progress():
    cpu = CPU()
    cpu.load_program(assemble("halt\n"))
    cpu.step()
    assert cpu.halted is True
    saved_cycle = cpu.cycle
    cpu.step()  # no progress past halt
    assert cpu.halted is True
    assert cpu.cycle == saved_cycle + 1  # cycle still ticks


def test_in_out_port_handlers_are_called():
    cpu = CPU()
    received: list[tuple[int, int]] = []
    cpu.port_out_handler = lambda port, value: received.append((port, value))
    cpu.port_in_handler = lambda port: 99 if port == 0x10 else 0

    cpu.load_program(assemble("""
        ldi r0, 0x77
        out 0x20, r0
        in r1, 0x10
        halt
    """))
    while not cpu.halted:
        cpu.step()
    assert received == [(0x20, 0x77)]
    assert cpu.registers[1] == 99


def test_register_count_is_32():
    assert NUM_REGISTERS == 32
    cpu = CPU()
    assert len(cpu.registers) == 32


def test_instruction_dataclass_carries_source_text():
    program = assemble("ldi r0, 7\nhalt\n")
    assert isinstance(program[0], Instruction)
    assert "ldi r0, 7" in program[0].source_text
    assert program[0].line_number > 0
