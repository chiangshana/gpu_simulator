"""Unit tests for gpu_simulator.memory — VRAM, SharedMemory, RegisterFile."""

from gpu_simulator.memory import VRAM, RegisterFile, SharedMemory


def test_vram_allocate_and_free_bytes():
    vram = VRAM(capacity_bytes=1024)
    assert vram.free_bytes == 1024

    assert vram.allocate("k1", 256, lifetime_ticks=5) is True
    assert vram.used_bytes == 256
    assert vram.free_bytes == 768
    assert vram.utilization == 256 / 1024


def test_vram_rejects_oversize_allocation():
    vram = VRAM(capacity_bytes=100)
    assert vram.allocate("k1", 200, lifetime_ticks=5) is False
    assert vram.used_bytes == 0


def test_vram_blocks_expire_with_tick():
    vram = VRAM(capacity_bytes=1024)
    vram.allocate("k1", 128, lifetime_ticks=2)
    vram.tick()
    assert vram.used_bytes == 128
    vram.tick()
    assert vram.used_bytes == 0


def test_vram_free_all_for_named_kernel():
    vram = VRAM(capacity_bytes=1024)
    vram.allocate("alpha", 100, lifetime_ticks=10)
    vram.allocate("beta", 100, lifetime_ticks=10)
    vram.free_all_for("alpha")
    remaining_owners = {block.owner_kernel for block in vram.blocks}
    assert remaining_owners == {"beta"}


def test_shared_memory_reserve_and_release():
    shared = SharedMemory(capacity_bytes=1024)
    assert shared.reserve(256) is True
    assert shared.used_bytes == 256
    assert shared.reserve(1024) is False  # would overflow
    shared.release(128)
    assert shared.used_bytes == 128


def test_register_file_utilization_and_release():
    registers = RegisterFile(registers_per_thread=32, thread_count=32)
    assert registers.total_registers == 32 * 32
    registers.reserve(256)
    assert registers.utilization == 256 / (32 * 32)
    registers.release_all()
    assert registers.utilization == 0.0
