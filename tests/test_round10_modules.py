"""Tests for the 8 round-10 deeper features."""

from __future__ import annotations

import pytest

from gpu_simulator.asm_games import (
    SNAKE_BASE_ADDRESS,
    SNAKE_SIZE,
    Direction,
    SnakeGameRunner,
)
from gpu_simulator.bridge import CPUGPUBridge
from gpu_simulator.cache import (
    AccessKind,
    CacheModel,
    builtin_scenarios,
    simulate_access_sequence,
)
from gpu_simulator.cpu import assemble
from gpu_simulator.kernel_dsl import DSLCompileError, compile_dsl
from gpu_simulator.multi_gpu import MultiGPUSystem
from gpu_simulator.plugins import (
    LoadedPlugin,
    PluginRegistry,
    load_plugins,
)
from gpu_simulator.profiler import (
    DEFAULT_KERNEL_COST,
    profile_session,
    roofline_points,
)
from gpu_simulator.themes import ALL_THEMES, all_codes, get_theme


# ---------------------------------------------------------------------------
# X6 themes
# ---------------------------------------------------------------------------
def test_themes_module_provides_at_least_4():
    assert len(ALL_THEMES) >= 4
    assert "classic" in all_codes()
    assert "cyberpunk" in all_codes()
    assert "matrix" in all_codes()
    assert "retro_dos" in all_codes()


def test_each_theme_has_stylesheet_and_palette():
    for theme in ALL_THEMES:
        assert theme.code
        assert theme.name
        assert theme.stylesheet.strip()
        assert theme.palette
        assert "bg" in theme.palette and "fg" in theme.palette


def test_get_theme_falls_back_to_classic_for_unknown():
    fallback = get_theme("does_not_exist")
    assert fallback.code == "classic"


# ---------------------------------------------------------------------------
# X1 plugins
# ---------------------------------------------------------------------------
def test_load_plugins_with_empty_dir(tmp_path):
    registry = load_plugins(tmp_path)
    assert isinstance(registry, PluginRegistry)
    assert registry.plugins == []
    assert registry.load_errors == []


def test_load_plugins_picks_up_kernels_examples_themes(tmp_path):
    plugin_text = '''
from gpu_simulator.kernel import Kernel, WorkloadProfile
from gpu_simulator.themes import Theme


def register_kernels():
    return {"my_kernel": lambda trigger: Kernel(
        name="my_kernel",
        grid_size=2,
        block_size=32,
        duration_ticks=8,
        vram_bytes=1024,
        profile=WorkloadProfile.COMPUTE,
        trigger=trigger,
    )}


def register_examples():
    return {"plugin_demo.asm": "; demo\\n    halt\\n"}


def register_themes():
    return [Theme(
        code="my_theme",
        name="My Theme",
        description="user theme",
        palette={"bg": "#111", "fg": "#fff"},
        stylesheet="QWidget { background: #111; }",
    )]
'''
    plugin_path = tmp_path / "user_plugin.py"
    plugin_path.write_text(plugin_text, encoding="utf-8")
    registry = load_plugins(tmp_path)
    assert registry.load_errors == []
    assert len(registry.plugins) == 1
    plugin = registry.plugins[0]
    assert isinstance(plugin, LoadedPlugin)
    assert "my_kernel" in plugin.kernel_factories
    assert "plugin_demo.asm" in plugin.examples
    assert any(theme.code == "my_theme" for theme in plugin.themes)


def test_broken_plugin_recorded_in_load_errors(tmp_path):
    bad_path = tmp_path / "broken.py"
    bad_path.write_text("def register_kernels(:\n    pass\n", encoding="utf-8")
    registry = load_plugins(tmp_path)
    assert len(registry.load_errors) == 1
    assert registry.load_errors[0].plugin_path == bad_path


