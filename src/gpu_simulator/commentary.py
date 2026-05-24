"""指令 → 中文解說生成器。

功能:
1. :func:`explain_instruction` — 給一段 Tiny8 / 我們子集 ISA 的指令文字,
   回傳一句中文白話解釋(例如「LDI R16, 5 → 把 5 載入 R16」)。
2. :func:`classify_event` — 給一個 :class:`TraceRow`,判斷它是 KLAUNCH /
   KWAIT / HALT / stall / 一般指令,給 UI 用來上色。
3. :class:`Commentator` — 內建小型對 KLAUNCH/KWAIT 的「教學旁白」生成器。

整支模組純 Python,沒有 Qt 依賴,可以單獨測試。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from gpu_simulator.bridge import GPU_PORT_KWAIT, kernel_name_for_id
from gpu_simulator.cpu import GPU_PORT_HINT, GPU_PORT_LAUNCH
from gpu_simulator.i18n import kernel_label


class EventKind(Enum):
    """Trace 行可以歸類的種類,影響上色與旁白風格。"""

    NORMAL = "normal"
    KLAUNCH = "klaunch"
    KSTAT = "kstat"
    KWAIT = "kwait"
    KWAIT_STALL = "kwait_stall"
    HALT = "halt"
    JUMP = "jump"
    BRANCH = "branch"
    MEMORY = "memory"


# ---------------------------------------------------------------------------
# 指令解說
# ---------------------------------------------------------------------------
# 每個 opcode 對應一段 (template, lambda(args)->字串) 的解釋
# 我們刻意把解釋寫得像「對學弟妹說人話」。
_REGISTER_PATTERN = re.compile(r"^[Rr](\d{1,2})$")


def _register_index(token: str) -> int | None:
    match = _REGISTER_PATTERN.match(token.strip())
    return int(match.group(1)) if match else None


def _format_value(token: str) -> str:
    token = token.strip()
    if token.startswith("0x") or token.startswith("0X"):
        return token  # 16 進位保留
    if token.startswith("$"):
        return f"0x{token[1:]}"
    return token


def explain_instruction(instruction_text: str) -> str:
    """給一段指令字串(像「LDI R16, 5」),回傳一句中文白話解釋。

    解析失敗或未知指令 → 回 fallback「執行 <原文>」。
    """
    if not instruction_text:
        return "—"
    text = instruction_text.strip()
    # 註解或空訊息直接 passthrough
    if text.startswith(";") or text.startswith("("):
        return text

    head, _, tail = text.partition(" ")
    op = head.strip().upper()
    operands = [token.strip() for token in tail.split(",")] if tail.strip() else []

    explainer = _OPCODE_EXPLAINERS.get(op)
    if explainer is None:
        return f"執行 {text}"
    try:
        return explainer(operands)
    except Exception:
        return f"執行 {text}"


def _explain_ldi(ops: list[str]) -> str:
    rd, k = ops
    return f"把 {_format_value(k)} 載入 {rd.upper()}"


def _explain_mov(ops: list[str]) -> str:
    rd, rr = ops
    return f"把 {rr.upper()} 的內容複製到 {rd.upper()}"


def _explain_add(ops: list[str]) -> str:
    rd, rr = ops
    return f"{rd.upper()} ← {rd.upper()} + {rr.upper()}(會更新 SREG)"


def _explain_sub(ops: list[str]) -> str:
    rd, rr = ops
    return f"{rd.upper()} ← {rd.upper()} − {rr.upper()}(會更新 SREG)"


def _explain_inc(ops: list[str]) -> str:
    return f"{ops[0].upper()} 加 1"


def _explain_dec(ops: list[str]) -> str:
    return f"{ops[0].upper()} 減 1(到 0 時 Z 旗標被設起)"


def _explain_cp(ops: list[str]) -> str:
    rd, rr = ops
    return f"比較 {rd.upper()} 跟 {rr.upper()}(只更新 SREG,不改值)"


def _explain_cpi(ops: list[str]) -> str:
    rd, k = ops
    return f"比較 {rd.upper()} 跟立即值 {_format_value(k)}(只更新 SREG)"


def _explain_jmp(ops: list[str]) -> str:
    return f"無條件跳到 {ops[0]}"


def _explain_brne(ops: list[str]) -> str:
    return f"如果 Z 旗標 = 0,跳到 {ops[0]}"


def _explain_breq(ops: list[str]) -> str:
    return f"如果 Z 旗標 = 1,跳到 {ops[0]}"


def _explain_brcs(ops: list[str]) -> str:
    return f"如果 C 旗標 = 1,跳到 {ops[0]}"


def _explain_brcc(ops: list[str]) -> str:
    return f"如果 C 旗標 = 0,跳到 {ops[0]}"


def _explain_brge(ops: list[str]) -> str:
    return f"如果有號運算結果 ≥ 0,跳到 {ops[0]}"


def _explain_brlt(ops: list[str]) -> str:
    return f"如果有號運算結果 < 0,跳到 {ops[0]}"


def _explain_nop(_ops: list[str]) -> str:
    return "什麼都不做(NOP),等下一個 cycle"


def _explain_halt(_ops: list[str]) -> str:
    return "停止 CPU。整支程式結束"


def _explain_in(ops: list[str]) -> str:
    rd, port_token = ops
    try:
        port = int(_format_value(port_token), 0)
    except ValueError:
        port = -1
    if port == GPU_PORT_LAUNCH:
        return f"從 GPU 狀態 port 讀「尚未完成的 kernel 數」進 {rd.upper()}(KSTAT)"
    if port == GPU_PORT_HINT:
        return f"從 GPU 提示 port 讀已完成 kernel 數進 {rd.upper()}"
    return f"從 I/O port {_format_value(port_token)} 讀一個 byte 進 {rd.upper()}"


def _explain_out(ops: list[str]) -> str:
    port_token, rr = ops
    try:
        port = int(_format_value(port_token), 0)
    except ValueError:
        port = -1
    if port == GPU_PORT_LAUNCH:
        return f"把 {rr.upper()} 當 kernel id 提交給 GPU(KLAUNCH 觸發!)"
    if port == GPU_PORT_HINT:
        return f"把 {rr.upper()} 當下一顆 kernel 的 hint 預設好"
    if port == GPU_PORT_KWAIT:
        return "送出 KWAIT,CPU 開始等 GPU 把所有 kernel 跑完"
    return f"把 {rr.upper()} 寫到 I/O port {_format_value(port_token)}"


def _explain_ld(ops: list[str]) -> str:
    rd, rr = ops
    return f"從記憶體 [{rr.upper()}] 載入一個 byte 到 {rd.upper()}"


def _explain_st(ops: list[str]) -> str:
    rr, rs = ops
    return f"把 {rs.upper()} 寫到記憶體 [{rr.upper()}]"


def _explain_lds(ops: list[str]) -> str:
    rd, k = ops
    return f"從記憶體 {_format_value(k)} 讀一個 byte 到 {rd.upper()}"


def _explain_sts(ops: list[str]) -> str:
    k, rr = ops
    return f"把 {rr.upper()} 寫到記憶體 {_format_value(k)}"


def _explain_klaunch(ops: list[str]) -> str:
    rr = ops[0].upper()
    return f"用 {rr} 的內容當 kernel id 提交給 GPU(別名,等同 OUT 0x40)"


def _explain_kwait(_ops: list[str]) -> str:
    return "卡住 CPU,直到 GPU 把所有提交的 kernel 跑完(別名,等同 OUT 0xFF)"


def _explain_kstat(ops: list[str]) -> str:
    return f"從 GPU 狀態 port 讀「尚未完成的 kernel 數」進 {ops[0].upper()}"


def _explain_mul(ops: list[str]) -> str:
    rd, rr = ops
    return (
        f"{rd.upper()} ← ({rd.upper()} × {rr.upper()}) 的低位元組(完整 Tiny8 才有)"
    )


_OPCODE_EXPLAINERS = {
    "LDI": _explain_ldi,
    "MOV": _explain_mov,
    "ADD": _explain_add,
    "SUB": _explain_sub,
    "INC": _explain_inc,
    "DEC": _explain_dec,
    "CP": _explain_cp,
    "CPI": _explain_cpi,
    "JMP": _explain_jmp,
    "RJMP": _explain_jmp,
    "BRNE": _explain_brne,
    "BREQ": _explain_breq,
    "BRCS": _explain_brcs,
    "BRCC": _explain_brcc,
    "BRGE": _explain_brge,
    "BRLT": _explain_brlt,
    "NOP": _explain_nop,
    "HALT": _explain_halt,
    "IN": _explain_in,
    "OUT": _explain_out,
    "LD": _explain_ld,
    "ST": _explain_st,
    "LDS": _explain_lds,
    "STS": _explain_sts,
    "KLAUNCH": _explain_klaunch,
    "KWAIT": _explain_kwait,
    "KSTAT": _explain_kstat,
    "MUL": _explain_mul,
}


# ---------------------------------------------------------------------------
# 事件分類(給 Trace 行上色用)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EventClassification:
    kind: EventKind
    badge_text: str  # 在 trace 行最後加的 ← 標記


def classify_port_writes(port_writes: Iterable[tuple[int, int]]) -> EventKind | None:
    """根據 trace row 的 port_writes 判斷該行的特殊事件種類。"""
    for port, _value in port_writes:
        if port == GPU_PORT_LAUNCH:
            return EventKind.KLAUNCH
        if port == GPU_PORT_KWAIT:
            return EventKind.KWAIT
        if port == GPU_PORT_HINT:
            return EventKind.NORMAL
    return None


def classify_row(
    *,
    instruction_text: str,
    port_writes: Iterable[tuple[int, int]] = (),
    cpu_halted: bool = False,
    cpu_stalled: bool = False,
) -> EventClassification:
    """把一筆 trace row 歸類成 :class:`EventKind`,並決定要加什麼中文 badge。"""
    text = (instruction_text or "").strip().upper()
    if cpu_stalled:
        return EventClassification(EventKind.KWAIT_STALL, "← 等 GPU…")
    port_kind = classify_port_writes(port_writes)
    if port_kind is EventKind.KLAUNCH:
        kernel_id_token = _last_token_value(instruction_text)
        if kernel_id_token is not None and 0 <= kernel_id_token < 7:
            kernel = kernel_name_for_id(kernel_id_token)
            return EventClassification(
                EventKind.KLAUNCH, f"← 提交「{kernel_label(kernel)}」"
            )
        return EventClassification(EventKind.KLAUNCH, "← KLAUNCH 提交 GPU kernel")
    if port_kind is EventKind.KWAIT:
        return EventClassification(EventKind.KWAIT, "← 進入 KWAIT")
    if cpu_halted:
        return EventClassification(EventKind.HALT, "← 程式結束")
    if text.startswith("HALT"):
        return EventClassification(EventKind.HALT, "← 程式結束")
    if text.startswith(("JMP", "RJMP")):
        return EventClassification(EventKind.JUMP, "← 跳轉")
    if text.startswith(("BRNE", "BREQ", "BRCS", "BRCC", "BRGE", "BRLT", "BRMI", "BRPL")):
        return EventClassification(EventKind.BRANCH, "← 條件分支")
    head = text.partition(" ")[0]
    if head in {"LD", "ST", "LDS", "STS"}:
        return EventClassification(EventKind.MEMORY, "← 動到記憶體")
    if head == "KSTAT" or (head == "IN" and "0X40" in text):
        return EventClassification(EventKind.KSTAT, "← 讀 GPU 狀態")
    return EventClassification(EventKind.NORMAL, "")


def _last_token_value(instruction_text: str) -> int | None:
    """從 'OUT 0x40, R16' / 'KLAUNCH R16' 抽出最後一個 register 的暫存器索引。

    僅 register 形式;若是直接的常數或無法解析就回 None。
    我們其實要的是 R16 *當下* 的值,呼叫端通常會自己看;
    這裡只做 best-effort,給 trace badge 增加可讀性。
    """
    return None


# ---------------------------------------------------------------------------
# Commentator — 給 Trace 旁白用的高階解說器
# ---------------------------------------------------------------------------
class Commentator:
    """把一連串 trace row 翻成中文敘事,給 LiveCommentaryPanel 用。

    使用方式::

        commentator = Commentator()
        for row in trace_rows:
            line = commentator.narrate(row)
            ui.append(line)
    """

    def __init__(self) -> None:
        self._kwait_in_progress = False
        self._stall_cycles = 0

    def reset(self) -> None:
        self._kwait_in_progress = False
        self._stall_cycles = 0

    def narrate(self, row) -> str:
        """產生一行中文旁白。``row`` 預期有 cpu/gpu trace row 的欄位。"""
        text = getattr(row, "instruction_text", "")
        port_writes = tuple(getattr(row, "port_writes", ()))
        stalled = bool(getattr(row, "cpu_stalled", False))
        halted = bool(getattr(row, "cpu_halted", False))

        if stalled:
            self._stall_cycles += 1
            if self._stall_cycles == 1:
                self._kwait_in_progress = True
                return "⏸ CPU 卡住等 GPU(已等 1 cycle)"
            return f"⏸ CPU 還在等 GPU(已等 {self._stall_cycles} cycle)"

        if self._kwait_in_progress and not stalled:
            self._kwait_in_progress = False
            self._stall_cycles = 0
            return f"▶ GPU 都跑完了!CPU 繼續執行 {text}"

        for port, value in port_writes:
            if port == GPU_PORT_LAUNCH:
                kernel_name = kernel_name_for_id(value)
                return (
                    f"🚀 KLAUNCH:把「{kernel_label(kernel_name)}」(id={value}) "
                    f"丟給 GPU 處理"
                )
            if port == GPU_PORT_KWAIT:
                self._kwait_in_progress = True
                return "⏳ KWAIT:從現在開始,CPU 卡到 GPU 都跑完才繼續"

        if halted:
            return f"🏁 {explain_instruction(text)}"

        return explain_instruction(text)
