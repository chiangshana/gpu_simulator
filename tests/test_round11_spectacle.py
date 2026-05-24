"""Tests for round-11 spectacle features (no Qt)."""

from __future__ import annotations

import random

from gpu_simulator.cinematic import (
    CinemaActionKind,
    CinemaPlayer,
    builtin_60_second_script,
)
from gpu_simulator.code_rain import CodeRain
from gpu_simulator.particle_fx import Particle, ParticleField
from gpu_simulator.tts import is_available as tts_is_available


# ---------------------------------------------------------------------------
# W1 · particles
# ---------------------------------------------------------------------------
def test_particle_decays_to_zero_after_enough_ticks():
    particle = Particle(x=0, y=0, velocity_x=1, velocity_y=1,
                        color_r=255, color_g=0, color_b=0, life=1.0)
    for _ in range(40):
        particle.tick()
    assert not particle.alive


def test_emit_launch_creates_count_particles():
    field = ParticleField()
    field.emit_launch(origin_x=0, origin_y=0, target_x=100, target_y=100,
                      count=12, seed=0)
    assert len(field) == 12


def test_emit_firework_creates_count_particles():
    field = ParticleField()
    field.emit_firework(center_x=50, center_y=50, count=20, seed=1)
    assert len(field) == 20


def test_emit_ripple_distributes_particles_in_circle():
    field = ParticleField()
    field.emit_ripple(center_x=50, center_y=50, count=12)
    # 每個粒子的方向應該是 360 度均勻分佈
    velocities = [(p.velocity_x, p.velocity_y) for p in field.particles]
    assert len(set(velocities)) == 12  # 都不一樣


def test_particle_field_clear():
    field = ParticleField()
    field.emit_firework(center_x=0, center_y=0, count=10)
    field.clear()
    assert len(field) == 0


def test_particle_field_eventually_empties_via_tick():
    field = ParticleField()
    field.emit_firework(center_x=0, center_y=0, count=10, seed=0)
    for _ in range(40):
        field.tick()
    assert len(field) == 0


# ---------------------------------------------------------------------------
# W4 · code rain
# ---------------------------------------------------------------------------
def test_code_rain_activates_above_threshold():
    rain = CodeRain()
    rain.update_utilization(0.85)
    assert rain.active is True


def test_code_rain_deactivates_below_threshold():
    rain = CodeRain()
    rain.update_utilization(0.85)
    rain.update_utilization(0.30)
    assert rain.active is False
    assert rain.streams == []


def test_code_rain_hysteresis_between_thresholds():
    """40% < util < 70% 時不切換狀態。"""
    rain = CodeRain()
    rain.update_utilization(0.20)
    assert rain.active is False
    rain.update_utilization(0.50)  # 在兩個門檻之間
    assert rain.active is False     # 仍然關著


def test_code_rain_spawns_streams_when_active():
    rain = CodeRain(width=200, height=400)
    rain.update_utilization(0.95)
    rng = random.Random(0)
    for _ in range(10):
        rain.tick(rng)
    assert len(rain.streams) > 0


def test_code_rain_resets_clean():
    rain = CodeRain()
    rain.update_utilization(0.95)
    rng = random.Random(0)
    for _ in range(5):
        rain.tick(rng)
    rain.reset()
    assert rain.active is False
    assert rain.streams == []


# ---------------------------------------------------------------------------
# W3 · cinematic
# ---------------------------------------------------------------------------
def test_builtin_script_has_reasonable_duration():
    script = builtin_60_second_script()
    # ~60 秒,允許 30s 容差
    assert 30000 <= script.total_duration_ms <= 90000


def test_cinema_player_finishes_after_all_actions():
    script = builtin_60_second_script()
    seen: list[CinemaActionKind] = []
    player = CinemaPlayer(script, on_action=lambda a: seen.append(a.kind))
    while player.advance() is not None:
        pass
    assert player.is_finished
    assert CinemaActionKind.DONE in seen
    assert CinemaActionKind.SHOW_CAPTION in seen
    assert CinemaActionKind.SWITCH_TAB in seen


def test_cinema_player_handles_callback_errors_gracefully():
    script = builtin_60_second_script()

    def bad_callback(action):
        raise RuntimeError("nope")

    player = CinemaPlayer(script, on_action=bad_callback)
    # 即使 callback 一直炸 player 還是要能 advance 到底
    actions = 0
    while player.advance() is not None and actions < 50:
        actions += 1
    assert player.is_finished


def test_cinema_player_progress_grows_monotonically():
    script = builtin_60_second_script()
    player = CinemaPlayer(script, on_action=lambda a: None)
    previous = 0.0
    for _ in range(len(script.actions)):
        player.advance()
        assert player.progress >= previous
        previous = player.progress


# ---------------------------------------------------------------------------
# W5 · TTS(只測 graceful availability check,不真的播音)
# ---------------------------------------------------------------------------
def test_tts_is_available_returns_tuple_with_reason():
    available, reason = tts_is_available()
    assert isinstance(available, bool)
    if not available:
        assert reason
