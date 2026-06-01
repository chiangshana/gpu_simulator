"""CPU 狀態時間熱圖 — 教育核心:看 Tiny8 每個 cycle 的暫存器 / 記憶體變化。

仿造常見大學 CPU 模擬器作業的「state-over-time heatmap」:
y 軸由上到下三個區塊
  • SREG 8 個旗標位(I T H S V N Z C)— 二值
  • R0..R31 32 個暫存器 — 0..255 著色
  • Memory 0x60..0x7f 32 個記憶體格 — 0..255 著色
x 軸:cycle step(0..N)
標題:Step / PC / SP / 當前指令

支援:
  • 載入並執行一支 ASM(用 :class:`FullCPUGPUBridge`)
  • 顯示完整時間軸熱圖,可拖 slider 看任一步的精確值
  • 表格列出該 step 的所有暫存器與記憶體值(教學/作業批改用)

純資料層:
  • :func:`record_run` — 跑一支 ASM,回 :class:`CPUStateHistory`(可單獨測試)
  • :func:`registers_to_matrix` — 轉成 numpy 2D (32 x N) 矩陣
  • :func:`memory_to_matrix` — 轉成 numpy 2D (32 x N) 矩陣
  • :func:`sreg_to_matrix` — 轉成 numpy 2D (8 x N) 0/1 矩陣
"""

from __future__ import annotations

from dataclasses import dataclass

# SREG 8 個旗標位的名稱 — Tiny8 / AVR 慣例(I=最高位)
SREG_BITS: tuple[str, ...] = ("I", "T", "H", "S", "V", "N", "Z", "C")

# 記憶體窗 — 跟參考圖一致,看 0x60..0x7f 共 32 byte
MEMORY_WINDOW_START = 0x60
MEMORY_WINDOW_END = 0x80


# ---------------------------------------------------------------------------
# 資料容器
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CPUStateHistory:
    """跑完一支 ASM 的完整狀態時間軸。

    每個欄位都是長度為 ``len(steps)`` 的 list,代表 N 個 cycle 的快照。
    """

    steps: tuple[int, ...]
    pc_at_step: tuple[int, ...]
    sp_at_step: tuple[int, ...]
    instruction_text: tuple[str, ...]
    sreg_strings: tuple[str, ...]           # 每步 8-char "00010100" 字串
    registers: tuple[tuple[int, ...], ...]  # (N, 32) registers
    memory_window: tuple[tuple[int, ...], ...]  # (N, 32) 對應 0x60..0x7f

    @property
    def total_steps(self) -> int:
        return len(self.steps)


# ---------------------------------------------------------------------------
# 資料層 — 跑 ASM 並 record state
# ---------------------------------------------------------------------------
def record_run(asm_source: str, max_steps: int = 500) -> CPUStateHistory:
    """組譯並單步執行 ``asm_source``,回完整 :class:`CPUStateHistory`。

    使用 :class:`FullCPUGPUBridge`(Tiny8 完整版 ISA)。如果 ASM assemble 失敗,
    讓 :class:`AssemblerError`(或 vendored 版本對應的 exception)往上拋,
    UI 端負責顯示錯誤訊息。
    """
    from gpu_simulator.full_bridge import FullCPUGPUBridge

    bridge = FullCPUGPUBridge()
    bridge.load_source(asm_source)
    steps_executed = 0
    pcs: list[int] = []
    sps: list[int] = []
    instrs: list[str] = []
    while steps_executed < max_steps:
        pc_before = bridge.cpu.pc
        instr_text = _format_instruction_at(bridge.cpu, pc_before)
        # SP 在 Tiny8 完整版用 0x5D/0x5E I/O 兩位元組(stack pointer)
        sp = _read_sp(bridge.cpu)
        row = bridge.step()
        pcs.append(pc_before)
        sps.append(sp)
        instrs.append("(end)" if row.cpu_halted and not row.cpu_stalled else instr_text)
        steps_executed += 1
        if row.cpu_halted and not row.cpu_stalled:
            break
    n = len(bridge.register_history)
    # 對齊長度 — 後三個 list 必為 n
    pcs = pcs[:n]
    sps = sps[:n]
    instrs = instrs[:n]
    return CPUStateHistory(
        steps=tuple(range(1, n + 1)),
        pc_at_step=tuple(pcs),
        sp_at_step=tuple(sps),
        instruction_text=tuple(instrs),
        sreg_strings=tuple(bridge.sreg_history),
        registers=tuple(bridge.register_history),
        memory_window=tuple(
            tuple(mem[MEMORY_WINDOW_START:MEMORY_WINDOW_END])
            for mem in bridge.memory_history
        ),
    )