# ---------------------------------------------------------------------------
# X4 cache
# ---------------------------------------------------------------------------
def test_cache_first_access_to_each_line_is_cold_miss():
    cache = CacheModel()
    result = cache.access(0x00)
    assert result.kind is AccessKind.COLD


def test_cache_repeated_access_to_same_line_is_hit():
    cache = CacheModel()
    cache.access(0x00)
    second = cache.access(0x00)
    assert second.kind is AccessKind.HIT


def test_cache_different_tag_same_line_is_miss():
    cache = CacheModel()
    cache.access(0x00)
    # 0x00 → line 0;0x100 = 256 byte 後也對應 line 0(因為 8 lines × 32 byte = 256 = wraparound)
    second = cache.access(0x100)
    assert second.kind is AccessKind.MISS


def test_simulate_access_sequence_hot_loop_has_high_hit_rate():
    cache, stats = simulate_access_sequence(
        list(range(0, 64)) * 3
    )
    # 重複讀同一段範圍 → 後兩輪幾乎都 hit
    assert stats.hit_rate > 0.5


def test_builtin_scenarios_are_well_formed():
    scenarios = builtin_scenarios()
    assert len(scenarios) >= 3
    for scenario in scenarios:
        assert scenario.code
        assert scenario.addresses


# ---------------------------------------------------------------------------
# X5 profiler
# ---------------------------------------------------------------------------
def test_profile_session_empty_returns_zero():
    profile = profile_session([])
    assert profile.total_cycles == 0
    assert profile.total_kernels == 0


def test_profile_session_counts_klaunch_kernels():
    bridge = CPUGPUBridge()
    bridge.load_program(assemble("""
        ldi r16, 0
        klaunch r16
        klaunch r16
        kwait
        halt
    """))
    bridge.run_until_halt(max_cycles=200)
    profile = profile_session(list(bridge.trace))
    assert profile.total_kernels == 2
    assert any(stat.kernel_name == "vector_add" for stat in profile.kernel_stats)


def test_roofline_points_match_kernel_stats():
    bridge = CPUGPUBridge()
    bridge.load_program(assemble("ldi r0, 0\nklaunch r0\nkwait\nhalt\n"))
    bridge.run_until_halt(max_cycles=200)
    profile = profile_session(list(bridge.trace))
    points = roofline_points(profile)
    assert len(points) == len(profile.kernel_stats)


def test_default_kernel_cost_table_covers_all_known_kernels():
    expected = {
        "vector_add", "interpolation", "hash", "texture_load",
        "idle_compression", "app_launch", "page_nav",
    }
    assert expected.issubset(DEFAULT_KERNEL_COST.keys())


# ---------------------------------------------------------------------------
# X2 kernel DSL
# ---------------------------------------------------------------------------
def test_dsl_let_const_compiles():
    program = compile_dsl("""
kernel demo:
    let a = 5
    let b = 3
""")
    assert "ldi r16, 5" in program.asm_source
    assert "ldi r17, 3" in program.asm_source


def test_dsl_addition_emits_mov_then_add():
    program = compile_dsl("""
kernel demo:
    let a = 10
    let b = 20
    let c = a + b
""")
    assert "add r" in program.asm_source.lower()


def test_dsl_launch_then_wait_runs_on_subset_cpu():
    program = compile_dsl("""
kernel demo:
    let x = 1
    launch hash
    wait
""")
    bridge = CPUGPUBridge()
    bridge.load_program(assemble(program.asm_source))
    bridge.run_until_halt(max_cycles=300)
    assert bridge.gpu.kernels_submitted == 1


def test_dsl_unknown_kernel_raises():
    with pytest.raises(DSLCompileError):
        compile_dsl("kernel demo:\n    launch nosuch\n")


def test_dsl_undefined_variable_raises():
    with pytest.raises(DSLCompileError):
        compile_dsl("kernel demo:\n    let a = b + 1\n")


