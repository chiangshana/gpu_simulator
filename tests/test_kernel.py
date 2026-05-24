"""Unit tests for gpu_simulator.kernel — Kernel dataclass + library factories."""

from gpu_simulator.kernel import Kernel, KernelLibrary, WorkloadProfile


def test_kernel_total_threads_is_grid_times_block():
    kernel = Kernel(
        name="test",
        grid_size=4,
        block_size=64,
        duration_ticks=10,
        vram_bytes=1024,
        profile=WorkloadProfile.COMPUTE,
    )
    assert kernel.total_threads == 4 * 64


def test_library_kernels_have_nonzero_cost():
    for kernel in (
        KernelLibrary.vector_add(),
        KernelLibrary.interpolation(),
        KernelLibrary.hash_kernel("a"),
        KernelLibrary.texture_load("explorer.exe"),
        KernelLibrary.idle_compression(),
    ):
        assert kernel.grid_size >= 1
        assert kernel.block_size >= 1
        assert kernel.duration_ticks > 0
        assert kernel.vram_bytes > 0


def test_library_profiles_are_as_expected():
    assert KernelLibrary.vector_add().profile is WorkloadProfile.COMPUTE
    assert KernelLibrary.texture_load("x").profile is WorkloadProfile.MEMORY
    assert KernelLibrary.interpolation().profile is WorkloadProfile.LIGHT
    assert KernelLibrary.hash_kernel("k").profile is WorkloadProfile.MIXED
    assert KernelLibrary.idle_compression().profile is WorkloadProfile.LIGHT


def test_trigger_is_propagated():
    kernel = KernelLibrary.vector_add(trigger="my-click")
    assert kernel.trigger == "my-click"
