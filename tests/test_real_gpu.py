"""Tests for gpu_simulator.real_gpu — graceful fallback when no backend is present."""

from gpu_simulator.real_gpu import RealGPUSample, RealGPUSampler


def test_sampler_with_explicit_none_backend_is_unavailable():
    sampler = RealGPUSampler(preferred_backend="none")
    assert sampler.available() is False
    assert sampler.sample() is None
    assert sampler.backend_name == "none"
    sampler.close()


def test_sampler_auto_degrades_without_crashing():
    """On a machine without pynvml / GPUtil the sampler must stay silent.

    We don't assert ``available is False`` because a CI machine with
    a real GPU should still pass; we just verify the call is safe.
    """
    sampler = RealGPUSampler(preferred_backend="auto")
    _ = sampler.available()
    _ = sampler.sample()
    sampler.close()


def test_realgpu_sample_snapshot_is_plain_dict():
    sample = RealGPUSample(
        backend="pynvml",
        name="RTX",
        utilization_percent=42.0,
        memory_used_bytes=1024,
        memory_total_bytes=4096,
        temperature_celsius=65.0,
        power_watts=120.5,
    )
    snapshot = sample.snapshot()
    assert snapshot["backend"] == "pynvml"
    assert snapshot["utilization_percent"] == 42.0
    assert snapshot["memory_total_bytes"] == 4096
