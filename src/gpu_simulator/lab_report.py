"""自動產出實驗報告(Markdown + 嵌入 PNG 圖)。

跑完一支 ASM 之後,呼叫 :func:`generate_report`,會在 ``output_dir`` 下
產生:

- ``report.md`` — 完整實驗報告(可直接用 GitHub / VS Code / Pandoc 看 / 轉 PDF)
- ``utilization.png`` / ``vram.png`` / ``register_heatmap.png`` — 嵌入的圖

報告內容:
1. 標題、時間、版本
2. 完整源碼(Markdown 程式碼區塊)
3. 中文逐行解說(用 :mod:`gpu_simulator.commentary`)
4. 執行統計:cycle 數、提交 / 完成的 kernel 數、最終暫存器值
5. 視覺化:利用率隨 step、VRAM 隨 step、暫存器熱圖(如果 matplotlib 在)
6. 中文「執行重點」自動摘要

整支模組純 Python,沒有 Qt 相依,可以在 CI / 命令列下跑。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from gpu_simulator.commentary import classify_row, explain_instruction
from gpu_simulator.i18n import kernel_label


@dataclass(frozen=True)
class LabReportResult:
    markdown_path: Path
    image_paths: tuple[Path, ...]


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def generate_report(
    *,
    title: str,
    asm_source: str,
    trace_rows: Sequence,
    register_history: Sequence,
    memory_history: Sequence,
    sreg_history: Sequence,
    final_registers: Sequence[int],
    final_memory: Sequence[int],
    kernels_submitted: int,
    kernels_completed: int,
    output_dir: Path | str,
    notes: str = "",
) -> LabReportResult:
    """產出 Markdown 實驗報告與嵌入圖片。"""
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    image_paths = _try_render_images(
        trace_rows=trace_rows,
        register_history=register_history,
        memory_history=memory_history,
        output_dir=output_dir,
    )

    markdown_text = _build_markdown(
        title=title,
        asm_source=asm_source,
        trace_rows=trace_rows,
        final_registers=final_registers,
        final_memory=final_memory,
        kernels_submitted=kernels_submitted,
        kernels_completed=kernels_completed,
        image_paths=image_paths,
        notes=notes,
    )
    report_path = output_dir / "report.md"
    report_path.write_text(markdown_text, encoding="utf-8")
    return LabReportResult(markdown_path=report_path, image_paths=tuple(image_paths))


# ---------------------------------------------------------------------------
# Markdown 拼裝
# ---------------------------------------------------------------------------
def _build_markdown(
    *,
    title: str,
    asm_source: str,
    trace_rows: Sequence,
    final_registers: Sequence[int],
    final_memory: Sequence[int],
    kernels_submitted: int,
    kernels_completed: int,
    image_paths: Sequence[Path],
    notes: str,
) -> str:
    timestamp = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    total_cycles = len(trace_rows)
    sections: list[str] = []

    sections.append(f"# 🧪 GPU Simulator 實驗報告 — {title}")
    sections.append(f"*產出時間:{timestamp}*\n")
    if notes:
        sections.append(f"> {notes}\n")

    # 一、執行統計總覽
    sections.append("## 📊 執行統計總覽\n")
    sections.append("| 指標 | 數值 |")
    sections.append("| --- | --- |")
    sections.append(f"| Cycle 總數 | {total_cycles} |")
    sections.append(f"| 提交 GPU kernel 數 | {kernels_submitted} |")
    sections.append(f"| 完成 GPU kernel 數 | {kernels_completed} |")
    completion_rate = (
        f"{kernels_completed / kernels_submitted * 100:.1f}%"
        if kernels_submitted
        else "n/a"
    )
    sections.append(f"| Kernel 完成率 | {completion_rate} |")
    sections.append("")

    # 二、原始碼
    sections.append("## 💻 原始碼\n")
    sections.append("```asm")
    sections.append(asm_source.strip())
    sections.append("```\n")

    # 三、中文逐行解說
    sections.append("## 📖 中文逐行解說\n")
    for line_number, raw_line in enumerate(asm_source.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        explanation = explain_instruction(stripped.split(";", 1)[0])
        sections.append(f"- **L{line_number:>3} `{stripped[:60]}`** — {explanation}")
    sections.append("")

    # 四、最終狀態
    sections.append("## 📦 執行結束時的暫存器與記憶體\n")
    register_lines = []
    for index in range(0, len(final_registers), 8):
        chunk = final_registers[index : index + 8]
        cells = " ".join(f"R{index + offset:02}={value:>3}" for offset, value in enumerate(chunk))
        register_lines.append(cells)
    sections.append("```")
    sections.extend(register_lines)
    sections.append("```\n")

    if any(byte for byte in final_memory):
        sections.append("**記憶體中非零的位址(只列前 32 個非零位置):**\n")
        non_zero = [
            (addr, value)
            for addr, value in enumerate(final_memory)
            if value != 0
        ][:32]
        if non_zero:
            sections.append("| 位址 | 值 (10 進) | 值 (16 進) |")
            sections.append("| --- | --- | --- |")
            for addr, value in non_zero:
                sections.append(f"| 0x{addr:02X} | {value} | 0x{value:02X} |")
            sections.append("")
        else:
            sections.append("(全為 0)\n")

    # 五、事件統計
    event_counter = Counter()
    for row in trace_rows:
        classification = classify_row(
            instruction_text=getattr(row, "instruction_text", ""),
            port_writes=getattr(row, "port_writes", ()),
            cpu_halted=getattr(row, "cpu_halted", False),
            cpu_stalled=getattr(row, "cpu_stalled", False),
        )
        event_counter[classification.kind.value] += 1
    if event_counter:
        sections.append("## 🎯 事件種類分佈\n")
        sections.append("| 事件 | 次數 |")
        sections.append("| --- | --- |")
        for kind_name, count in event_counter.most_common():
            sections.append(f"| {kind_name} | {count} |")
        sections.append("")

    # 六、kernel 種類分佈
    kernel_counter = _count_kernel_dispatches(trace_rows)
    if kernel_counter:
        sections.append("## 🚀 GPU kernel 派送統計\n")
        sections.append("| 對應 kernel | 次數 |")
        sections.append("| --- | --- |")
        for kernel_id, count in kernel_counter.most_common():
            kernel_name = _kernel_id_to_name(kernel_id)
            chinese = kernel_label(kernel_name)
            sections.append(f"| {kernel_name}({chinese}) | {count} |")
        sections.append("")

    # 七、圖
    if image_paths:
        sections.append("## 📈 圖表\n")
        for image_path in image_paths:
            sections.append(f"![{image_path.stem}]({image_path.name})\n")

    # 八、自動摘要
    sections.append("## ✍️ 自動產出的執行重點摘要\n")
    sections.extend(_build_autosummary(trace_rows, kernel_counter))

    sections.append("\n---")
    sections.append("*Generated by `gpu_simulator.lab_report`.*")
    return "\n".join(sections) + "\n"


def _build_autosummary(trace_rows: Sequence, kernel_counter: Counter) -> list[str]:
    if not trace_rows:
        return ["(尚無 trace 可分析)"]
    lines: list[str] = []
    total = len(trace_rows)
    stalled_count = sum(
        1 for row in trace_rows if getattr(row, "cpu_stalled", False)
    )
    lines.append(
        f"- 整支程式跑了 **{total}** 個 cycle,其中 **{stalled_count}** 個 cycle 是 CPU 被 KWAIT 卡住"
    )
    if kernel_counter:
        most_common_id, most_common_count = kernel_counter.most_common(1)[0]
        kernel_chinese = kernel_label(_kernel_id_to_name(most_common_id))
        lines.append(
            f"- 最常被派送的 kernel:**{kernel_chinese}**(共 {most_common_count} 次)"
        )
    if stalled_count > 0:
        lines.append(
            f"- KWAIT 占了總 cycle 的 **{stalled_count / total * 100:.1f}%** — "
            "如果想壓低延遲,可以把 KLAUNCH 跟其他 CPU 工作交錯,讓兩邊同步進行"
        )
    lines.append(
        "- 想自己驗證:把這份報告連同原始 .asm 交回,任何人都能在 widget 重現結果"
    )
    return lines


# ---------------------------------------------------------------------------
# 圖表渲染
# ---------------------------------------------------------------------------
def _try_render_images(
    *,
    trace_rows: Sequence,
    register_history: Sequence,
    memory_history: Sequence,
    output_dir: Path,
) -> list[Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")  # headless-friendly
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    saved: list[Path] = []

    # 1) 利用率圖(虛擬:用 "running" warp 比例代表)
    if trace_rows:
        clocks = [getattr(row, "cycle", index) for index, row in enumerate(trace_rows)]
        running_share = []
        for row in trace_rows:
            stalled = getattr(row, "cpu_stalled", False)
            halted = getattr(row, "cpu_halted", False)
            if halted:
                running_share.append(0)
            elif stalled:
                running_share.append(1)
            else:
                running_share.append(2)
        figure, axis = plt.subplots(figsize=(6.5, 2.4))
        axis.step(clocks, running_share, where="post", color="#f0a040")
        axis.set_yticks([0, 1, 2])
        axis.set_yticklabels(["halted", "stalled", "running"])
        axis.set_xlabel("cycle")
        axis.set_title("CPU 狀態時序")
        axis.grid(True, alpha=0.3)
        figure.tight_layout()
        path = output_dir / "cpu_state_timeline.png"
        figure.savefig(path, dpi=120)
        plt.close(figure)
        saved.append(path)

    # 2) 暫存器熱圖
    if register_history:
        try:
            import numpy as np

            matrix = np.array(register_history, dtype=float).T
            figure, axis = plt.subplots(figsize=(6.5, 3.2))
            axis.imshow(matrix, aspect="auto", cmap="inferno", vmin=0, vmax=255, interpolation="nearest")
            axis.set_xlabel("step")
            axis.set_ylabel("register index")
            axis.set_title("R0–R31 隨 step 變化(顏色 = 值)")
            figure.tight_layout()
            path = output_dir / "register_heatmap.png"
            figure.savefig(path, dpi=120)
            plt.close(figure)
            saved.append(path)
        except ImportError:
            pass

    # 3) 記憶體 0x60–0x7F 熱圖
    if memory_history:
        try:
            import numpy as np

            sliced = [snapshot[0x60:0x80] for snapshot in memory_history]
            matrix = np.array(sliced, dtype=float).T
            figure, axis = plt.subplots(figsize=(6.5, 2.4))
            axis.imshow(matrix, aspect="auto", cmap="inferno", vmin=0, vmax=255, interpolation="nearest")
            axis.set_xlabel("step")
            axis.set_ylabel("memory address (0x60–0x7F)")
            axis.set_title("記憶體 0x60–0x7F 隨 step 變化")
            figure.tight_layout()
            path = output_dir / "memory_heatmap.png"
            figure.savefig(path, dpi=120)
            plt.close(figure)
            saved.append(path)
        except ImportError:
            pass

    return saved


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
_KERNEL_ID_TO_NAME = (
    "vector_add",
    "interpolation",
    "hash",
    "texture_load",
    "idle_compression",
    "app_launch",
    "page_nav",
)


def _kernel_id_to_name(kernel_id: int) -> str:
    return _KERNEL_ID_TO_NAME[kernel_id % len(_KERNEL_ID_TO_NAME)]


def _count_kernel_dispatches(trace_rows: Iterable) -> Counter:
    counter: Counter = Counter()
    for row in trace_rows:
        port_writes = getattr(row, "port_writes", ())
        for port, value in port_writes:
            if port == 0x40:
                counter[value & 0xFF] += 1
    return counter
