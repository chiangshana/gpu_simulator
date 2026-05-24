"""Tests for the 🪞 對照鏡 mirror dashboard (data layer only — no Qt)."""

from __future__ import annotations

import time

import pytest

from gpu_simulator.core import GPU
from gpu_simulator.mirror_dashboard import (
    ComparisonSnapshot,
    SimulatedSMSummary,
    _format_real_gpu_line,
    compose_snapshot,
    divergence_score,
)
from gpu_simulator.real_hardware import CPUSample, RealHardwareSample, RealHardwareSampler


def test_simulated_sm_summary_label():
    sm = SimulatedSMSummary(sm_id=3, utilization_percent=42.0, active_warps=2)
    assert sm.label == "SM3"


def test_compose_snapshot_reads_sim_and_real():
    pytest.importorskip("psutil")
    gpu = GPU()
    sampler = RealHardwareSampler()
    time.sleep(0.15)
    snap = compose_snapshot(gpu.snapshot(), sampler.sample())
    sampler.close()
    assert snap.simulated_count == 8  # default 8 SMs
    assert snap.real_count > 0
    assert len(snap.simulated_sms) == 8
    for sm in snap.simulated_sms:
        assert 0.0 <= sm.utilization_percent <= 100.0
    assert isinstance(snap.simulated_clock, int)


def test_alignment_independent_of_counts():
    fake_sim = (
        SimulatedSMSummary(0, 10.0, 0),
        SimulatedSMSummary(1, 20.0, 0),
    )
    cpu = CPUSample(
        per_core_percent=(5.0,) * 16,
        overall_percent=5.0,
        logical_count=16,
        physical_count=8,
        frequency_mhz=4000.0,
        process_count=100,
    )
    snap = ComparisonSnapshot(
        simulated_sms=fake_sim,
        simulated_overall_percent=15.0,
        simulated_clock=42,
        real_cpu=cpu,
        real_gpu_summary="(test)",
    )
    assert snap.alignment() == (2, 16)


def test_divergence_score_zero_when_equal():
    cpu = CPUSample((50.0,), 50.0, 1, 1, None, 0)
    snap = ComparisonSnapshot(
        simulated_sms=(SimulatedSMSummary(0, 50.0, 0),),
        simulated_overall_percent=50.0,
        simulated_clock=0,
        real_cpu=cpu,
        real_gpu_summary="",
    )
    assert divergence_score(snap) == 0.0


def test_divergence_score_max_when_opposite():
    cpu = CPUSample((), 0.0, 0, 0, None, 0)
    snap = ComparisonSnapshot(
        simulated_sms=(SimulatedSMSummary(0, 100.0, 0),),
        simulated_overall_percent=100.0,
        simulated_clock=0,
        real_cpu=cpu,
        real_gpu_summary="",
    )
    # 沒有 sim_sms 時應該是 0;有 sim_sms 時應該是差距
    assert divergence_score(snap) == 100.0


def test_divergence_score_empty_sim_is_zero():
    cpu = CPUSample((), 0.0, 0, 0, None, 0)
    snap = ComparisonSnapshot(
        simulated_sms=(),
        simulated_overall_percent=0.0,
        simulated_clock=0,
        real_cpu=cpu,
        real_gpu_summary="",
    )
    assert divergence_score(snap) == 0.0


def test_format_real_gpu_line_no_gpu():
    cpu = CPUSample((), 0.0, 0, 0, None, 0)
    sample = RealHardwareSample(cpu=cpu, gpu=None)
    text = _format_real_gpu_line(sample)
    assert "未偵測到" in text


def test_compose_snapshot_handles_missing_sm_warps_gracefully():
    fake_sim_snapshot = {
        "sms": [{"sm_id": 0, "warps": []}],
        "overall_utilization": 0.0,
        "clock": 5,
    }
    cpu = CPUSample((10.0,), 10.0, 1, 1, None, 0)
    real_sample = RealHardwareSample(cpu=cpu, gpu=None)
    snap = compose_snapshot(fake_sim_snapshot, real_sample)
    assert snap.simulated_count == 1
    assert snap.simulated_sms[0].active_warps == 0


def test_compose_snapshot_counts_active_warps():
    fake_sim_snapshot = {
        "sms": [
            {
                "sm_id": 0,
                "warps": [
                    {"state": "running"},
                    {"state": "idle"},
                    {"state": "fetch"},
                    {"state": "idle"},
                ],
            },
        ],
        "overall_utilization": 0.5,
        "clock": 10,
    }
    cpu = CPUSample((10.0,), 10.0, 1, 1, None, 0)
    real_sample = RealHardwareSample(cpu=cpu, gpu=None)
    snap = compose_snapshot(fake_sim_snapshot, real_sample)
    assert snap.simulated_sms[0].active_warps == 2  # 2 non-idle warps
    assert snap.simulated_sms[0].utilization_percent == 50.0
    assert snap.simulated_overall_percent == 50.0