def _format_instruction_at(cpu, pc: int) -> str:
    """跟 full_bridge 一樣的字串組裝邏輯,但 standalone。"""
    if pc >= len(cpu.program):
        return "(end)"
    mnemonic, operands = cpu.program[pc]
    parts = []
    for operand in operands:
        if isinstance(operand, tuple) and len(operand) == 2 and operand[0] == "reg":
            parts.append(f"R{operand[1]}")
        else:
            parts.append(str(operand))
    return f"{mnemonic.upper()} {', '.join(parts)}".strip()


def _read_sp(cpu) -> int:
    """Tiny8 stack pointer 在 I/O 空間 0x5D(SPL)+ 0x5E(SPH)。"""
    try:
        spl = cpu.read_ram(0x5D)
        sph = cpu.read_ram(0x5E)
        return (sph << 8) | spl
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# 矩陣轉換 — UI 端 / matplotlib 用
# ---------------------------------------------------------------------------
def registers_to_matrix(history: CPUStateHistory) -> list[list[int]]:
    """轉成 [32][N] 矩陣 — 行 = R0..R31,列 = step。"""
    n = history.total_steps
    matrix = [[0] * n for _ in range(32)]
    for step_idx, regs in enumerate(history.registers):
        for r_idx, value in enumerate(regs[:32]):
            matrix[r_idx][step_idx] = int(value) & 0xFF
    return matrix


def memory_to_matrix(history: CPUStateHistory) -> list[list[int]]:
    """轉成 [32][N] 矩陣 — 行 = 0x60..0x7f,列 = step。"""
    width = MEMORY_WINDOW_END - MEMORY_WINDOW_START
    n = history.total_steps
    matrix = [[0] * n for _ in range(width)]
    for step_idx, mem in enumerate(history.memory_window):
        for m_idx, value in enumerate(mem[:width]):
            matrix[m_idx][step_idx] = int(value) & 0xFF
    return matrix


def sreg_to_matrix(history: CPUStateHistory) -> list[list[int]]:
    """SREG 字串 → [8][N] 0/1 矩陣;字串高位 = I,低位 = C。

    sreg_text helper 通常給 ``"00010100"`` 之類的字串 — 直接逐字 parse。
    若該步 sreg 字串長度不對(例如帶旗標字母),用 0 填。
    """
    n = history.total_steps
    matrix = [[0] * n for _ in range(8)]
    for step_idx, sreg in enumerate(history.sreg_strings):
        bits = _normalize_sreg_string(sreg)
        for bit_idx in range(8):
            matrix[bit_idx][step_idx] = bits[bit_idx]
    return matrix


def _normalize_sreg_string(sreg: str) -> tuple[int, ...]:
    """把任何形式的 sreg 字串(``"01010101"`` 或 ``"-T-S---C"``)轉成 8 個 0/1。

    規則:長度截到 8;``"1"`` 或字母(代表旗標被點亮)→ 1,其餘 → 0。
    """
    s = (sreg or "").ljust(8, "0")[:8]
    bits = []
    for ch in s:
        if ch == "1":
            bits.append(1)
        elif ch == "0" or ch == "-":
            bits.append(0)
        elif ch.isalpha():
            bits.append(1)
        else:
            bits.append(0)
    return tuple(bits)


