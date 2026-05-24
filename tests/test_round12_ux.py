"""第十二輪測試:UX + 樂趣模組 (toast / palette / status_bar / mood / eggs / heatmap)。

所有測試都跑純資料層,不需要 QApplication。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from gpu_simulator.command_palette import (
    Command,
    fuzzy_score,
    rank_commands,
)
from gpu_simulator.cpu_heatmap import (
    MEMORY_WINDOW_END,
    MEMORY_WINDOW_START,
    SREG_BITS,
    _normalize_sreg_string,
    memory_to_matrix,
    record_run,
    registers_to_matrix,
    sreg_to_matrix,
)
from gpu_simulator.easter_eggs import (
    DEFAULT_MAGIC_WORDS,
    KONAMI_SEQUENCE,
    EasterEggDetector,
    dispatch,
    make_default_handlers,
)
from gpu_simulator.gpu_pet import (
    is_valid_pet_name,
    stage_for_achievement_count,
    suggest_random_name,
)
from gpu_simulator.mood_calendar import DayMood, MoodLog, build_grid
from gpu_simulator.status_bar import StatusSnapshot
from gpu_simulator.toast import (
    ToastLevel,
    ToastManager,
    ToastSpec,
    stack_y_offset,
)


# ---------------------------------------------------------------------------
# Y1 toast
# ---------------------------------------------------------------------------
def test_toast_levels_have_distinct_icons_and_colors():
    icons = {level.icon for level in ToastLevel}
    colors = {level.background_color for level in ToastLevel}
    assert len(icons) == 4
    assert len(colors) == 4


def test_toast_spec_display_text_includes_title_and_icon():
    spec = ToastSpec(title="Hello", body="world", level=ToastLevel.SUCCESS)
    text = spec.display_text()
    assert "Hello" in text
    assert "world" in text
    assert ToastLevel.SUCCESS.icon in text


def test_toast_stack_offset_grows_with_index():
    o0 = stack_y_offset(0, 60)
    o1 = stack_y_offset(1, 60)
    o2 = stack_y_offset(2, 60)
    assert o0 < o1 < o2
    assert o1 - o0 == o2 - o1  # 等距


def test_toast_manager_test_mode_collects_specs():
    mgr = ToastManager(parent=None, with_qt=False)
    mgr.show(ToastSpec(title="a"))
    mgr.show(ToastSpec(title="b", level=ToastLevel.WARNING))
    assert len(mgr) == 2


# ---------------------------------------------------------------------------
# Y2 command palette
# ---------------------------------------------------------------------------
def test_fuzzy_score_substring_beats_subsequence():
    score_sub = fuzzy_score("cinema", "🎬 電影模式 cinema demo")
    score_subseq = fuzzy_score("cinema", "c some i other n exe m fa a")
    assert score_sub > score_subseq > 0


def test_fuzzy_score_zero_for_no_match():
    assert fuzzy_score("xyz", "abc def") == 0.0


def test_fuzzy_score_empty_query_zero():
    assert fuzzy_score("", "anything") == 0.0


def test_rank_commands_returns_only_matches_sorted():
    cmds = [
        Command(id="a", title="Run kernel", description="跑 kernel", run=lambda: None,
                keywords=("run", "kernel")),
        Command(id="b", title="Save", description="存檔", run=lambda: None,
                keywords=("save", "disk")),
        Command(id="c", title="Run quiz", description="開考考你", run=lambda: None,
                keywords=("quiz", "test", "run")),
    ]
    ranked = rank_commands("run", cmds)
    assert {c.id for c in ranked} == {"a", "c"}


def test_rank_commands_empty_query_keeps_order():
    cmds = [
        Command(id=str(i), title=f"X{i}", description="", run=lambda: None)
        for i in range(3)
    ]
    assert [c.id for c in rank_commands("", cmds)] == ["0", "1", "2"]


# ---------------------------------------------------------------------------
# Y3 status bar
# ---------------------------------------------------------------------------
def test_status_snapshot_format_text_contains_all_fields():
    snap = StatusSnapshot(version="0.10.0", mode="即時", kernels=7,
                          utilization_percent=42.0, fps=30.0)
    text = snap.format_text()
    assert "v0.10.0" in text
    assert "即時" in text
    assert "7" in text
    assert "42" in text
    assert "30" in text


def test_status_snapshot_extra_appended():
    snap = StatusSnapshot(version="x", extra=("⚡ live", "🔥 hot"))
    text = snap.format_text()
    assert "⚡ live" in text
    assert "🔥 hot" in text


# ---------------------------------------------------------------------------
# Y4 mood calendar
# ---------------------------------------------------------------------------
def test_day_mood_emoji_changes_with_load():
    idle = DayMood(date.today(), 0, 0, 0)
    busy = DayMood(date.today(), 80, 95, 50)
    assert idle.emoji != busy.emoji


def test_day_mood_intensity_in_range():
    for util in (0, 10, 30, 60, 99):
        m = DayMood(date.today(), util, util, 5)
        assert 1 <= m.intensity <= 4


def test_day_mood_intensity_zero_when_idle():
    m = DayMood(date.today(), 0, 0, 0)
    assert m.intensity == 0


def test_build_grid_shape_and_today_in_last_column():
    today = date(2026, 5, 22)  # 五月廿二 = 星期五
    moods = [DayMood(today, 50, 70, 3)]
    grid = build_grid(today, moods, weeks=4)
    assert len(grid) == 4
    assert all(len(col) == 7 for col in grid)
    # 今天在 grid 最後一欄、index = weekday()
    assert grid[-1][today.weekday()] is not None
    assert grid[-1][today.weekday()].day == today


def test_build_grid_future_days_are_none():
    today = date(2026, 5, 20)  # 週三
    grid = build_grid(today, [], weeks=2)
    # 週四 / 週五(週三之後)應該都是 None
    last_col = grid[-1]
    for d_idx in range(today.weekday() + 1, 7):
        assert last_col[d_idx] is None


def test_mood_log_round_trip(tmp_path: Path):
    log = MoodLog(tmp_path / "mood.db")
    d = DayMood(date(2026, 5, 20), 55.0, 72.0, 12, note="今天衝刺")
    log.record(d)
    again = log.get(date(2026, 5, 20))
    assert again is not None
    assert again.kernel_count == 12
    assert again.note == "今天衝刺"


def test_mood_log_upsert_overwrites(tmp_path: Path):
    log = MoodLog(tmp_path / "mood.db")
    today = date.today()
    log.record(DayMood(today, 10, 20, 1))
    log.record(DayMood(today, 90, 95, 50, note="busy"))
    final = log.get(today)
    assert final is not None
    assert final.average_utilization == 90
    assert final.kernel_count == 50
    assert final.note == "busy"


# ---------------------------------------------------------------------------
# Y5 easter eggs
# ---------------------------------------------------------------------------
def test_konami_sequence_triggers():
    det = EasterEggDetector()
    triggered = None
    for label in KONAMI_SEQUENCE:
        triggered = det.feed_key(label)
    assert triggered == "konami"


def test_konami_resets_on_wrong_key():
    det = EasterEggDetector()
    det.feed_key("UP")
    det.feed_key("UP")
    det.feed_key("LEFT")  # 錯
    # 從頭開始,應該還沒觸發
    assert det.feed_key("UP") is None


def test_magic_word_matrix_triggers():
    det = EasterEggDetector()
    triggered = None
    for ch in "matrix":
        triggered = det.feed_char(ch)
    assert triggered == DEFAULT_MAGIC_WORDS["matrix"]


def test_magic_word_after_garbage_still_works():
    det = EasterEggDetector()
    for ch in "blah blah dragon":
        triggered = det.feed_char(ch)
    assert triggered == DEFAULT_MAGIC_WORDS["dragon"]


def test_dispatch_calls_handler_and_returns_true():
    called = {"x": 0}
    handlers = make_default_handlers(on_konami=lambda: called.__setitem__("x", 1))
    assert dispatch("konami", handlers) is True
    assert called["x"] == 1


def test_dispatch_unknown_trigger_returns_false():
    handlers = make_default_handlers()
    assert dispatch("not_a_real_trigger", handlers) is False
    assert dispatch(None, handlers) is False


# ---------------------------------------------------------------------------
# Y6 pet name + idle
# ---------------------------------------------------------------------------
def test_pet_name_validity():
    assert is_valid_pet_name("小皮")
    assert is_valid_pet_name("Dragon-A")
    assert not is_valid_pet_name("")
    assert not is_valid_pet_name("   ")
    assert not is_valid_pet_name("這個名字實在是太長了會超過十二個字限制就會被擋下來")
    assert not is_valid_pet_name(None)  # type: ignore[arg-type]


def test_suggest_random_name_is_valid():
    for seed in range(5):
        name = suggest_random_name(seed=seed)
        assert is_valid_pet_name(name)


def test_stage_grows_with_achievements():
    s0 = stage_for_achievement_count(0)
    s5 = stage_for_achievement_count(5)
    s99 = stage_for_achievement_count(99)
    assert s0.code == "egg"
    assert s5.code in ("bird", "eagle")
    assert s99.code == "dragon"


# ---------------------------------------------------------------------------
# CPU 狀態時間熱圖
# ---------------------------------------------------------------------------
def test_sreg_bits_have_8_names():
    assert len(SREG_BITS) == 8


def test_memory_window_size_is_32():
    assert MEMORY_WINDOW_END - MEMORY_WINDOW_START == 32


def test_normalize_sreg_string_handles_binary():
    bits = _normalize_sreg_string("01010101")
    assert bits == (0, 1, 0, 1, 0, 1, 0, 1)


def test_normalize_sreg_string_handles_dash_and_letters():
    bits = _normalize_sreg_string("-Z---N-C")
    assert bits[1] == 1  # Z 點亮
    assert bits[5] == 1  # N 點亮
    assert bits[7] == 1  # C 點亮
    assert bits[0] == 0  # dash 不點亮


def test_normalize_sreg_string_pads_short_input():
    bits = _normalize_sreg_string("11")
    assert len(bits) == 8
    assert bits[0] == 1


def test_record_run_produces_state_history():
    asm = """
        ldi r16, 5
        ldi r17, 10
    """
    history = record_run(asm, max_steps=20)
    assert history.total_steps >= 2
    assert len(history.registers) == history.total_steps
    assert len(history.memory_window) == history.total_steps
    last_regs = history.registers[-1]
    assert last_regs[16] == 5
    assert last_regs[17] == 10


def test_registers_to_matrix_shape():
    asm = """
        ldi r16, 7
    """
    history = record_run(asm, max_steps=10)
    mat = registers_to_matrix(history)
    assert len(mat) == 32
    assert all(len(row) == history.total_steps for row in mat)


def test_memory_to_matrix_shape():
    # 簡單寫一些暫存器,然後看 memory matrix 形狀正確
    asm = """
        ldi r16, 50
        ldi r17, 80
        add r16, r17
    """
    history = record_run(asm, max_steps=20)
    mat = memory_to_matrix(history)
    assert len(mat) == 32  # 0x60..0x7f
    assert all(len(row) == history.total_steps for row in mat)


def test_sreg_to_matrix_shape():
    asm = """
        ldi r16, 1
    """
    history = record_run(asm, max_steps=10)
    mat = sreg_to_matrix(history)
    assert len(mat) == 8
    assert all(len(row) == history.total_steps for row in mat)
    # 每格都該是 0 或 1
    for row in mat:
        for v in row:
            assert v in (0, 1)
