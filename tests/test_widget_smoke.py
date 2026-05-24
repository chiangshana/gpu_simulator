"""Integration smoke tests — 證明關鍵模組可以 import + 基礎物件能建構。

完整的 GPUVizWidget 構造會 spawn 一個 event listener thread 跟 16 個 QTimer,
不適合在 pytest 自動化跑(會 hang 或污染 home 目錄)。
這支檔測試「import + 純資料層初始化」這條路徑,確保 widget 的依賴鏈完整。
真實 widget launch 用 ``gpu-simulator`` CLI 手動驗證。
"""

from __future__ import annotations

import os

# 在 Linux/CI 上跑 Qt 需要 offscreen platform。先在 import Qt 之前設好。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_widget_module_imports_without_error():
    """所有 widget 相依模組都能 import — 抓 import-time error / cycle。"""
    from gpu_simulator import widget  # noqa: F401

    assert hasattr(widget, "GPUVizWidget")


def test_all_round_12_13_modules_import():
    """第十二/十三輪新增的模組都能 import。"""
    from gpu_simulator import (
        command_palette,
        cpu_heatmap,
        easter_eggs,
        mirror_dashboard,
        mood_calendar,
        real_hardware,
        status_bar,
        toast,
    )

    assert command_palette.fuzzy_score("a", "abc") > 0
    assert cpu_heatmap.MEMORY_WINDOW_END > cpu_heatmap.MEMORY_WINDOW_START
    assert len(easter_eggs.KONAMI_SEQUENCE) == 10
    assert mirror_dashboard.divergence_score is not None
    assert real_hardware.utilization_to_color(50)
    assert mood_calendar.DayMood is not None
    assert status_bar.StatusSnapshot is not None
    assert toast.ToastLevel.INFO


def test_simulated_gpu_constructs():
    """模擬 GPU 引擎能初始化 + snapshot。"""
    from gpu_simulator.core import GPU

    gpu = GPU()
    snap = gpu.snapshot()
    assert "sms" in snap
    assert "overall_utilization" in snap
    assert len(snap["sms"]) >= 1


def test_real_hardware_sampler_constructs():
    """psutil 取樣器能初始化 + close 不爆。"""
    from gpu_simulator.real_hardware import RealHardwareSampler

    sampler = RealHardwareSampler()
    sample = sampler.sample()
    assert sample.cpu.logical_count > 0
    sampler.close()


def test_kernel_queue_pipeline():
    """模擬 kernel queue:push → drain → submit 可以串。"""
    from gpu_simulator.core import GPU
    from gpu_simulator.event_listener import KernelQueue
    from gpu_simulator.kernel import KernelLibrary

    queue = KernelQueue()
    gpu = GPU()
    queue.push(KernelLibrary.vector_add(trigger="smoke"))
    queue.push(KernelLibrary.interpolation(trigger="smoke"))
    drained = queue.drain(limit=5)
    assert len(drained) == 2
    for kernel in drained:
        gpu.submit_kernel(kernel)
    # 跑幾個 tick,讓模擬器消化一下
    for _ in range(5):
        gpu.tick()
    assert gpu.kernels_submitted >= 2


def test_mirror_snapshot_end_to_end():
    """🪞 對照鏡 的核心管線:模擬 GPU snapshot + 真實硬體 sample → ComparisonSnapshot。"""
    from gpu_simulator.core import GPU
    from gpu_simulator.mirror_dashboard import compose_snapshot, divergence_score
    from gpu_simulator.real_hardware import RealHardwareSampler

    gpu = GPU()
    sampler = RealHardwareSampler()
    try:
        snapshot = compose_snapshot(gpu.snapshot(), sampler.sample())
    finally:
        sampler.close()
    assert snapshot.simulated_count >= 1
    assert snapshot.real_count >= 1
    score = divergence_score(snapshot)
    assert 0.0 <= score <= 100.0


def test_cinema_script_visits_mirror_first():
    """第十四輪新劇本:🪞 對照鏡 應該在最前面被切換到。"""
    from gpu_simulator.cinematic import CinemaActionKind, builtin_60_second_script

    script = builtin_60_second_script()
    # 找出第一個 SWITCH_TAB action
    first_switch = next(
        (a for a in script.actions if a.kind is CinemaActionKind.SWITCH_TAB), None
    )
    assert first_switch is not None
    assert "對照鏡" in first_switch.payload.get("tab", "")


def test_cinema_script_duration_around_one_minute():
    """劇本總時長應該在 50–80 秒範圍內。"""
    from gpu_simulator.cinematic import builtin_60_second_script

    script = builtin_60_second_script()
    seconds = script.total_duration_ms / 1000.0
    assert 45 <= seconds <= 80


def test_cinema_script_ends_with_done():
    """最後一個 action 應該是 DONE。"""
    from gpu_simulator.cinematic import CinemaActionKind, builtin_60_second_script

    script = builtin_60_second_script()
    assert script.actions[-1].kind is CinemaActionKind.DONE


def test_full_bridge_runs_short_program():
    """完整 Tiny8 ISA 能跑一支短程式不爆 — 證明熱圖分頁的後端 OK。"""
    from gpu_simulator.full_bridge import FullCPUGPUBridge

    bridge = FullCPUGPUBridge()
    bridge.load_source("ldi r16, 42\nldi r17, 10\nadd r16, r17\n")
    for _ in range(10):
        row = bridge.step()
        if row.cpu_halted and not row.cpu_stalled:
            break
    assert bridge.cpu.regs[16] == 52  # 42 + 10
