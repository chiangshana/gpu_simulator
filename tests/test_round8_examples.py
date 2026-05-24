"""End-to-end tests for the 5 round-8 GPU-integrated Tiny8 examples."""

from pathlib import Path

import pytest

from gpu_simulator.full_bridge import FullCPUGPUBridge

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def _run(filename: str, max_steps: int = 1500) -> FullCPUGPUBridge:
    """Examples end with 'jmp end' so they never naturally halt;
    1500 steps is well past the meaningful work but keeps tests fast.
    """
    bridge = FullCPUGPUBridge()
    source = (EXAMPLES_DIR / filename).read_text(encoding="utf-8")
    bridge.load_source(source)
    bridge.run_until_halt(max_steps=max_steps)
    return bridge


# ---------------------------------------------------------------------------
# 個別範例的數值正確性
# ---------------------------------------------------------------------------
def test_gcd_24_18_equals_6():
    bridge = _run("full_gcd_gpu.asm")
    assert bridge.cpu.regs[0] == 6
    assert bridge.gpu.kernels_submitted >= 2  # 至少幾個 checkpoint kernel


def test_count_bits_of_0xb7_equals_6():
    bridge = _run("full_count_bits_gpu.asm")
    assert bridge.cpu.regs[0] == 6
    # 6 個 set bit 對應 6 顆 GPU kernel
    assert bridge.gpu.kernels_submitted == 6
    assert bridge.gpu.kernels_completed == 6


def test_factorial_5_equals_120_low_byte():
    bridge = _run("full_factorial_gpu.asm")
    assert bridge.cpu.regs[0] == 120
    # 4 顆 vector_add(每次 multiply)+ 1 顆 page_nav = 5 顆
    assert bridge.gpu.kernels_submitted == 5


def test_histogram_buckets_each_count_4():
    bridge = _run("full_histogram_gpu.asm")
    buckets = [bridge.cpu.read_ram(0x70 + i) for i in range(4)]
    assert buckets == [4, 4, 4, 4]
    # 16 個 sample → 16 顆 hash kernel
    assert bridge.gpu.kernels_submitted == 16


def test_matrix_diagonal_writes_ones_on_diagonal():
    bridge = _run("full_matrix_diagonal_gpu.asm")
    diagonal = [bridge.cpu.read_ram(0x60 + i * 8 + i) for i in range(8)]
    assert diagonal == [1] * 8
    # 8 列 → 8 顆 texture_load kernel
    assert bridge.gpu.kernels_submitted == 8


# ---------------------------------------------------------------------------
# 通用:每支範例都能 halt 並至少送一顆 kernel
# ---------------------------------------------------------------------------
ROUND8_EXAMPLES = (
    "full_gcd_gpu.asm",
    "full_count_bits_gpu.asm",
    "full_factorial_gpu.asm",
    "full_histogram_gpu.asm",
    "full_matrix_diagonal_gpu.asm",
)


@pytest.mark.parametrize("filename", ROUND8_EXAMPLES)
def test_each_example_dispatches_at_least_one_kernel(filename):
    bridge = _run(filename)
    assert bridge.gpu.kernels_submitted >= 1, (
        f"{filename}: expected at least 1 kernel submission"
    )


@pytest.mark.parametrize("filename", ROUND8_EXAMPLES)
def test_each_example_makes_per_step_history_grow(filename):
    bridge = _run(filename)
    # bridge 必須在每個 step 把 register / memory / sreg 各推一筆進 history,
    # 而且三條 history 長度要對齊
    assert len(bridge.register_history) > 5
    assert len(bridge.memory_history) == len(bridge.register_history)
    assert len(bridge.sreg_history) == len(bridge.register_history)
