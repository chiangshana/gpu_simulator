"""Tests for the achievement system (no Qt required)."""

from gpu_simulator.achievements import (
    ACHIEVEMENTS,
    ACHIEVEMENTS_BY_CODE,
    AchievementStore,
    AchievementTracker,
)


def test_default_achievements_are_well_defined():
    assert len(ACHIEVEMENTS) >= 8
    codes = {a.code for a in ACHIEVEMENTS}
    assert len(codes) == len(ACHIEVEMENTS)  # 沒重複
    for achievement in ACHIEVEMENTS:
        assert achievement.name  # i18n 翻譯有東西
        assert achievement.description


def test_store_unlock_returns_true_only_first_time():
    store = AchievementStore(":memory:")
    try:
        assert store.is_unlocked("first_run") is False
        assert store.unlock("first_run") is True
        assert store.unlock("first_run") is False
        assert store.is_unlocked("first_run") is True
    finally:
        store.close()


def test_store_all_unlocked_returns_dict_of_datetime():
    store = AchievementStore(":memory:")
    try:
        store.unlock("first_run")
        store.unlock("first_klaunch")
        unlocked = store.all_unlocked()
        assert set(unlocked.keys()) == {"first_run", "first_klaunch"}
        for value in unlocked.values():
            assert value.tzinfo is not None
    finally:
        store.close()


def test_store_reset_clears_table():
    store = AchievementStore(":memory:")
    try:
        store.unlock("first_run")
        store.reset()
        assert store.all_unlocked() == {}
    finally:
        store.close()


def test_tracker_invokes_callback_on_first_unlock_only():
    received: list[str] = []
    store = AchievementStore(":memory:")
    try:
        tracker = AchievementTracker(store, on_unlock=lambda a: received.append(a.code))
        tracker.report_first_run()
        tracker.report_first_run()  # 不應再觸發 callback
        assert received == ["first_run"]
    finally:
        store.close()


def test_tracker_unlocks_full_load_when_utilization_is_one():
    received: list[str] = []
    store = AchievementStore(":memory:")
    try:
        tracker = AchievementTracker(store, on_unlock=lambda a: received.append(a.code))
        tracker.report_snapshot({"overall_utilization": 1.0, "kernels_submitted": 1})
        assert "full_load" in received
    finally:
        store.close()


def test_tracker_unlocks_kernel_collector_at_five_kernels():
    received: list[str] = []
    store = AchievementStore(":memory:")
    try:
        tracker = AchievementTracker(store, on_unlock=lambda a: received.append(a.code))
        tracker.report_snapshot({"overall_utilization": 0.2, "kernels_submitted": 5})
        assert "kernel_collector" in received
    finally:
        store.close()


def test_tracker_unlocks_long_session_at_100_cycles():
    received: list[str] = []
    store = AchievementStore(":memory:")
    try:
        tracker = AchievementTracker(store, on_unlock=lambda a: received.append(a.code))
        tracker.report_snapshot(
            {"overall_utilization": 0.1, "kernels_submitted": 0},
            cycles_observed=100,
        )
        assert "long_session" in received
    finally:
        store.close()


def test_memory_master_requires_16_addresses():
    received: list[str] = []
    store = AchievementStore(":memory:")
    try:
        tracker = AchievementTracker(store, on_unlock=lambda a: received.append(a.code))
        tracker.report_memory_writes(15)
        assert "memory_master" not in received
        tracker.report_memory_writes(16)
        assert "memory_master" in received
    finally:
        store.close()


def test_known_codes_match_dict():
    assert set(ACHIEVEMENTS_BY_CODE.keys()) == {a.code for a in ACHIEVEMENTS}
