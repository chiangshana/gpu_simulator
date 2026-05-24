"""考考你 — 跑完 ASM 後彈一份 5 題選擇題。

題目分兩類:

1. **靜態題庫**(模組常數)— 涵蓋一般性的 GPU / Tiny8 觀念,任何 session 都能用。
2. **動態題目**(由最後一段 trace 推得)— 例如「最後 R16 是多少」「GPU 完成幾顆 kernel」。

題目選擇邏輯故意簡單(明確答案不靠猜),目標是把使用者剛剛看到的東西
鞏固一遍,而不是出難題。
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class QuizQuestion:
    prompt: str
    options: tuple[str, ...]
    correct_index: int
    explanation: str


# ---------------------------------------------------------------------------
# 靜態題庫
# ---------------------------------------------------------------------------
STATIC_QUESTIONS: tuple[QuizQuestion, ...] = (
    QuizQuestion(
        prompt="一張典型的 NVIDIA GPU 是用什麼名字的核心執行 warp?",
        options=("ALU", "Streaming Multiprocessor (SM)", "DSP", "MMU"),
        correct_index=1,
        explanation=(
            "Streaming Multiprocessor 才是 GPU 上負責執行 warp 的單位;"
            "ALU/DSP/MMU 是其他通用名詞。"
        ),
    ),
    QuizQuestion(
        prompt="在我們的小工具裡,KWAIT 指令的目的是什麼?",
        options=(
            "讓 CPU 進入睡眠模式以節能",
            "讓 CPU 卡住直到 GPU 把所有提交的 kernel 跑完",
            "強制清空 VRAM",
            "停止整個程式並關閉 widget",
        ),
        correct_index=1,
        explanation="KWAIT = busy-wait until the GPU is idle,讓 CPU 跟 GPU 同步。",
    ),
    QuizQuestion(
        prompt="一個 warp 通常包含幾條 thread?",
        options=("8", "16", "32", "256"),
        correct_index=2,
        explanation="主流 GPU 一個 warp 是 32 條 thread,所以 KLAUNCH 一次至少會啟動 32 條。",
    ),
    QuizQuestion(
        prompt="下列哪一段 pipeline 階段是「把暫存器寫回去」?",
        options=("Fetch", "Decode", "Memory", "Writeback"),
        correct_index=3,
        explanation="5 階 pipeline = Fetch → Decode → Execute → Memory → Writeback。",
    ),
    QuizQuestion(
        prompt="在這個小工具中,VRAM 進度條顯示的是什麼?",
        options=(
            "目前已分配給尚未結束 kernel 的位元組數",
            "GPU 中央處理器的負載",
            "遊戲畫面的解析度",
            "電源使用瓦數",
        ),
        correct_index=0,
        explanation="VRAM 條顯示的是目前所有「還沒釋放」的 kernel 共佔用的 GPU 記憶體。",
    ),
    QuizQuestion(
        prompt="Tiny8 風格 Heatmap 的縱軸最下面那層代表什麼?",
        options=("時鐘 cycle 數", "32 個暫存器", "0x60–0x7F 範圍的記憶體", "8 顆 SM"),
        correct_index=2,
        explanation="Heatmap 從上到下:SREG flags / R0–R31 / 記憶體 0x60–0x7F。",
    ),
    QuizQuestion(
        prompt="哪一個指令是「把暫存器值寫到記憶體」?",
        options=("LD Rd, Rr", "ST Rr, Rs", "MOV Rd, Rr", "OUT port, Rr"),
        correct_index=1,
        explanation="ST Rr, Rs 把暫存器 Rs 的值寫到 memory[Rr]。",
    ),
    QuizQuestion(
        prompt="以下哪個事件會在我們的小工具觸發 texture_load(紋理載入)kernel?",
        options=("滑鼠移動", "鍵盤輸入", "切換到別的 App(視窗焦點變動)", "閒置超過 5 秒"),
        correct_index=2,
        explanation="切換前景視窗會被當成「載入新 App 紋理」,觸發 texture_load。",
    ),
    QuizQuestion(
        prompt="若 SREG 顯示 ZNCV = `Z---`,代表什麼?",
        options=(
            "結果是 0(Z 旗標被設起,其餘清掉)",
            "出現負數",
            "出現進位",
            "整數溢位",
        ),
        correct_index=0,
        explanation="Z=零旗標,值為 1 表示最近一次運算結果是 0。",
    ),
    QuizQuestion(
        prompt="哪個操作會觸發我們的小工具提交 idle_compression(閒置壓縮)kernel?",
        options=(
            "瘋狂打字",
            "拖曳視窗",
            "什麼都不做超過 5 秒",
            "按下重置鍵",
        ),
        correct_index=2,
        explanation="閒置監聽器在 5 秒沒事件時會丟一顆 idle_compression。",
    ),
)


# ---------------------------------------------------------------------------
# 動態題目產生(根據最後一輪 ASM trace)
# ---------------------------------------------------------------------------
def build_dynamic_questions(
    *,
    final_register_value_r0: int | None,
    kernels_submitted: int,
    kernels_completed: int,
    cycles_executed: int,
) -> list[QuizQuestion]:
    questions: list[QuizQuestion] = []

    if final_register_value_r0 is not None:
        actual = int(final_register_value_r0)
        # 三個誤導選項
        misleading = sorted(
            {
                (actual + 1) & 0xFF,
                (actual + 7) & 0xFF,
                (actual ^ 0xFF) & 0xFF,
                0,
            }
            - {actual}
        )[:3]
        options_pool = [actual, *misleading]
        random.shuffle(options_pool)
        correct_index = options_pool.index(actual)
        questions.append(
            QuizQuestion(
                prompt="剛剛這支 ASM 跑完之後,R0 的值是多少?",
                options=tuple(str(value) for value in options_pool),
                correct_index=correct_index,
                explanation=f"看 Trace / Debug 分頁的 R0 欄位,實際值是 {actual}。",
            )
        )

    if kernels_submitted >= 0:
        actual = int(kernels_submitted)
        options_pool = sorted({actual, max(0, actual - 1), actual + 1, actual + 3})[:4]
        if actual not in options_pool:
            options_pool[0] = actual
        random.shuffle(options_pool)
        correct_index = options_pool.index(actual)
        questions.append(
            QuizQuestion(
                prompt="這次跑完總共提交了幾顆 kernel 給 GPU?",
                options=tuple(str(value) for value in options_pool),
                correct_index=correct_index,
                explanation=(
                    f"Trace / Live 分頁的「submitted」欄位顯示 {actual},"
                    f"完成的是 {kernels_completed}。"
                ),
            )
        )

    if cycles_executed > 0:
        actual = int(cycles_executed)
        if actual >= 5:
            options_pool = sorted({actual, actual - 3, actual + 4, max(1, actual // 2)})
        else:
            options_pool = sorted({actual, actual + 1, actual + 2, actual + 5})
        # 修正可能落在外面的選項
        if actual not in options_pool:
            options_pool[0] = actual
        random.shuffle(options_pool)
        correct_index = options_pool.index(actual)
        questions.append(
            QuizQuestion(
                prompt="這次 ASM 從開始到 HALT 共花了幾個 cycle?",
                options=tuple(str(value) for value in options_pool),
                correct_index=correct_index,
                explanation=f"Trace 表格最後一列的 Cycle 編號是 {actual}。",
            )
        )

    return questions


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def build_quiz(
    *,
    static_count: int = 3,
    dynamic_questions: Sequence[QuizQuestion] = (),
    seed: int | None = None,
) -> list[QuizQuestion]:
    """組一份 5 題的小考(預設 3 題靜態 + 至多 2 題動態)。"""
    rng = random.Random(seed)
    static_pool = list(STATIC_QUESTIONS)
    rng.shuffle(static_pool)
    selected_static = static_pool[: max(0, static_count)]
    selected_dynamic = list(dynamic_questions)[: max(0, 5 - len(selected_static))]
    questions = selected_static + selected_dynamic
    rng.shuffle(questions)
    return questions[:5]
