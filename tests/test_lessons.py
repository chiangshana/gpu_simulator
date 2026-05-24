"""Tests for the 5-lesson teaching content."""

from gpu_simulator.bridge import CPUGPUBridge
from gpu_simulator.cpu import assemble
from gpu_simulator.full_bridge import FullCPUGPUBridge
from gpu_simulator.lessons import LESSONS, lesson_by_code


def test_we_have_at_least_five_lessons():
    assert len(LESSONS) >= 5


def test_each_lesson_has_a_unique_code():
    codes = [lesson.code for lesson in LESSONS]
    assert len(codes) == len(set(codes))


def test_each_lesson_has_chinese_title_and_summary():
    for lesson in LESSONS:
        assert any("一" <= ch <= "鿿" for ch in lesson.title), (
            f"lesson {lesson.code} title missing Chinese"
        )
        assert any("一" <= ch <= "鿿" for ch in lesson.summary)
        assert len(lesson.bullets) >= 2


def test_each_lesson_asm_assembles_and_halts():
    """Every lesson's bundled program must run on the right bridge to halt."""
    for lesson in LESSONS:
        if lesson.use_full_tiny8:
            bridge = FullCPUGPUBridge()
            bridge.load_source(lesson.asm_source)
            steps_run = bridge.run_until_halt(max_steps=2000)
        else:
            bridge = CPUGPUBridge()
            bridge.load_program(assemble(lesson.asm_source))
            steps_run = bridge.run_until_halt(max_cycles=2000)
        assert steps_run > 0, f"lesson {lesson.code} did not run"


def test_lesson_by_code_returns_object_or_none():
    assert lesson_by_code("lesson1_sm") is not None
    assert lesson_by_code("does_not_exist") is None


def test_lesson_5_actually_uses_full_tiny8_only_instruction():
    """第 5 課刻意用了 MUL,確認沒有跑錯到子集 CPU。"""
    fifth = lesson_by_code("lesson5_full")
    assert fifth is not None
    assert fifth.use_full_tiny8 is True
    assert "mul" in fifth.asm_source.lower()


def test_klaunch_lessons_actually_submit_kernels():
    """第 2 / 3 / 4 課應該都會送 kernel 給 GPU。"""
    for code in ("lesson2_klaunch", "lesson3_kwait", "lesson4_loop"):
        lesson = lesson_by_code(code)
        assert lesson is not None
        bridge = CPUGPUBridge()
        bridge.load_program(assemble(lesson.asm_source))
        bridge.run_until_halt(max_cycles=2000)
        assert bridge.gpu.kernels_submitted >= 1, (
            f"lesson {code} expected to submit kernels but submitted 0"
        )
