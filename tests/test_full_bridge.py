"""Tests for the full Tiny8 (vendored) ↔ virtual GPU bridge."""

from pathlib import Path

import pytest

from gpu_simulator.core import GPU, GPUConfig
from gpu_simulator.full_bridge import FullCPUGPUBridge, FullTiny8CPU, sreg_text
from gpu_simulator.tiny8_full import CPU as VendoredCPU
from gpu_simulator.tiny8_full import assemble as tiny8_assemble

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


# ---------------------------------------------------------------------------
# vendoring sanity
# ---------------------------------------------------------------------------
def test_vendored_tiny8_module_imports_and_has_full_isa():
    program = tiny8_assemble("""
        ldi r16, 5
        ldi r17, 3
        mul r16, r17    ; MUL is full-Tiny8 only — 不在我們的子集
    """)
    cpu = VendoredCPU()
    cpu.load_program(program)
    while cpu.step():
        pass
    # MUL stores low byte of result in Rd; 5 * 3 = 15
    assert cpu.regs[16] == 15


def test_full_tiny8_cpu_subclass_does_not_break_normal_writes():
    cpu = FullTiny8CPU()
    cpu.write_ram(0x70, 99)
    assert cpu.read_ram(0x70) == 99


# ---------------------------------------------------------------------------
# bridge: kernel dispatch
# ---------------------------------------------------------------------------
def _tiny_bridge() -> FullCPUGPUBridge:
    return FullCPUGPUBridge(
        gpu=GPU(GPUConfig(num_sms=2, warps_per_sm=2, threads_per_warp=8))
    )


def test_out_to_port_0x40_dispatches_kernel():
    bridge = _tiny_bridge()
    bridge.load_source("""
        ldi r0, 0          ; vector_add id
        out 0x40, r0
    """)
    bridge.run_until_halt(max_steps=20)
    assert bridge.gpu.kernels_submitted == 1


def test_kwait_stalls_until_gpu_drains():
    bridge = _tiny_bridge()
    bridge.load_source("""
        ldi r0, 0
        out 0x40, r0
        out 0x40, r0
        out 0xFF, r0     ; KWAIT
        ldi r1, 42       ; 只有等到 GPU 跑完才會執行
    """)
    bridge.run_until_halt(max_steps=400)
    assert bridge.gpu.kernels_completed == 2
    assert bridge.cpu.regs[1] == 42


def test_in_port_returns_outstanding_kernel_count():
    bridge = _tiny_bridge()
    bridge.load_source("""
        ldi r0, 0
        out 0x40, r0
        out 0x40, r0
        in  r2, 0x40     ; r2 should be ≥ 1 (尚未完成的 kernel 數)
    """)
    bridge.run_until_halt(max_steps=20)
    assert bridge.cpu.regs[2] >= 1


# ---------------------------------------------------------------------------
# bridge: history / trace recording
# ---------------------------------------------------------------------------
def test_bridge_records_per_step_history():
    bridge = _tiny_bridge()
    bridge.load_source("""
        ldi r0, 0
        out 0x40, r0
    """)
    bridge.run_until_halt(max_steps=20)
    assert len(bridge.register_history) >= 2
    assert len(bridge.memory_history) == len(bridge.register_history)
    assert len(bridge.sreg_history) == len(bridge.register_history)
    # 最後一筆暫存器快照長度 = 32(R0..R31)
    assert len(bridge.register_history[-1]) == 32


def test_trace_rows_include_port_writes_for_klaunch():
    bridge = _tiny_bridge()
    bridge.load_source("""
        ldi r0, 0
        out 0x40, r0
    """)
    bridge.run_until_halt(max_steps=20)
    # 第一筆 OUT 要把 (0x40, 0) 記在 port_writes 裡
    klaunch_rows = [row for row in bridge.trace if any(p == 0x40 for p, _ in row.port_writes)]
    assert klaunch_rows, "OUT 0x40 should appear in trace.port_writes"


def test_sreg_text_helper_returns_4_chars():
    cpu = FullTiny8CPU()
    text = sreg_text(cpu)
    assert len(text) == 4
    assert all(ch in "ZNCV-" for ch in text)


# ---------------------------------------------------------------------------
# end-to-end: the bundled examples
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "filename,expected_min_kernels",
    [
        ("full_fibonacci.asm", 1),
        ("full_bubble_sort.asm", 2),
    ],
)
def test_full_examples_run_and_submit_kernels(filename, expected_min_kernels):
    bridge = FullCPUGPUBridge()
    source = (EXAMPLES_DIR / filename).read_text(encoding="utf-8")
    bridge.load_source(source)
    bridge.run_until_halt(max_steps=3000)
    assert bridge.gpu.kernels_submitted >= expected_min_kernels


def test_full_fibonacci_computes_55():
    bridge = FullCPUGPUBridge()
    source = (EXAMPLES_DIR / "full_fibonacci.asm").read_text(encoding="utf-8")
    bridge.load_source(source)
    bridge.run_until_halt(max_steps=2000)
    # F(10) = 55 lives in R17 by the end of the loop
    assert bridge.cpu.regs[17] == 55


def test_full_bubble_sort_actually_sorts_memory():
    bridge = FullCPUGPUBridge()
    source = (EXAMPLES_DIR / "full_bubble_sort.asm").read_text(encoding="utf-8")
    bridge.load_source(source)
    bridge.run_until_halt(max_steps=3000)
    sorted_bytes = [bridge.cpu.read_ram(0x60 + offset) for offset in range(8)]
    assert sorted_bytes == sorted(sorted_bytes)


# ---------------------------------------------------------------------------
# reset() clears state
# ---------------------------------------------------------------------------
def test_reset_clears_history_and_resets_cpu():
    bridge = _tiny_bridge()
    bridge.load_source("ldi r0, 1\nout 0x40, r0\n")
    bridge.run_until_halt(max_steps=20)
    assert bridge.register_history
    bridge.reset()
    assert bridge.register_history == []
    assert bridge.memory_history == []
    assert len(bridge.trace) == 0
    assert all(value == 0 for value in bridge.cpu.regs)