# ---------------------------------------------------------------------------
# Qt widget(可選) — 整合 matplotlib FigureCanvas + slider + 控制列
# ---------------------------------------------------------------------------
def build_heatmap_tab(parent=None):
    """建一個完整的「CPU 狀態時間熱圖」分頁。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QSlider,
        QSpinBox,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )

    box = QWidget(parent)
    outer = QVBoxLayout(box)
    outer.setContentsMargins(8, 8, 8, 8)

    header = QLabel(
        "🧪 <b>CPU 狀態變化色塊圖</b> — 跑一段程式指令(組合語言 ASM),"
        "看 CPU 內部 8 個小燈(狀態旗標 SREG)、32 個小格子(暫存器 R0–R31)、"
        "記憶體 0x60–0x7F,每一拍(cycle)怎麼變化"
    )
    header.setStyleSheet("color: rgba(220,230,240,240); font-size: 11pt;")
    header.setWordWrap(True)
    outer.addWidget(header)

    splitter = QSplitter(Qt.Horizontal, box)
    outer.addWidget(splitter, 1)

    # 左邊:ASM 編輯器
    left = QWidget(splitter)
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(4, 4, 4, 4)
    left_layout.addWidget(QLabel("程式指令(組合語言 ASM):"))
    editor = QPlainTextEdit(left)
    editor.setPlainText(_DEFAULT_DEMO_ASM)
    editor.setStyleSheet(
        "background: rgba(20,20,28,230); color: #d8e6f8; "
        "font-family: Consolas, 'Cascadia Mono', monospace; font-size: 10pt;"
    )
    left_layout.addWidget(editor, 1)
    run_row = QHBoxLayout()
    max_steps_box = QSpinBox(left)
    max_steps_box.setRange(10, 5000)
    max_steps_box.setValue(200)
    max_steps_box.setPrefix("最多跑幾拍:")
    run_btn = QPushButton("▶️ 開跑並畫圖", left)
    run_row.addWidget(max_steps_box)
    run_row.addWidget(run_btn, 1)
    left_layout.addLayout(run_row)
    splitter.addWidget(left)

    # 右邊:matplotlib canvas + slider
    right = QWidget(splitter)
    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(4, 4, 4, 4)

    status_lbl = QLabel("還沒開始。請按左下「▶️ 開跑並畫圖」按鈕。", right)
    status_lbl.setStyleSheet("color: rgba(240,220,140,240); font-size: 10pt;")
    right_layout.addWidget(status_lbl)

    canvas_holder = QVBoxLayout()
    right_layout.addLayout(canvas_holder, 1)

    slider_row = QHBoxLayout()
    slider_lbl = QLabel("第幾拍:", right)
    slider = QSlider(Qt.Horizontal, right)
    slider.setMinimum(1)
    slider.setMaximum(1)
    slider_row.addWidget(slider_lbl)
    slider_row.addWidget(slider, 1)
    right_layout.addLayout(slider_row)

    detail_lbl = QLabel("(按上面執行後,拖下方拉桿可以看任一拍的精確數值)", right)
    detail_lbl.setStyleSheet("color: rgba(200,210,225,235); font-size: 10pt;")
    detail_lbl.setWordWrap(True)
    right_layout.addWidget(detail_lbl)

    splitter.addWidget(right)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 2)

    # 內部狀態
    state: dict = {
        "history": None,
        "canvas": None,
        "figure": None,
        "cursor_line": None,
    }

    def render_history(history: CPUStateHistory) -> None:
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure
        except ImportError:
            status_lbl.setText("⚠️ 需要 matplotlib,請 `pip install matplotlib`")
            return
        # 清掉舊的 canvas
        for i in reversed(range(canvas_holder.count())):
            w = canvas_holder.itemAt(i).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        fig = Figure(figsize=(7, 5.4), tight_layout=True, facecolor="#0d0e14")
        ax_sreg = fig.add_subplot(311)
        ax_reg = fig.add_subplot(312, sharex=ax_sreg)
        ax_mem = fig.add_subplot(313, sharex=ax_sreg)

        sreg_mat = sreg_to_matrix(history)
        reg_mat = registers_to_matrix(history)
        mem_mat = memory_to_matrix(history)

        ax_sreg.imshow(
            sreg_mat, aspect="auto", interpolation="nearest", cmap="YlOrBr_r", vmin=0, vmax=1
        )
        ax_sreg.set_yticks(range(8))
        ax_sreg.set_yticklabels(SREG_BITS, fontsize=7, color="white")
        ax_sreg.set_ylabel("SREG", color="white", fontsize=8)
        ax_sreg.tick_params(axis="x", colors="#a0a4b0", labelsize=7)
        ax_sreg.set_facecolor("#0d0e14")

        ax_reg.imshow(
            reg_mat, aspect="auto", interpolation="nearest", cmap="inferno", vmin=0, vmax=255
        )
        ax_reg.set_yticks(range(0, 32, 2))
        ax_reg.set_yticklabels([f"R{i}" for i in range(0, 32, 2)], fontsize=7, color="white")
        ax_reg.set_ylabel("Registers", color="white", fontsize=8)
        ax_reg.tick_params(axis="x", colors="#a0a4b0", labelsize=7)
        ax_reg.set_facecolor("#0d0e14")

        im = ax_mem.imshow(
            mem_mat, aspect="auto", interpolation="nearest", cmap="inferno", vmin=0, vmax=255
        )
        addrs = list(range(MEMORY_WINDOW_START, MEMORY_WINDOW_END))
        ax_mem.set_yticks(range(0, len(addrs), 2))
        ax_mem.set_yticklabels([f"0x{addrs[i]:02x}" for i in range(0, len(addrs), 2)],
                                fontsize=7, color="white")
        ax_mem.set_ylabel("Memory", color="white", fontsize=8)
        ax_mem.set_xlabel("Step", color="white", fontsize=8)
        ax_mem.tick_params(axis="x", colors="#a0a4b0", labelsize=7)
        ax_mem.set_facecolor("#0d0e14")

        fig.colorbar(im, ax=[ax_sreg, ax_reg, ax_mem], shrink=0.7, pad=0.02)

        cursor_line = ax_reg.axvline(0, color="#ffffff", linewidth=1.2, alpha=0.6)
        cursor_line_mem = ax_mem.axvline(0, color="#ffffff", linewidth=1.2, alpha=0.6)
        cursor_line_sreg = ax_sreg.axvline(0, color="#ffffff", linewidth=1.2, alpha=0.6)

        canvas = FigureCanvasQTAgg(fig)
        canvas_holder.addWidget(canvas)
        state["history"] = history
        state["canvas"] = canvas
        state["figure"] = fig
        state["cursor_lines"] = (cursor_line, cursor_line_mem, cursor_line_sreg)
        canvas.draw()

        # 更新 slider 範圍
        slider.setMaximum(history.total_steps)
        slider.setValue(history.total_steps)
        refresh_detail(history.total_steps)

    def refresh_detail(step: int) -> None:
        history: CPUStateHistory | None = state.get("history")
        if history is None or history.total_steps == 0:
            return
        idx = max(0, min(history.total_steps - 1, step - 1))
        pc = history.pc_at_step[idx]
        sp = history.sp_at_step[idx]
        instr = history.instruction_text[idx]
        sreg = history.sreg_strings[idx]
        regs = history.registers[idx]
        title = (
            f"Step: {history.steps[idx]:3d}    "
            f"PC: 0x{pc:04x}    SP: 0x{sp:04x}    {instr}    "
            f"SREG: {sreg}"
        )
        # 顯示前 8 個暫存器當作快速覽
        reg_preview = "  ".join(
            f"R{i}={regs[i]:3d}" for i in range(min(8, len(regs)))
        )
        detail_lbl.setText(f"<pre>{title}\n{reg_preview}</pre>")
        # 移動游標
        canvas = state.get("canvas")
        cursor_lines = state.get("cursor_lines")
        if canvas is not None and cursor_lines is not None:
            for line in cursor_lines:
                line.set_xdata([idx, idx])
            canvas.draw_idle()

    def run_clicked() -> None:
        source = editor.toPlainText()
        max_steps = max_steps_box.value()
        try:
            history = record_run(source, max_steps=max_steps)
        except Exception as exc:
            status_lbl.setText(f"❌ 跑失敗(程式有錯):{exc}")
            return
        status_lbl.setText(
            f"✅ 跑完 {history.total_steps} 拍 — 拖下方拉桿看任一拍的詳細狀態"
        )
        render_history(history)

    slider.valueChanged.connect(refresh_detail)
    run_btn.clicked.connect(run_clicked)

    return box


_DEFAULT_DEMO_ASM = """; CPU 狀態時間熱圖 — 預設展示程式
; 把幾個值寫入暫存器,看看熱圖長怎樣
    ldi r16, 5
    ldi r17, 10
    ldi r18, 20
    ldi r19, 40
    ldi r20, 80
    ldi r21, 160
    add r16, r17
    add r18, r19
    inc r20
    inc r20
    inc r21
    mov r22, r16
    mov r23, r18
"""
