"""Tests for the quiz module (no Qt)."""

from gpu_simulator.quiz import (
    STATIC_QUESTIONS,
    QuizQuestion,
    build_dynamic_questions,
    build_quiz,
)


def test_static_pool_is_well_formed():
    assert len(STATIC_QUESTIONS) >= 8
    for question in STATIC_QUESTIONS:
        assert isinstance(question, QuizQuestion)
        assert len(question.options) >= 2
        assert 0 <= question.correct_index < len(question.options)
        assert question.explanation


def test_build_quiz_returns_5_questions_at_most():
    quiz = build_quiz(seed=1)
    assert 1 <= len(quiz) <= 5


def test_build_quiz_combines_static_and_dynamic():
    dynamic = build_dynamic_questions(
        final_register_value_r0=42,
        kernels_submitted=3,
        kernels_completed=3,
        cycles_executed=12,
    )
    assert dynamic, "dynamic builder should always produce at least one question"
    quiz = build_quiz(static_count=2, dynamic_questions=dynamic, seed=42)
    assert len(quiz) == 5


def test_build_dynamic_questions_includes_correct_answer_for_r0():
    dynamic = build_dynamic_questions(
        final_register_value_r0=99,
        kernels_submitted=0,
        kernels_completed=0,
        cycles_executed=0,
    )
    r0_question = next(q for q in dynamic if "R0" in q.prompt)
    assert r0_question.options[r0_question.correct_index] == "99"


def test_build_dynamic_questions_handles_zero_state():
    dynamic = build_dynamic_questions(
        final_register_value_r0=0,
        kernels_submitted=0,
        kernels_completed=0,
        cycles_executed=0,
    )
    # 至少 R0 跟 kernel 數量兩題
    assert len(dynamic) >= 2
    for question in dynamic:
        assert question.options[question.correct_index] in question.options


def test_build_quiz_is_deterministic_with_seed():
    a = build_quiz(seed=7)
    b = build_quiz(seed=7)
    assert [(q.prompt, q.options) for q in a] == [(q.prompt, q.options) for q in b]
