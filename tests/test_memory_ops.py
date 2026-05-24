"""Tests for the new LD / ST / LDS / STS instructions and the bridge histories."""

from gpu_simulator.bridge import CPUGPUBridge
from gpu_simulator.cpu import CPU, MEMORY_SIZE, NUM_REGISTERS, Opcode, assemble


def test_st_writes_register_value_to_memory_address_in_register():
    cpu = CPU()
    cpu.load_program(assemble("""
        ldi r16, 0x60
        ldi r17, 99
        st  r16, r17
        halt
    """))
    while not cpu.halted:
        cpu.step()
    assert cpu.memory[0x60] == 99


def test_ld_reads_memory_at_address_held_in_register():
    cpu = CPU()
    cpu.load_program(assemble("""
        ldi r16, 0x40
        ldi r17, 7
        st  r16, r17
        ld  r0, r16
        halt
    """))
    while not cpu.halted:
        cpu.step()
    assert cpu.registers[0] == 7


def test_lds_and_sts_use_immediate_addresses():
    cpu = CPU()
    cpu.load_program(assemble("""
        ldi r0, 123
        sts 0x10, r0
        lds r1, 0x10
        halt
    """))
    while not cpu.halted:
        cpu.step()
    assert cpu.memory[0x10] == 123
    assert cpu.registers[1] == 123


def test_address_is_clamped_to_memory_size():
    cpu = CPU()
    # 0x1FF wraps to 0xFF inside the 256-byte bank
    cpu.load_program(assemble("""
        ldi r16, 0xFF
        ldi r17, 42
        st  r16, r17
        halt
    """))
    while not cpu.halted:
        cpu.step()
    assert cpu.memory[0xFF] == 42
    assert len(cpu.memory) == MEMORY_SIZE


def test_assembler_emits_correct_opcodes_for_ld_st():
    program = assemble("""
        ld  r0, r1
        st  r2, r3
        lds r4, 0x20
        sts 0x21, r5
        halt
    """)
    opcodes = [instr.opcode for instr in program]
    assert opcodes == [Opcode.LD, Opcode.ST, Opcode.LDS, Opcode.STS, Opcode.HALT]


def test_cycle_result_records_memory_changes():
    cpu = CPU()
    cpu.load_program(assemble("""
        ldi r16, 0x60
        ldi r17, 5
        st  r16, r17
        halt
    """))
    cpu.step()  # ldi r16
    cpu.step()  # ldi r17
    result = cpu.step()  # st r16, r17 — should record memory change
    assert result.memory_changes == {0x60: 5}


def test_bridge_records_register_and_memory_history_per_cycle():
    bridge = CPUGPUBridge()
    bridge.load_program(assemble("""
        ldi r0, 1
        ldi r1, 2
        ldi r16, 0x60
        st  r16, r0
        halt
    """))
    while not bridge.cpu.halted:
        bridge.step()
    # one snapshot per stepped cycle
    assert len(bridge.register_history) >= 4
    assert len(bridge.memory_history) >= 4
    assert len(bridge.sreg_history) == len(bridge.register_history)
    # the last memory snapshot must include the store at 0x60
    assert bridge.memory_history[-1][0x60] == 1
    # the last register snapshot must contain R0 = 1, R1 = 2
    assert bridge.register_history[-1][0] == 1
    assert bridge.register_history[-1][1] == 2
    assert len(bridge.register_history[-1]) == NUM_REGISTERS


def test_reset_clears_all_histories():
    bridge = CPUGPUBridge()
    bridge.load_program(assemble("ldi r0, 1\nhalt\n"))
    bridge.step()
    bridge.step()
    assert bridge.register_history
    bridge.reset()
    assert bridge.register_history == []
    assert bridge.memory_history == []
    assert bridge.sreg_history == []
    assert len(bridge.trace) == 0


def test_memory_copy_example_program_runs_to_completion():
    """End-to-end: the canonical Tiny8-style memory copy demo."""
    bridge = CPUGPUBridge()
    program_path = "examples/memory_copy.asm"
    with open(program_path, encoding="utf-8") as handle:
        source = handle.read()
    bridge.load_program(assemble(source))
    bridge.run_until_halt(max_cycles=2000)
    assert bridge.cpu.halted
    # the destination range should now mirror the source range
    for offset in range(6):
        assert bridge.cpu.memory[0x70 + offset] == bridge.cpu.memory[0x60 + offset]
    assert bridge.gpu.kernels_completed >= 1
