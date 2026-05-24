"""Smoke tests for the GPU pet (mood logic) and sounds (silent fallback)."""

from gpu_simulator.gpu_pet import (
    ALL_STAGES,
    STAGE_DRAGON,
    STAGE_EGG,
    mood_for_utilization,
    stage_for_achievement_count,
)
from gpu_simulator.sounds import SoundEffect, play


# ---------------------------------------------------------------------------
# 進化階段
# ---------------------------------------------------------------------------
def test_stages_progress_with_achievement_count():
    """五個階段都隨成就數推進。"""
    assert stage_for_achievement_count(0).code == "egg"
    assert stage_for_achievement_count(1).code == "hatchling"
    assert stage_for_achievement_count(3).code == "bird"
    assert stage_for_achievement_count(6).code == "eagle"
    assert stage_for_achievement_count(9).code == "dragon"
    assert stage_for_achievement_count(99).code == "dragon"


def test_we_have_five_stages():
    assert len(ALL_STAGES) == 5
    codes = {stage.code for stage in ALL_STAGES}
    assert codes == {"egg", "hatchling", "bird", "eagle", "dragon"}


# ---------------------------------------------------------------------------
# 心情(綁定到階段)
# ---------------------------------------------------------------------------
def test_default_egg_stage_uses_egg_emoji():
    # 預設(沒給 stage)→ egg
    assert mood_for_utilization(0.0).emoji == "🥚"
    assert mood_for_utilization(0.99).emoji == "🥚"


def test_dragon_stage_burns_at_high_utilization():
    mood = mood_for_utilization(0.95, stage=STAGE_DRAGON)
    # 龍階段高負載會冒火
    assert mood.emoji in {"🔥", "🐲", "🐉"}


def test_egg_stage_does_not_change_emoji_across_utilization():
    egg_moods = {
        mood_for_utilization(u, stage=STAGE_EGG).emoji
        for u in (0.0, 0.3, 0.6, 0.95)
    }
    # 蛋階段不論負載都是蛋(暗示「還沒孵化」)
    assert egg_moods == {"🥚"}


def test_stages_have_five_moods_each():
    for stage in ALL_STAGES:
        assert len(stage.moods) == 5  # 5 級利用率


# ---------------------------------------------------------------------------
# 音效(靜默降級)
# ---------------------------------------------------------------------------
def test_play_does_not_raise_on_unknown_or_silent_environment():
    for effect in SoundEffect:
        play(effect)