# ---------------------------------------------------------------------------
# X3 Snake
# ---------------------------------------------------------------------------
def test_snake_initial_state_has_3_segments_and_alive():
    runner = SnakeGameRunner()
    snapshot = runner.board_snapshot()
    body_count = sum(cell == 1 for row in snapshot for cell in row)
    head_count = sum(cell == 2 for row in snapshot for cell in row)
    food_count = sum(cell == 3 for row in snapshot for cell in row)
    assert head_count == 1
    assert body_count == 2
    assert food_count == 1
    assert runner.alive


def test_snake_step_dispatches_kernels():
    runner = SnakeGameRunner()
    before = runner.bridge.gpu.kernels_submitted
    runner.step()
    after = runner.bridge.gpu.kernels_submitted
    assert after > before


def test_snake_set_direction_blocks_180_reverse():
    runner = SnakeGameRunner()
    runner.direction = Direction.LEFT
    runner.set_direction(Direction.RIGHT)  # 應該被擋
    assert runner.direction == Direction.LEFT
    runner.set_direction(Direction.UP)  # 90 度允許
    assert runner.direction == Direction.UP


def test_snake_constants_match_layout():
    assert SNAKE_SIZE == 8
    assert SNAKE_BASE_ADDRESS == 0xC0


# ---------------------------------------------------------------------------
# X8 multi_gpu
# ---------------------------------------------------------------------------
def test_multi_gpu_default_has_two_gpus():
    system = MultiGPUSystem()
    assert len(system.gpus) == 2


def test_multi_gpu_independent_kernel_submission():
    from gpu_simulator.kernel import KernelLibrary

    system = MultiGPUSystem()
    system.submit_kernel_to(0, KernelLibrary.vector_add())
    system.submit_kernel_to(1, KernelLibrary.hash_kernel("a"))
    assert system.gpus[0].kernels_submitted == 1
    assert system.gpus[1].kernels_submitted == 1


def test_multi_gpu_nvlink_transfer_eventually_completes():
    system = MultiGPUSystem()
    system.transfer_between(0, 1, size_bytes=512 * 1024, label="data")
    # 預設頻寬 256 KB / cycle → 至少要 2 cycle
    for _ in range(5):
        system.tick()
    assert system.cross_gpu_completions == 1


def test_multi_gpu_snapshot_includes_nvlink():
    system = MultiGPUSystem()
    system.transfer_between(0, 1, size_bytes=1024 * 1024, label="x")
    snap = system.snapshot()
    assert "nvlink" in snap
    assert "pending_transfers" in snap["nvlink"]


# ---------------------------------------------------------------------------
# X7 headless CLI
# ---------------------------------------------------------------------------
def test_headless_run_executes_asm(tmp_path, capsys):
    from gpu_simulator.cli import _run_headless

    asm_path = tmp_path / "tiny.asm"
    asm_path.write_text(
        "ldi r16, 7\nldi r17, 3\nadd r16, r17\nhalt\n", encoding="utf-8"
    )
    rc = _run_headless([str(asm_path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "headless run" in captured.out
    assert "R16 = 10" in captured.out  # 7+3=10


def test_headless_run_full_cpu_path(tmp_path, capsys):
    from gpu_simulator.cli import _run_headless

    asm_path = tmp_path / "tiny.asm"
    asm_path.write_text("ldi r0, 42\n", encoding="utf-8")
    rc = _run_headless([str(asm_path), "--full-cpu", "--max-cycles", "20"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "R00 = 42" in out


def test_headless_run_writes_report_when_asked(tmp_path, capsys):
    from gpu_simulator.cli import _run_headless

    asm_path = tmp_path / "tiny.asm"
    asm_path.write_text("ldi r0, 5\nklaunch r0\nkwait\nhalt\n", encoding="utf-8")
    report_dir = tmp_path / "out"
    rc = _run_headless([str(asm_path), "--report", str(report_dir)])
    assert rc == 0
    assert (report_dir / "report.md").exists()
