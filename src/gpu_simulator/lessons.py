"""教學課程 — 五課中文導覽。

每一課用 :class:`Lesson` dataclass 描述,內容包含:
- 標題與簡介
- 預載的 ASM 程式
- 「重點觀察」清單(會跑在 Lesson 對話框旁邊)
- 對應的 Trace 分頁應該關注的 cycle / 指令

UI 端 (:class:`gpu_simulator.dialogs.GuidedLessonDialog`) 負責:
- 列出所有課程
- 點下一課 → 把 ASM 文字塞進 Input 編輯器
- 切換到 Tiny8 完整版分頁,自動執行
- 把講解逐段顯示在側欄
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lesson:
    code: str
    title: str
    summary: str
    asm_source: str
    use_full_tiny8: bool
    bullets: tuple[str, ...]


# ---------------------------------------------------------------------------
# 5 lessons
# ---------------------------------------------------------------------------
LESSONS: tuple[Lesson, ...] = (
    Lesson(
        code="lesson1_sm",
        title="第 1 課 · 認識 GPU:SM 跟 warp 是什麼",
        summary=(
            "在按下執行之前,我們先弄懂 GPU 內部長什麼樣。"
            "這支小工具裡的 GPU 有 8 個 SM(Streaming Multiprocessor),"
            "每個 SM 有 4 個 warp,每個 warp 有 32 條 thread。"
        ),
        asm_source=(
            "; 最簡單的程式:用兩條 ldi 指令把資料準備好,然後 halt。\n"
            "; 我們刻意不提交 GPU 工作 — 主要是要讓你看右邊的 GPU 在「閒置」狀態。\n"
            "    ldi r0, 0\n"
            "    ldi r1, 0\n"
            "    halt\n"
        ),
        use_full_tiny8=False,
        bullets=(
            "看 Live 分頁的 8 個方塊 — 那就是 8 個 SM,顏色越亮代表 warp 越忙",
            "目前每個 SM 都是冷色,因為我們還沒提交 GPU 工作",
            "VRAM 條也是 0%,合理",
            "下一課我們會送 GPU 第一個 kernel — 看 SM 怎麼亮起來",
        ),
    ),
    Lesson(
        code="lesson2_klaunch",
        title="第 2 課 · KLAUNCH:你的第一顆 GPU kernel",
        summary=(
            "GPU 不會自己動,要 CPU 寫資料到「LAUNCH port」(地址 0x40)它才會開始算。"
            "這一課我們用 `OUT 0x40, R16` 提交一顆 vector_add kernel。"
        ),
        asm_source=(
            "    ldi r16, 0          ; 0 = vector_add 的 kernel id\n"
            "    out 0x40, r16       ; KLAUNCH:把 R16 的值 (0) 推給 GPU\n"
            "    halt\n"
        ),
        use_full_tiny8=False,
        bullets=(
            "Trace 分頁的 OUT 0x40 那一行會被染成橘色 ← 那是 KLAUNCH 事件",
            "切到 Tiny8 完整版分頁,你會看到中間的 kernel 箭頭亮起",
            "等幾個 cycle,Live 分頁的 SM 方塊會逐顆亮綠 → 黃 → 紅",
            "VRAM 條也會跳一下 — 因為 vector_add 會吃 2 MiB",
        ),
    ),
    Lesson(
        code="lesson3_kwait",
        title="第 3 課 · KWAIT:為什麼 CPU 需要等 GPU",
        summary=(
            "提交 kernel 是「非同步」的 — CPU 提交完馬上就走,不會等 GPU 跑完。"
            "如果接下來的程式需要 GPU 的結果,就要用 KWAIT(寫到 0xFF)讓 CPU 卡住等。"
        ),
        asm_source=(
            "    ldi r16, 0\n"
            "    out 0x40, r16       ; 提交 vector_add\n"
            "    out 0x40, r16       ; 再提交一顆\n"
            "    out 0x40, r16       ; 再一顆\n"
            "    out 0xFF, r16       ; KWAIT:卡到 GPU 全部跑完\n"
            "    ldi r0, 42          ; 這一行只有等 GPU 都做完才會跑到\n"
            "    halt\n"
        ),
        use_full_tiny8=False,
        bullets=(
            "看 Trace 分頁:OUT 0xFF 那行被染成藍色,接下來幾行被染成灰色 — 那是 stall",
            "stall 期間 PC 不前進,但 GPU 那邊還在跑(8 個 SM 仍會忙碌)",
            "等到所有提交的 kernel 都完成,CPU 才繼續執行 LDI R0, 42",
            "如果不寫 KWAIT,LDI R0, 42 會在 GPU 還沒跑完時就執行 — 可能拿到舊資料",
        ),
    ),
    Lesson(
        code="lesson4_loop",
        title="第 4 課 · 用迴圈批次提交 — DEC + BRNE",
        summary=(
            "實務上往往要連發一堆 kernel。用 `DEC` 加 `BRNE` 就能寫一個迴圈,"
            "每跑一輪就提交一顆 kernel。"
        ),
        asm_source=(
            "    ldi r16, 1          ; 1 = interpolation 的 kernel id\n"
            "    ldi r17, 5          ; 提交 5 顆\n"
            "loop:\n"
            "    out 0x40, r16       ; KLAUNCH 一顆\n"
            "    dec r17             ; r17 -= 1,Z 旗標會被更新\n"
            "    brne loop           ; r17 != 0 就回去 loop\n"
            "    out 0xFF, r17       ; KWAIT(R17 已經是 0,但值不重要)\n"
            "    halt\n"
        ),
        use_full_tiny8=False,
        bullets=(
            "看 Heatmap 分頁的 SREG 那一列 — Z 旗標會固定不亮(因為 r17 不是 0)",
            "直到迴圈最後一輪,DEC 把 r17 變成 0,Z 旗標亮起,BRNE 才不再跳",
            "Trace 分頁可以看到 OUT 0x40 連續 5 次出現(都是橘色)",
            "之後 KWAIT,8 個 SM 一次跑 5 顆 interpolation,看 SM 利用率怎麼飆",
        ),
    ),
    Lesson(
        code="lesson5_full",
        title="第 5 課 · 用真正的 Tiny8 ISA 玩進階範例(MUL / RJMP)",
        summary=(
            "我們的子集 ISA 只有 ~20 個指令,但「Tiny8 完整版」分頁用的是真正完整的 60+ 指令。"
            "這一課用 MUL(乘法)算 12 × 7,然後丟給 GPU 做 page_nav kernel。"
            "請點對話框的「載入到 ASM 編輯器」後切到 🧬 Tiny8 完整版 分頁執行。"
        ),
        asm_source=(
            "; 這支用了「子集」ISA 不支援的 MUL 指令。\n"
            "; 載入後請切到「🧬 Tiny8 完整版」分頁執行。\n"
            "    ldi r16, 12\n"
            "    ldi r17, 7\n"
            "    mul r16, r17        ; r16 ← (12 × 7) 的低位元組 = 84\n"
            "    ldi r0, 6           ; 6 = page_nav kernel id\n"
            "    out 0x41, r16       ; HINT = 84\n"
            "    out 0x40, r0        ; KLAUNCH page_nav\n"
            "    out 0xFF, r0        ; KWAIT\n"
            "done:\n"
            "    jmp done\n"
        ),
        use_full_tiny8=True,
        bullets=(
            "MUL 是真實 AVR 才有的指令 — 我們的子集刻意省掉,讓你體會差別",
            "完整版分頁的並列視圖:左邊看到 R16 ← 84,右邊看到 GPU 開始忙 page_nav",
            "OUT 0x41 是「HINT」port,會把 R16 當下一顆 kernel 的 hint 傳給 GPU",
            "看完這課,你已經會 KLAUNCH / HINT / KWAIT 三大 GPU 控制 port 了 🎉",
        ),
    ),
)


def lesson_by_code(code: str) -> Lesson | None:
    for lesson in LESSONS:
        if lesson.code == code:
            return lesson
    return None
