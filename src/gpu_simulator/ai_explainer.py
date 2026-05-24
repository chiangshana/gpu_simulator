"""(Optional)用 Claude API 解釋 ASM 程式 + trace 結果。

如果 ``anthropic`` 套件沒安裝、或環境變數 ``ANTHROPIC_API_KEY`` 沒設,
:func:`is_available` 會回 False,UI 端可以據此顯示「AI 功能未啟用」訊息;
**整支模組永遠 import 得起來**,不會因為沒有 API key 就崩潰。

核心 API:

- :func:`is_available` — 檢查能不能用
- :class:`ExplainRequest` — 一次解釋的輸入(asm + trace 摘要)
- :class:`Explainer` — 真正的呼叫端
- :func:`offline_fallback` — 沒 AI 時的純規則式中文摘要

不依賴 Qt,可以單獨測試。
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

from gpu_simulator.commentary import classify_row, explain_instruction


# ---------------------------------------------------------------------------
# environment / availability
# ---------------------------------------------------------------------------
def is_available() -> tuple[bool, str]:
    """Return (available, reason)."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "anthropic 套件未安裝。執行:pip install anthropic"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "請設定環境變數 ANTHROPIC_API_KEY"
    return True, ""


def default_model() -> str:
    """The Claude model the explainer uses by default."""
    return os.environ.get("GPU_SIMULATOR_AI_MODEL", "claude-haiku-4-5-20251001")


# ---------------------------------------------------------------------------
# request / response shapes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExplainRequest:
    asm_source: str
    trace_summary: str  # 一段預先濃縮過的 trace text
    final_register_summary: str
    kernels_submitted: int
    kernels_completed: int

    def to_prompt(self) -> str:
        return (
            "你是一位耐心的助教,正在替商管系初學者解釋一段 Tiny8 風格 ASM "
            "程式 + 它在我們的虛擬 GPU 上跑出來的 trace。\n\n"
            "請用**繁體中文**寫一段 4–6 段的解說,內容包含:\n"
            "1. 這支程式整體在做什麼(用日常比喻)\n"
            "2. 哪幾行最關鍵\n"
            "3. trace 的高潮:KLAUNCH / KWAIT 在哪裡發生\n"
            "4. 最終結果(暫存器、提交了幾顆 kernel)\n"
            "5. 用一句話的初學者建議結尾\n\n"
            "=== ASM 程式 ===\n"
            f"{self.asm_source.strip()}\n\n"
            "=== Trace 摘要 ===\n"
            f"{self.trace_summary.strip()}\n\n"
            "=== 結束時暫存器 ===\n"
            f"{self.final_register_summary.strip()}\n\n"
            f"GPU kernel 提交={self.kernels_submitted},完成={self.kernels_completed}"
        )


@dataclass(frozen=True)
class ExplainResponse:
    text: str
    used_ai: bool
    model: str | None = None


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------
class Explainer:
    """Wrap the Claude SDK and provide a graceful offline fallback."""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or default_model()

    def explain(self, request: ExplainRequest) -> ExplainResponse:
        available, _reason = is_available()
        if not available:
            return ExplainResponse(text=offline_fallback(request), used_ai=False)
        try:
            import anthropic
        except ImportError:
            return ExplainResponse(text=offline_fallback(request), used_ai=False)

        try:
            client = anthropic.Anthropic()
            message = client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": request.to_prompt()}],
            )
            blocks = getattr(message, "content", []) or []
            chunks: list[str] = []
            for block in blocks:
                text_attr = getattr(block, "text", None)
                if text_attr:
                    chunks.append(str(text_attr))
            text = "\n".join(chunks).strip() or offline_fallback(request)
            return ExplainResponse(text=text, used_ai=True, model=self._model)
        except Exception as exc:
            return ExplainResponse(
                text=(
                    "(AI 呼叫失敗,改用離線模式)\n\n錯誤:"
                    f"{exc}\n\n{offline_fallback(request)}"
                ),
                used_ai=False,
            )


# ---------------------------------------------------------------------------
# 離線 fallback — 純 Python,沒網路也能解釋一段 asm
# ---------------------------------------------------------------------------
def offline_fallback(request: ExplainRequest) -> str:
    lines: list[str] = []
    lines.append("📝 **離線模式中文導讀**(沒呼叫 AI,純規則式產生)\n")
    lines.append("### 1. 整體在做什麼")
    asm_lines = [line for line in request.asm_source.splitlines() if line.strip()]
    lines.append(f"這支程式總共 {len(asm_lines)} 行(含註解),逐行重點如下:\n")

    lines.append("### 2. 逐行關鍵指令")
    for line_number, raw_line in enumerate(asm_lines, start=1):
        stripped = raw_line.split(";", 1)[0].strip()
        if not stripped or stripped.endswith(":"):
            continue
        explanation = explain_instruction(stripped)
        lines.append(f"- **L{line_number}** `{stripped[:50]}` → {explanation}")
    lines.append("")
    lines.append("### 3. Trace 高潮")
    lines.append(request.trace_summary[:600])
    lines.append("")
    lines.append("### 4. 最終結果")
    lines.append(request.final_register_summary[:300])
    lines.append(
        f"GPU 共提交 {request.kernels_submitted} 顆 kernel,完成 {request.kernels_completed} 顆。"
    )
    lines.append("")
    lines.append("### 5. 給初學者的話")
    lines.append(
        "如果 KLAUNCH 跟 KWAIT 中間 cycle 數很多,代表 GPU 跑很久 — "
        "想想能不能讓 CPU 也順便做別的事。"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 公用工具:從 trace 產生簡短摘要,避免 prompt 太長
# ---------------------------------------------------------------------------
def summarize_trace(trace_rows: Iterable, max_lines: int = 30) -> str:
    """挑 trace 裡最具代表性的幾行,組成一段純文字摘要。"""
    interesting: list[str] = []
    for row in trace_rows:
        classification = classify_row(
            instruction_text=getattr(row, "instruction_text", ""),
            port_writes=getattr(row, "port_writes", ()),
            cpu_halted=getattr(row, "cpu_halted", False),
            cpu_stalled=getattr(row, "cpu_stalled", False),
        )
        kind = classification.kind.value
        # 平凡的 NORMAL row 太多,只挑一部分
        if kind == "normal" and len(interesting) > max_lines // 2:
            continue
        cycle = getattr(row, "cycle", getattr(row, "step", "?"))
        text = getattr(row, "instruction_text", "")
        interesting.append(f"C{cycle:>04}  [{kind:<13}] {text}")
        if len(interesting) >= max_lines:
            break
    return "\n".join(interesting)


def summarize_registers(registers: list[int]) -> str:
    non_zero = [
        f"R{index:02}={value}"
        for index, value in enumerate(registers)
        if value != 0
    ]
    if not non_zero:
        return "所有暫存器都是 0(可能還沒跑或 reset 了)。"
    return ", ".join(non_zero[:16])
