"""End-to-end checks for all bundled example .asm programs."""

from pathlib import Path

import pytest

from gpu_simulator.bridge import CPUGPUBridge
from gpu_simulator.cpu import assemble

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

ALL_EXAMPLES = (
    "hello_gpu.asm",
    "burst_and_count.asm",
    "loop_kernel.asm",
    "memory_copy.asm",
    "sort_three.asm",
    "find_max.asm",
    "counter.asm",
    "mixed_burst.asm",
)


@pytest.mark.parametrize("filename", ALL_EXAMPLES)
def test_example_assembles_and_halts(filename: str) -> None:
    source = (EXAMPLES_DIR / filename).read_text(encoding="utf-8")
    bridge = CPUGPUBridge()
    bridge.load_program(assemble(source))
    bridge.run_until_halt(max_cycles=4000)
    assert bridge.cpu.halted, f"{filename} should reach HALT within 4000 cycles"


def test_counter_writes_descending_pattern_to_memory():
    """Counter example fills memory[0x70..0x79] from 9 down to 1."""
    source = (EXAMPLES_DIR / "counter.asm").read_text(encoding="utf-8")
    bridge = CPUGPUBridge()
    bridge.load_program(assemble(source))
    bridge.run_until_halt(max_cycles=2000)
    written_values = [bridge.cpu.memory[0x70 + i] for i in range(9)]
    assert written_values == [9, 8, 7, 6, 5, 4, 3, 2, 1]


def test_mixed_burst_submits_seven_kernels():
    source = (EXAMPLES_DIR / "mixed_burst.asm").read_text(encoding="utf-8")
    bridge = CPUGPUBridge()
    bridge.load_program(assemble(source))
    bridge.run_until_halt(max_cycles=3000)
    assert bridge.gpu.kernels_submitted == 7
    assert bridge.gpu.kernels_completed == 7


def test_memory_copy_actually_copies_six_bytes():
    source = (EXAMPLES_DIR / "memory_copy.asm").read_text(encoding="utf-8")
    bridge = CPUGPUBridge()
    bridge.load_program(assemble(source))
    bridge.run_until_halt(max_cycles=2000)
    for offset in range(6):
        assert bridge.cpu.memory[0x60 + offset] == bridge.cpu.memory[0x70 + offset]
