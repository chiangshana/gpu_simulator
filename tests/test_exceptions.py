"""Tests for the custom exception hierarchy."""

import pytest

from gpu_simulator.core import GPU, GPUConfig
from gpu_simulator.exceptions import (
    ConfigError,
    GPUError,
    GPUVizError,
    KernelSubmissionError,
    PersistenceError,
    RealGPUUnavailableError,
    VRAMOverflowError,
)
from gpu_simulator.kernel import KernelLibrary


def test_hierarchy_rooted_at_gpuviz_error():
    for subclass in (
        GPUError,
        VRAMOverflowError,
        KernelSubmissionError,
        ConfigError,
        PersistenceError,
        RealGPUUnavailableError,
    ):
        assert issubclass(subclass, GPUVizError)


def test_vram_overflow_error_reports_requested_and_free_bytes():
    error = VRAMOverflowError(requested_bytes=2048, free_bytes=512)
    assert error.requested_bytes == 2048
    assert error.free_bytes == 512
    assert "2048" in str(error)
    assert "512" in str(error)


def test_submit_kernel_strict_raises_on_vram_overflow():
    tiny = GPU(GPUConfig(vram_capacity_bytes=1024))
    with pytest.raises(VRAMOverflowError) as exc_info:
        tiny.submit_kernel_strict(KernelLibrary.vector_add())
    assert exc_info.value.free_bytes == 1024


def test_submit_kernel_strict_rejects_zero_sized_kernel():
    from dataclasses import replace

    gpu = GPU(GPUConfig())
    malformed = replace(KernelLibrary.vector_add(), grid_size=0)
    with pytest.raises(KernelSubmissionError):
        gpu.submit_kernel_strict(malformed)
