"""End-to-end tests of the GPU simulation loop."""

from gpu_simulator.core import GPU, GPUConfig, WarpState
from gpu_simulator.kernel import KernelLibrary


def _tiny_gpu() -> GPU:
    return GPU(
        GPUConfig(
            num_sms=2,
            warps_per_sm=2,
            threads_per_warp=8,
            vram_capacity_bytes=4 * 1024 * 1024,
        )
    )


def test_fresh_gpu_reports_zero_activity():
    gpu = _tiny_gpu()
    snapshot = gpu.snapshot()
    assert snapshot["clock"] == 0
    assert snapshot["kernels_submitted"] == 0
    assert snapshot["kernels_completed"] == 0
    assert snapshot["overall_utilization"] == 0.0


def test_submit_kernel_populates_queue_and_allocates_vram():
    gpu = _tiny_gpu()
    assert gpu.submit_kernel(KernelLibrary.vector_add()) is True
    snapshot = gpu.snapshot()
    assert snapshot["kernels_submitted"] == 1
    assert snapshot["vram"]["used_bytes"] > 0


def test_tick_advances_clock_and_dispatches_blocks():
    gpu = _tiny_gpu()
    gpu.submit_kernel(KernelLibrary.vector_add())
    gpu.tick()
    snapshot = gpu.snapshot()
    assert snapshot["clock"] == 1
    busy_warps = [
        warp
        for sm in snapshot["sms"]
        for warp in sm["warps"]
        if warp["state"] != WarpState.IDLE.value
    ]
    assert len(busy_warps) >= 1


def test_enough_ticks_completes_small_kernel():
    gpu = _tiny_gpu()
    gpu.submit_kernel(KernelLibrary.interpolation())
    for _ in range(200):
        gpu.tick()
    snapshot = gpu.snapshot()
    assert snapshot["kernels_completed"] >= 1


def test_oversized_kernel_is_dropped_and_logged():
    gpu = GPU(GPUConfig(vram_capacity_bytes=1024))
    # vector_add requests ~2 MiB → should not fit into 1 KiB.
    assert gpu.submit_kernel(KernelLibrary.vector_add()) is False
    snapshot = gpu.snapshot()
    assert snapshot["kernels_submitted"] == 0
    messages = [entry["message"] for entry in snapshot["event_log"]]
    assert any("dropped" in message for message in messages)


def test_reset_restores_initial_state():
    gpu = _tiny_gpu()
    gpu.submit_kernel(KernelLibrary.vector_add())
    for _ in range(5):
        gpu.tick()
    gpu.reset()
    snapshot = gpu.snapshot()
    assert snapshot["clock"] == 0
    assert snapshot["kernels_submitted"] == 0
