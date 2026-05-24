"""Sanity tests for the i18n module."""

from gpu_simulator.i18n import STRINGS, kernel_label, t, trigger_label


def test_t_returns_chinese_string_for_known_key():
    assert "提交" in t("status.running", count=3) or "執行" in t("status.running", count=3)
    assert t("tab.live") != "tab.live"


def test_t_falls_back_to_key_for_unknown():
    assert t("not.a.real.key") == "not.a.real.key"


def test_t_supports_format_kwargs():
    rendered = t("status.recording", seconds=12)
    assert "12" in rendered


def test_kernel_label_translates_known_kernels():
    assert kernel_label("vector_add") == "向量加法"
    assert kernel_label("texture_load") == "紋理載入"
    assert kernel_label("idle_compression") == "閒置壓縮"


def test_trigger_label_translates_known_triggers():
    assert trigger_label("mouse_click") == "滑鼠點擊"
    assert trigger_label("idle") == "使用者閒置"


def test_essential_keys_present():
    """確保核心 UI 字串都還在(防止 PR 刪到。"""
    required_keys = (
        "app.title",
        "tab.live",
        "tab.input",
        "btn.run",
        "btn.reset",
        "status.ready",
        "welcome.title",
        "trophy.title",
        "quiz.title",
        "kernel.vector_add",
        "trigger.mouse_click",
        "pet.busy",
    )
    for key in required_keys:
        assert key in STRINGS, f"missing required i18n key: {key}"
