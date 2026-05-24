"""Tests for the commentary module (no Qt dependency)."""

from gpu_simulator.commentary import (
    Commentator,
    EventKind,
    classify_row,
    explain_instruction,
)


# ---------------------------------------------------------------------------
# explain_instruction
# ---------------------------------------------------------------------------
def test_ldi_is_translated():
    text = explain_instruction("LDI R16, 5")
    assert "5" in text
    assert "R16" in text


def test_klaunch_via_out_0x40_is_translated():
    text = explain_instruction("OUT 0x40, R16")
    assert "GPU" in text or "kernel" in text.lower()


def test_kwait_via_out_0xff_is_translated():
    text = explain_instruction("OUT 0xFF, R0")
    assert "KWAIT" in text or "等" in text


def test_klaunch_alias_translates_to_klaunch():
    text = explain_instruction("KLAUNCH R0")
    assert "kernel" in text.lower() or "GPU" in text


def test_unknown_opcode_falls_back_gracefully():
    text = explain_instruction("FOOBAR R0, R1")
    assert text.startswith("執行")


def test_empty_or_comment_passthrough():
    assert explain_instruction("") == "—"
    assert explain_instruction("; just a comment").startswith(";")


# ---------------------------------------------------------------------------
# classify_row
# ---------------------------------------------------------------------------
def test_classify_klaunch_marks_event_with_chinese_badge():
    classification = classify_row(
        instruction_text="OUT 0x40, R16",
        port_writes=[(0x40, 0)],
    )
    assert classification.kind is EventKind.KLAUNCH
    assert "提交" in classification.badge_text or "KLAUNCH" in classification.badge_text


def test_classify_kwait_marks_event_with_chinese_badge():
    classification = classify_row(
        instruction_text="OUT 0xFF, R0",
        port_writes=[(0xFF, 0)],
    )
    assert classification.kind is EventKind.KWAIT


def test_classify_stalled_row_is_kwait_stall():
    classification = classify_row(
        instruction_text="; KWAIT (stalled)",
        cpu_stalled=True,
    )
    assert classification.kind is EventKind.KWAIT_STALL


def test_classify_halt_row():
    classification = classify_row(instruction_text="HALT", cpu_halted=True)
    assert classification.kind is EventKind.HALT


def test_classify_ldi_is_normal_not_memory():
    classification = classify_row(instruction_text="LDI R16, 5")
    assert classification.kind is EventKind.NORMAL


def test_classify_ld_st_are_memory():
    assert classify_row(instruction_text="LD R0, R1").kind is EventKind.MEMORY
    assert classify_row(instruction_text="ST R0, R1").kind is EventKind.MEMORY


def test_classify_branches():
    assert classify_row(instruction_text="BRNE loop").kind is EventKind.BRANCH
    assert classify_row(instruction_text="BREQ done").kind is EventKind.BRANCH


# ---------------------------------------------------------------------------
# Commentator narration
# ---------------------------------------------------------------------------
class _FakeRow:
    def __init__(
        self,
        instruction_text: str = "NOP",
        port_writes=(),
        cpu_stalled: bool = False,
        cpu_halted: bool = False,
    ) -> None:
        self.instruction_text = instruction_text
        self.port_writes = port_writes
        self.cpu_stalled = cpu_stalled
        self.cpu_halted = cpu_halted


def test_commentator_recognizes_klaunch():
    commentator = Commentator()
    line = commentator.narrate(
        _FakeRow(instruction_text="OUT 0x40, R16", port_writes=[(0x40, 0)])
    )
    assert "🚀" in line or "KLAUNCH" in line


def test_commentator_starts_kwait_then_announces_resumption():
    commentator = Commentator()
    enter = commentator.narrate(
        _FakeRow(instruction_text="OUT 0xFF, R0", port_writes=[(0xFF, 0)])
    )
    assert "KWAIT" in enter or "等" in enter

    stalling = commentator.narrate(
        _FakeRow(instruction_text="; KWAIT (stalled)", cpu_stalled=True)
    )
    assert "等" in stalling

    resuming = commentator.narrate(_FakeRow(instruction_text="LDI R0, 1"))
    assert "繼續" in resuming or "GPU" in resuming


def test_commentator_marks_halt_with_flag():
    commentator = Commentator()
    line = commentator.narrate(_FakeRow(instruction_text="HALT", cpu_halted=True))
    assert "🏁" in line or "停止" in line


def test_commentator_reset_clears_kwait_state():
    commentator = Commentator()
    commentator.narrate(_FakeRow(instruction_text="; KWAIT", cpu_stalled=True))
    commentator.narrate(_FakeRow(instruction_text="; KWAIT", cpu_stalled=True))
    commentator.reset()
    line = commentator.narrate(_FakeRow(instruction_text="LDI R0, 5"))
    # 第一條應該不要有「繼續」這個詞,因為 reset 後就不該認為剛從 stall 出來
    assert "繼續" not in line
