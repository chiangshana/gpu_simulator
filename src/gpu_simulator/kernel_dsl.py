"""Mini kernel DSL — Python-like 高階語法 → Tiny8 asm。

這是一個刻意縮小的 DSL,讓使用者寫:

```text
kernel my_op:
    let x = 5
    let y = 3
    let z = x + y
    launch vector_add
    wait
```

我們會編譯成等價的 Tiny8 asm:

```asm
    ldi r16, 5
    ldi r17, 3
    mov r18, r16
    add r18, r17
    ldi r0, 0
    out 0x40, r0
    out 0xff, r0
done:
    jmp done
```

支援的語法(刻意極簡,教學用):

- ``kernel <name>:``        — 整段程式的標頭(只有一個 kernel 區段)
- ``let <var> = <expr>``    — 宣告變數;expr 可以是常數、變數,或 ``a + b`` / ``a - b``
- ``inc <var>``             — 加 1
- ``dec <var>``             — 減 1
- ``launch <kernel_name>``  — 等同 ``OUT 0x40, R0`` + 預先 ``LDI R0, <id>``
- ``wait``                  — KWAIT
- ``# 任何中文註解``         — 整行忽略

功能不大但足夠展示「higher-level DSL → low-level ISA」的編譯器骨架,
書面報告寫起來很有料。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from gpu_simulator.exceptions import GPUVizError

# kernel id 表(對應 KernelLibrary)
_KERNEL_NAMES_TO_ID: dict[str, int] = {
    "vector_add": 0,
    "interpolation": 1,
    "hash": 2,
    "texture_load": 3,
    "idle_compression": 4,
    "app_launch": 5,
    "page_nav": 6,
}

_DEFAULT_REGISTER_BASE = 16  # 變數從 R16 開始分配,R0..R15 預留給 launch 用


class DSLCompileError(GPUVizError):
    """DSL 解析或編譯失敗。"""

    def __init__(self, line_number: int, message: str) -> None:
        self.line_number = line_number
        super().__init__(f"DSL line {line_number}: {message}")


@dataclass
class CompiledProgram:
    """DSL 編譯結果。"""

    asm_source: str
    variable_to_register: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def compile_dsl(source: str) -> CompiledProgram:
    """把 DSL 源碼編譯成 Tiny8 asm。"""
    state = _CompilerState()
    lines = source.splitlines()
    in_kernel = False

    for line_number, raw_line in enumerate(lines, start=1):
        text = raw_line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("kernel"):
            in_kernel = True
            continue
        if not in_kernel:
            raise DSLCompileError(
                line_number, "請先用 `kernel <name>:` 開頭"
            )
        _compile_statement(text, state, line_number)

    state.add_asm("done:")
    state.add_asm("    jmp done")
    return CompiledProgram(
        asm_source="\n".join(state.asm_lines) + "\n",
        variable_to_register=dict(state.variables),
    )


# ---------------------------------------------------------------------------
# 編譯器內部狀態
# ---------------------------------------------------------------------------
@dataclass
class _CompilerState:
    asm_lines: list[str] = field(default_factory=list)
    variables: dict[str, int] = field(default_factory=dict)
    next_register: int = _DEFAULT_REGISTER_BASE

    def add_asm(self, line: str) -> None:
        self.asm_lines.append(line)

    def assign_variable(self, name: str) -> int:
        if name in self.variables:
            return self.variables[name]
        if self.next_register >= 32:
            raise DSLCompileError(0, "register 用完了(只有 R16..R31 可用)")
        register = self.next_register
        self.variables[name] = register
        self.next_register += 1
        return register


# ---------------------------------------------------------------------------
# 各種 statement 的編譯
# ---------------------------------------------------------------------------
_LET_PATTERN = re.compile(r"^let\s+(\w+)\s*=\s*(.+)$")
_INC_PATTERN = re.compile(r"^inc\s+(\w+)$")
_DEC_PATTERN = re.compile(r"^dec\s+(\w+)$")
_LAUNCH_PATTERN = re.compile(r"^launch\s+(\w+)$")


def _compile_statement(text: str, state: _CompilerState, line_number: int) -> None:
    if text == "wait":
        state.add_asm("    out 0xff, r0")
        return

    match = _LET_PATTERN.match(text)
    if match:
        name, expr = match.group(1), match.group(2).strip()
        register = state.assign_variable(name)
        _emit_assignment(state, register, expr, line_number)
        return

    match = _INC_PATTERN.match(text)
    if match:
        name = match.group(1)
        register = _expect_var(state, name, line_number)
        state.add_asm(f"    inc r{register}")
        return

    match = _DEC_PATTERN.match(text)
    if match:
        name = match.group(1)
        register = _expect_var(state, name, line_number)
        state.add_asm(f"    dec r{register}")
        return

    match = _LAUNCH_PATTERN.match(text)
    if match:
        kernel_name = match.group(1)
        if kernel_name not in _KERNEL_NAMES_TO_ID:
            raise DSLCompileError(
                line_number, f"unknown kernel {kernel_name!r}"
            )
        kernel_id = _KERNEL_NAMES_TO_ID[kernel_name]
        state.add_asm(f"    ldi r0, {kernel_id}     ; {kernel_name}")
        state.add_asm("    out 0x40, r0")
        return

    raise DSLCompileError(line_number, f"看不懂這行:{text!r}")


def _emit_assignment(
    state: _CompilerState, dest_register: int, expr: str, line_number: int
) -> None:
    """處理 ``let <var> = <expr>`` 的右邊式子。"""
    expr = expr.strip()

    # 常數
    if expr.lstrip("-").isdigit() or expr.startswith("0x"):
        try:
            value = int(expr, 0)
        except ValueError as e:
            raise DSLCompileError(line_number, f"無法解析數字 {expr!r}") from e
        state.add_asm(f"    ldi r{dest_register}, {value & 0xff}")
        return

    # 加減運算 a + b / a - b
    for operator, mnemonic in (("+", "add"), ("-", "sub")):
        if operator in expr:
            left, right = (token.strip() for token in expr.split(operator, 1))
            left_reg = _resolve_to_register(state, left, line_number)
            right_reg = _resolve_to_register(state, right, line_number)
            state.add_asm(f"    mov r{dest_register}, r{left_reg}")
            state.add_asm(f"    {mnemonic} r{dest_register}, r{right_reg}")
            return

    # 單一變數複製
    if expr.isidentifier():
        source_reg = _expect_var(state, expr, line_number)
        state.add_asm(f"    mov r{dest_register}, r{source_reg}")
        return

    raise DSLCompileError(line_number, f"無法解析 expr {expr!r}")


def _resolve_to_register(
    state: _CompilerState, token: str, line_number: int
) -> int:
    """把 token 解析成「保證有一個 register 持有它的值」。

    若 token 是常數,會配一個隱形 var(``__tmp_<n>``)。
    """
    token = token.strip()
    if token.lstrip("-").isdigit() or token.startswith("0x"):
        tmp_name = f"__tmp_{len(state.variables)}"
        register = state.assign_variable(tmp_name)
        try:
            value = int(token, 0) & 0xFF
        except ValueError as e:
            raise DSLCompileError(line_number, f"無法解析數字 {token!r}") from e
        state.add_asm(f"    ldi r{register}, {value}")
        return register
    if token.isidentifier():
        return _expect_var(state, token, line_number)
    raise DSLCompileError(line_number, f"看不懂運算元 {token!r}")


def _expect_var(state: _CompilerState, name: str, line_number: int) -> int:
    if name not in state.variables:
        raise DSLCompileError(line_number, f"變數 {name!r} 尚未宣告(用 `let`)")
    return state.variables[name]
