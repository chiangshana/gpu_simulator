"""Tests for the real-hardware sampler (psutil per-core CPU + GPU bridge).

These tests don't need a Qt application — they exercise the pure data layer
:class:`RealHardwareSampler`,以及純函式 :func:`utilization_to_color` /
:func:`bin_per_core` 兩支。
"""

from __future__ import annotations

import time

import pytest

from gpu_simulator.real_hardware import (
    CPUSample,
    RealHardwareSampler,
    bin_per_core,
    utilization_to_color,
)


def test_utilization_to_color_brackets():
    # 四個區間,each should give a different colour
    colors = {utilization_to_color(p) for p in (5, 45, 75, 95)}
    assert len(colors) == 4


def test_utilization_to_color_clamps():
    # 超出 0..100 不該爆掉
    utilization_to_color(-50)
    utilization_to_color(9999)


def test_bin_per_core_distributes_correctly():
    bins = bin_per_core((5, 25, 50, 90, 100, 0))
    assert bins["idle (<10%)"] == 2
    assert bins["light (10-40%)"] == 1
    assert bins["busy (40-80%)"] == 1
    assert bins["hot (>=80%)"] == 2
    assert sum(bins.values()) == 6


def test_bin_per_core_empty_input():
    bins = bin_per_core(())
    assert sum(bins.values()) == 0
    assert set(bins.keys()) == {"idle (<10%)", "light (10-40%)", "busy (40-80%)", "hot (>=80%)"}


def test_cpu_sample_summary_includes_core_counts():
    s = CPUSample(
        per_core_percent=(10.0, 20.0, 30.0, 40.0),
        overall_percent=25.0,
        logical_count=4,
        physical_count=2,
        frequency_mhz=3500.0,
        process_count=200,
    )
    summary = s.summary()
    assert "4" in summary
    assert "2" in summary
    assert "3500" in summary
    assert "200" in summary


def test_cpu_sample_hottest_core():
    s = CPUSample(
        per_core_percent=(5.0, 99.0, 30.0, 12.0),
        overall_percent=30.0,
        logical_count=4,
        physical_count=4,
        frequency_mhz=None,
        process_count=10,
    )
    assert s.hottest_core_index == 1


def test_cpu_sample_hottest_core_empty():
    s = CPUSample(
        per_core_percent=(),
        overall_percent=0.0,
        logical_count=0,
        physical_count=0,
        frequency_mhz=None,
        process_count=0,
    )
    assert s.hottest_core_index == -1


def test_sampler_returns_cpu_data():
    pytest.importorskip("psutil")
    sampler = RealHardwareSampler()
    # 第一筆讀數可能全是 0(psutil 需要兩次讀才有真實值);先等一下
    time.sleep(0.15)
    sample = sampler.sample()
    sampler.close()
    assert sample.cpu.logical_count > 0
    assert len(sample.cpu.per_core_percent) == sample.cpu.logical_count
    for pct in sample.cpu.per_core_percent:
        assert 0.0 <= pct <= 100.0


def test_sampler_gpu_available_is_bool():
    sampler = RealHardwareSampler()
    assert isinstance(sampler.gpu_available(), bool)
    assert isinstance(sampler.gpu_backend_name(), str)
    sampler.close()


def test_sampler_close_is_idempotent():
    sampler = RealHardwareSampler()
    sampler.close()
    sampler.close()  # 不該爆
