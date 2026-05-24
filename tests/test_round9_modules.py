"""Tests for the 8 round-9 feature modules.

These all run without Qt and without network — even the web mirror is
exercised via stdlib :mod:`urllib.request` against ``127.0.0.1``.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import date

import pytest

from gpu_simulator.ai_explainer import (
    Explainer,
    ExplainRequest,
    offline_fallback,
    summarize_registers,
)
from gpu_simulator.ai_explainer import (
    is_available as ai_is_available,
)
from gpu_simulator.asm_games import (
    GRID_BASE_ADDRESS,
    GRID_BYTES,
    LifeBoard,
    LifeGameRunner,
)
from gpu_simulator.bridge import CPUGPUBridge
from gpu_simulator.challenges import (
    Challenge,
    LeaderboardStore,
    daily_challenge,
    score_attempt,
)
from gpu_simulator.cpu import assemble
from gpu_simulator.divergence import (
    analyze_branch,
    analyze_memory_access,
    builtin_coalescing_presets,
    builtin_divergence_presets,
)
from gpu_simulator.lab_report import generate_report
from gpu_simulator.sounds import KERNEL_CHORDS, SoundEffect, play, play_kernel_chord
from gpu_simulator.web_mirror import MirrorServer, SnapshotPublisher


# ---------------------------------------------------------------------------
# #4 sounds upgrade
# ---------------------------------------------------------------------------
def test_every_kernel_has_a_chord_motif():
    expected_kernels = {
        "vector_add", "interpolation", "hash", "texture_load",
        "idle_compression", "app_launch", "page_nav",
    }
    assert expected_kernels.issubset(KERNEL_CHORDS.keys())
    for pattern in KERNEL_CHORDS.values():
        assert pattern  # 至少 1 個音
        for frequency, duration in pattern:
            assert frequency > 0
            assert duration > 0


def test_play_and_play_kernel_chord_dont_raise_in_silent_environment():
    for effect in SoundEffect:
        play(effect)
    play_kernel_chord("vector_add")
    play_kernel_chord("unknown_kernel_xyz")  # fallback path


# ---------------------------------------------------------------------------
# #3 lab_report
# ---------------------------------------------------------------------------
def _quick_bridge_run() -> CPUGPUBridge:
    bridge = CPUGPUBridge()
    bridge.load_program(assemble("""
        ldi r16, 0
        klaunch r16
        klaunch r16
        kwait
        halt
    """))
    bridge.run_until_halt(max_cycles=200)
    return bridge


def test_lab_report_generates_markdown(tmp_path):
    bridge = _quick_bridge_run()
    result = generate_report(
        title="unit-test",
        asm_source="ldi r16, 0\nklaunch r16\nhalt",
        trace_rows=list(bridge.trace),
        register_history=bridge.register_history,
        memory_history=bridge.memory_history,
        sreg_history=bridge.sreg_history,
        final_registers=list(bridge.cpu.registers),
        final_memory=list(bridge.cpu.memory),
        kernels_submitted=bridge.gpu.kernels_submitted,
        kernels_completed=bridge.gpu.kernels_completed,
        output_dir=tmp_path,
    )
    assert result.markdown_path.exists()
    text = result.markdown_path.read_text(encoding="utf-8")
    assert "GPU Simulator 實驗報告" in text
    assert "klaunch" in text.lower() or "KLAUNCH" in text
    # 至少嵌入一張圖(用 matplotlib;若沒安裝就略過)
    if result.image_paths:
        for image_path in result.image_paths:
            assert image_path.exists()


# ---------------------------------------------------------------------------
# #5 challenges
# ---------------------------------------------------------------------------
def test_daily_challenge_is_stable_per_day():
    today = date(2026, 5, 8)
    a = daily_challenge(today)
    b = daily_challenge(today)
    assert a.code == b.code
    assert a.title == b.title


def test_daily_challenge_changes_with_date():
    a = daily_challenge(date(2026, 5, 8))
    b = daily_challenge(date(2026, 5, 9))
    assert a.code != b.code


def test_score_attempt_kernel_count_pass(_=None):
    challenge = Challenge(
        code="test-kc",
        kind="kernel_count",
        title="t",
        description="d",
        target_kernel="vector_add",
        target_count=2,
        cycle_budget=100,
    )
    bridge = _quick_bridge_run()
    result = score_attempt(
        challenge,
        trace_rows=list(bridge.trace),
        kernels_submitted=bridge.gpu.kernels_submitted,
    )
    assert result.passed
    assert result.score >= 1


def test_leaderboard_records_and_reads_back():
    store = LeaderboardStore(":memory:")
    try:
        store.record("test-1", "alice", cycles_used=10, score=90)
        store.record("test-1", "bob", cycles_used=12, score=88)
        top = store.top_for("test-1")
        # 最高分排第一
        assert top[0].nickname == "alice"
        assert top[0].score == 90
        assert top[1].nickname == "bob"
    finally:
        store.close()


# ---------------------------------------------------------------------------
# #6 ai_explainer
# ---------------------------------------------------------------------------
def test_ai_is_available_returns_reason_when_no_dep_or_no_key():
    available, reason = ai_is_available()
    assert isinstance(available, bool)
    if not available:
        assert reason  # non-empty


def test_offline_fallback_produces_chinese_output():
    request = ExplainRequest(
        asm_source="ldi r16, 5\nhalt\n",
        trace_summary="C0001 LDI R16, 5",
        final_register_summary="R16=5",
        kernels_submitted=0,
        kernels_completed=0,
    )
    text = offline_fallback(request)
    assert "離線模式" in text
    assert "L1" in text


def test_explainer_with_no_ai_falls_back_to_offline(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    explainer = Explainer()
    response = explainer.explain(
        ExplainRequest(
            asm_source="halt\n",
            trace_summary="(empty)",
            final_register_summary="—",
            kernels_submitted=0,
            kernels_completed=0,
        )
    )
    assert response.used_ai is False
    assert response.text  # 至少有 fallback 內容


def test_summarize_helpers():
    assert summarize_registers([0] * 32).startswith("所有暫存器")
    registers = [0] * 32
    registers[5] = 99
    assert "R05=99" in summarize_registers(registers)


# ---------------------------------------------------------------------------
# #1 asm_games (Conway's Life)
# ---------------------------------------------------------------------------
def test_blinker_oscillates_with_period_2():
    runner = LifeGameRunner()
    runner.seed("blinker")
    runner.start_simulator()
    initial = runner.board.snapshot_rows()
    runner.step_one_generation()
    after_one = runner.board.snapshot_rows()
    runner.step_one_generation()
    after_two = runner.board.snapshot_rows()
    assert initial != after_one
    assert initial == after_two


def test_each_generation_dispatches_8_kernels():
    runner = LifeGameRunner()
    runner.seed("blinker")
    runner.start_simulator()
    before = runner.bridge.gpu.kernels_submitted
    runner.step_one_generation()
    after = runner.bridge.gpu.kernels_submitted
    assert after - before == 8


def test_life_board_writes_grid_into_tiny8_ram():
    runner = LifeGameRunner()
    runner.seed("blinker")
    runner.start_simulator()
    # blinker 中三個活細胞:row=3, col=2..4 → 位址 = 0x80 + 3*8 + (2..4)
    for col in (2, 3, 4):
        addr = GRID_BASE_ADDRESS + 3 * 8 + col
        assert runner.bridge.cpu.read_ram(addr) == 1


def test_life_board_step_works_in_pure_python():
    board = LifeBoard()
    board.seed_blinker()
    initial_alive = board.alive_count()
    board.step()
    assert board.alive_count() == initial_alive  # blinker 維持 3 個活細胞


def test_grid_size_constants():
    assert GRID_BYTES == 64


# ---------------------------------------------------------------------------
# #8 divergence
# ---------------------------------------------------------------------------
def test_no_divergence_when_all_threads_pick_same_path():
    analysis = analyze_branch([0] * 32)
    assert analysis.diverged is False
    assert analysis.divergence_factor == 1.0


def test_divergence_factor_matches_unique_path_count():
    decisions = [thread_id % 4 for thread_id in range(32)]
    analysis = analyze_branch(decisions)
    assert analysis.divergence_factor == 4.0
    assert analysis.diverged


def test_perfect_coalesced_uses_one_transaction():
    analysis = analyze_memory_access(list(range(32)))
    assert analysis.transactions == 1
    assert analysis.coalesced_ratio == 1.0


def test_strided_access_uses_more_transactions():
    analysis = analyze_memory_access([thread_id * 32 for thread_id in range(32)])
    # 步長 32 = line width,每個 thread 都觸到不同 line
    assert analysis.transactions == 32


def test_builtin_presets_are_well_formed():
    for preset in builtin_divergence_presets():
        assert len(preset.branch_decisions) == 32
    for preset in builtin_coalescing_presets():
        assert len(preset.addresses) == 32


# ---------------------------------------------------------------------------
# #7 web_mirror
# ---------------------------------------------------------------------------
def test_publisher_is_thread_safe_basic():
    publisher = SnapshotPublisher()
    publisher.publish({"clock": 1})
    assert publisher.get() == {"clock": 1}
    publisher.publish({"clock": 2})
    assert publisher.get() == {"clock": 2}


def test_mirror_server_serves_snapshot_endpoint():
    publisher = SnapshotPublisher()
    publisher.publish({"clock": 99, "kernels_submitted": 7})
    server = MirrorServer(publisher, port=8889)
    server.start()
    try:
        time.sleep(0.2)
        response = urllib.request.urlopen(
            "http://127.0.0.1:8889/snapshot", timeout=2
        )
        data = json.loads(response.read().decode("utf-8"))
        assert data["clock"] == 99
        assert data["kernels_submitted"] == 7
    finally:
        server.stop()
    assert not server.is_running


def test_mirror_server_serves_html_at_root():
    publisher = SnapshotPublisher()
    server = MirrorServer(publisher, port=8890)
    server.start()
    try:
        time.sleep(0.2)
        response = urllib.request.urlopen("http://127.0.0.1:8890/", timeout=2)
        body = response.read().decode("utf-8")
        assert "<title>" in body
        assert "GPU Simulator" in body
    finally:
        server.stop()


def test_mirror_server_404_on_unknown_path():
    publisher = SnapshotPublisher()
    server = MirrorServer(publisher, port=8891)
    server.start()
    try:
        time.sleep(0.2)
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen("http://127.0.0.1:8891/no-such-path", timeout=2)
        assert excinfo.value.code == 404
    finally:
        server.stop()
