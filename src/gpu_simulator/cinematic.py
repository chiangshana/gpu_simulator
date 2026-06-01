"""電影模式 (cinematic showcase) — 60 秒劇本式自動 demo。

`gpu-simulator --cinema` 啟動後,widget 不接 OS 事件,改照一份預設劇本
跑一連串展示:切分頁、跑範例 asm、解鎖成就、放煙火、最後 fade out。
**直接拍下來就是展示影片的素材**,後製成本接近 0。

劇本用 :class:`CinemaScript` 表達(純資料,可單獨測試);UI 端的
:class:`CinemaPlayer`(透過 :func:`build_player`)用 QTimer 一格一格觸發事件。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum


class CinemaActionKind(Enum):
    """一個劇本步驟的種類。"""

    SHOW_CAPTION = "show_caption"       # 螢幕上方顯示一行中文字幕
    SWITCH_TAB = "switch_tab"            # 切到指定分頁(by tab name)
    LOAD_AND_RUN_ASM = "load_and_run_asm"  # 載入 asm 並跑(藉 asm panel)
    PLAY_KERNEL_CHORD = "play_kernel_chord"  # 播放 kernel 的音
    PARTICLE_BURST = "particle_burst"    # 觸發粒子煙火
    HIGHLIGHT_FEATURE = "highlight_feature"  # 短暫聚焦某個 UI 區塊
    WAIT = "wait"                        # 純等待 N 毫秒
    DONE = "done"                        # 結束


@dataclass(frozen=True)
class CinemaAction:
    kind: CinemaActionKind
    payload: dict = field(default_factory=dict)
    duration_ms: int = 1500  # 這個動作之後等多久才換下一個

    def with_(self, **overrides) -> CinemaAction:
        new_payload = dict(self.payload)
        new_payload.update(overrides)
        return CinemaAction(kind=self.kind, payload=new_payload, duration_ms=self.duration_ms)


@dataclass(frozen=True)
class CinemaScript:
    name: str
    description: str
    actions: tuple[CinemaAction, ...]

    @property
    def total_duration_ms(self) -> int:
        return sum(action.duration_ms for action in self.actions)


# ---------------------------------------------------------------------------
# 預設 60-second 劇本
# ---------------------------------------------------------------------------
def builtin_60_second_script() -> CinemaScript:
    """60 秒劇本 — 第十四輪改寫,以 🪞 對照鏡 開場,把專題論述放最前。

    結構:
    * 0–18s  論述具象化:🪞 對照鏡 → 觸發負載 → 看左跳右不動
    * 18–28s 支柱 ① 教學核心:🌡️ 狀態熱圖
    * 28–38s 支柱 ③ 真實硬體:💻 真實硬體
    * 38–55s 其他亮點速覽:Cycle Cinema / Tiny8 完整版 / 進階 GPU
    * 55–60s 收尾
    """
    actions = (
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "🎬 GPU Simulator · 30 秒看完專題核心論述"},
            duration_ms=2500,
        ),
        # ── 0–18s 對照鏡:把論述變成可以看到的圖 ──────────────────────────
        CinemaAction(
            CinemaActionKind.SWITCH_TAB,
            payload={"tab": "🪞 對照鏡"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "左邊:模擬 GPU 8 顆 SM    |    右邊:你電腦真實 N 顆 CPU 核心"},
            duration_ms=3000,
        ),
        CinemaAction(
            CinemaActionKind.LOAD_AND_RUN_ASM,
            payload={
                "asm": (
                    "    ldi r16, 0\n"
                    "    klaunch r16\n"
                    "    klaunch r16\n"
                    "    klaunch r16\n"
                    "    kwait\n"
                    "    halt\n"
                ),
            },
            duration_ms=3500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "看!左邊 SM 跳起來,右邊 CPU 不動 — 模擬器跟真實電腦是兩件事"},
            duration_ms=3500,
        ),
        CinemaAction(
            CinemaActionKind.PARTICLE_BURST,
            payload={"kind": "firework"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "這就是專題論述:模擬世界學原理,真實世界看效果,並排對照"},
            duration_ms=3000,
        ),
        # ── 18–28s 支柱 ① 教學核心 ─────────────────────────────────────
        CinemaAction(
            CinemaActionKind.SWITCH_TAB,
            payload={"tab": "🌡️ 狀態熱圖"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "支柱 ①:寫 Tiny8 ASM,看每個 cycle 暫存器 / 記憶體 / SREG 變化熱圖"},
            duration_ms=5000,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "拖時間軸 slider 可以時光旅行到任一個 cycle"},
            duration_ms=3500,
        ),
        # ── 28–38s 支柱 ③ 真實硬體 ─────────────────────────────────────
        CinemaAction(
            CinemaActionKind.SWITCH_TAB,
            payload={"tab": "💻 真實硬體"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "支柱 ③:你電腦真實 N 顆 CPU 核心 + NVIDIA GPU 即時負載"},
            duration_ms=5000,
        ),
        # ── 38–55s 其他亮點速覽 ───────────────────────────────────────
        CinemaAction(
            CinemaActionKind.SWITCH_TAB,
            payload={"tab": "🎬 Cycle Cinema"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "🎬 Cycle Cinema — CPU 跟 GPU 同框慢動作"},
            duration_ms=2500,
        ),
        CinemaAction(
            CinemaActionKind.SWITCH_TAB,
            payload={"tab": "🧬 Tiny8 完整版"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "🧬 內嵌真正的 Tiny8 CPU,60+ 指令完整 ISA"},
            duration_ms=2500,
        ),
        CinemaAction(
            CinemaActionKind.SWITCH_TAB,
            payload={"tab": "🧠 進階 GPU"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "🧠 Warp 發散 + Memory coalescing 視覺化"},
            duration_ms=2500,
        ),
        # ── 55–60s 收尾 ───────────────────────────────────────────────
        CinemaAction(
            CinemaActionKind.SWITCH_TAB,
            payload={"tab": "🪞 對照鏡"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.PARTICLE_BURST,
            payload={"kind": "firework"},
            duration_ms=1500,
        ),
        CinemaAction(
            CinemaActionKind.SHOW_CAPTION,
            payload={"text": "🐲 模擬 vs 真實 · 並排對照 · 期末專題完整呈現"},
            duration_ms=3000,
        ),
        CinemaAction(
            CinemaActionKind.DONE,
            payload={},
            duration_ms=0,
        ),
    )
    return CinemaScript(
        name="60-second showcase",
        description="60 秒以 🪞 對照鏡 為開場,展示模擬 vs 真實並排論述",
        actions=actions,
    )


# ---------------------------------------------------------------------------
# 10 分鐘詳細導覽劇本 — 比 60 秒版慢很多,每個概念都會停留讓使用者讀字幕
# ---------------------------------------------------------------------------
def _cap(text: str, secs: float) -> CinemaAction:
    """字幕 helper:給文字 + 顯示秒數,自動換成 SHOW_CAPTION action。"""
    return CinemaAction(
        CinemaActionKind.SHOW_CAPTION,
        payload={"text": text},
        duration_ms=int(secs * 1000),
    )


def _switch(tab_name: str, secs: float = 2.0) -> CinemaAction:
    """換分頁 helper。"""
    return CinemaAction(
        CinemaActionKind.SWITCH_TAB,
        payload={"tab": tab_name},
        duration_ms=int(secs * 1000),
    )


def _wait(secs: float) -> CinemaAction:
    return CinemaAction(
        CinemaActionKind.WAIT,
        payload={},
        duration_ms=int(secs * 1000),
    )


def builtin_10_minute_tutorial_script() -> CinemaScript:
    """10 分鐘詳細導覽 — 假設觀眾完全不會寫程式,把 CPU / GPU / 暫存器 / 程式
    一個一個概念講過去,搭配每個分頁實際操作。

    結構(總時長約 600 秒):
    *   0– 60s  開場、本工具是什麼、要介紹哪些東西
    *  60–180s  概念 1:CPU vs GPU 是什麼,為什麼要兩個
    * 180–300s  概念 2:CPU 內部長怎樣(暫存器 = 小格子)
    * 300–420s  概念 3:程式怎麼跑(一拍一拍、指令是什麼)
    * 420–510s  概念 4:GPU 為什麼比較快(平行)
    * 510–600s  收尾、回到對照鏡再看一次
    """
    actions = (
        # ──────────────────── 0–60s 開場 ────────────────────
        _cap("📖 歡迎使用!接下來 10 分鐘帶你看懂這個工具", 7.8),
        _cap("不用懂程式也沒關係 — 我們會從最基本的概念講起", 7.8),
        _cap("這個工具的目標是讓你「看見」電腦內部到底在做什麼", 9.3),
        _cap("我們會介紹 4 個概念:CPU、GPU、暫存器、程式怎麼跑", 10.8),
        _cap("每個概念都有對應的分頁,看完你會懂為什麼電腦能算這麼快", 10.8),
        _cap("準備好了嗎?開始 👇", 6.2),

        # ──────────────────── 60–180s 概念 1:CPU vs GPU ────────────────────
        _switch("🪞 對照", 2),
        _cap("這是「對照鏡」分頁,左右兩邊各代表一個世界", 9.3),
        _cap("左邊 = 我們自己寫程式做出來的「假 GPU」(模擬的)", 9.3),
        _cap("右邊 = 你這台筆電裡面真實的 CPU 核心", 9.3),
        _cap("CPU = Central Processing Unit,電腦的大腦", 9.3),
        _cap("GPU = Graphics Processing Unit,顯示卡,負責算大量的圖形 / 並行運算", 10.8),
        _cap("差別:CPU 通常 4–24 核,每個核很聰明、什麼都能做", 10.8),
        _cap("GPU 有幾千個小核,每個比較笨,但「一起算同一件事」非常快", 10.8),
        _cap("等一下我們會派一個任務給左邊的模擬 GPU,看它跳起來", 9.3),
        CinemaAction(
            CinemaActionKind.LOAD_AND_RUN_ASM,
            payload={
                "asm": (
                    "    ldi r16, 0\n"
                    "    klaunch r16\n"
                    "    klaunch r16\n"
                    "    klaunch r16\n"
                    "    kwait\n"
                    "    halt\n"
                ),
            },
            duration_ms=4000,
        ),
        _cap("看到了嗎?左邊 SM 跳起來,右邊 CPU 幾乎沒動", 10.8),
        _cap("這就是專題的論述:模擬世界跟真實世界是兩件事,但能並排對照", 12.4),

        # ──────────────────── 180–300s 概念 2:CPU 內部 ────────────────────
        _switch("🌡️ 變化", 2),
        _cap("好,現在來看 CPU「內部」長什麼樣子", 7.8),
        _cap("CPU 算東西時,要把數字暫時存在哪?答案是「暫存器」", 9.3),
        _cap("暫存器 = CPU 內部的小格子,只有 32 個,每個能存 0–255", 10.8),
        _cap("為什麼只有 32 個?因為它們是離計算單元最近的儲存,容量小但速度極快", 12.4),
        _cap("除了暫存器,還有「記憶體」 — 容量大很多,但比較慢", 10.8),
        _cap("還有「狀態旗標(SREG)」 — 8 個小燈,記住上一步運算的結果是不是零、有沒有溢位", 12.4),
        _cap("這個分頁的三層色塊圖就是把這三樣東西畫出來", 9.3),
        _cap("我們現在按「開跑並畫圖」,跑一段範例程式,看格子怎麼變", 9.3),
        CinemaAction(
            CinemaActionKind.LOAD_AND_RUN_ASM,
            payload={
                "asm": (
                    "    ldi r16, 5\n"
                    "    ldi r17, 10\n"
                    "    ldi r18, 20\n"
                    "    add r16, r17\n"
                    "    add r18, r16\n"
                    "    mov r19, r18\n"
                ),
            },
            duration_ms=5000,
        ),
        _cap("看到了嗎?暫存器格子的顏色從深(0)變到亮(數值大),每一拍都記錄下來", 12.4),
        _cap("這就是「程式跑起來時 CPU 內部發生的事」的視覺化", 9.3),
        _cap("可以拖下方的時間軸,看任何一拍 CPU 那 32 個格子裝什麼值", 10.8),

        # ──────────────────── 300–420s 概念 3:程式怎麼跑 ────────────────────
        _switch("⌨️ 寫程式", 2),
        _cap("剛才我們跑的是「組合語言」(ASM) — 最接近機器的程式語言", 10.8),
        _cap("一行 = 一個指令,CPU 一次只做一件事", 9.3),
        _cap("例如「ldi r16, 5」 = 把數字 5 放進 16 號小格子", 9.3),
        _cap("「add r16, r17」 = 把 16 號 + 17 號的值,結果存回 16 號", 10.8),
        _cap("CPU 跑完每個指令叫做「走一拍」(cycle)", 9.3),
        _cap("一秒可以走幾十億拍 — 這就是為什麼電腦看起來這麼快", 10.8),
        _switch("📜 逐拍", 2),
        _cap("這個分頁列出每一拍 CPU 做了什麼", 7.8),
        _cap("有變動的格子會亮起來,點任一列可以「時光旅行」回到那一拍", 10.8),
        _switch("🐞 內部", 2),
        _cap("這個分頁顯示 CPU 目前的內部狀態:32 個暫存器 + 一段記憶體", 10.8),
        _cap("黃色 = 上一拍剛變動過。看著它你就能理解「每個指令到底改了什麼」", 12.4),

        # ──────────────────── 420–510s 概念 4:GPU 跟並行 ────────────────────
        _switch("⚡ 即時", 2),
        _cap("回頭來看 GPU 那一邊", 6.2),
        _cap("我們模擬的 GPU 有 8 顆「運算單元」(SM)", 9.3),
        _cap("每顆 SM 內又有 4 個「平行小組」(warp),每組 32 個 thread", 12.4),
        _cap("總共 8 × 4 × 32 = 1024 個 thread 可以同時跑", 9.3),
        _cap("這就是 GPU 比 CPU 快的祕密 — 不是單個核心強,而是核心非常多", 12.4),
        _cap("CPU 派一個工作給 GPU,叫做「KLAUNCH」 — kernel launch", 10.8),
        _cap("Kernel = 一段給 GPU 算的程式 (中文叫「核函式」)", 9.3),
        _switch("🏗️ 3D", 2),
        _cap("用 3D 視角看 8 顆 SM — 越忙的塔越高", 9.3),
        _switch("🧠 進階", 2),
        _cap("進階一點:同一組 32 個 thread 如果走不同分支,會「分歧」變慢", 12.4),
        _cap("這個分頁示範分歧 vs 不分歧的效率差距", 9.3),

        # ──────────────────── 510–600s 收尾 ────────────────────
        _switch("💻 硬體", 2),
        _cap("最後看你電腦真實的硬體 — 每顆 CPU 核心、真實顯卡的負載", 10.8),
        _cap("跟剛剛模擬出來的左邊比較,你會發現它們其實是同個概念", 10.8),
        _switch("🪞 對照", 2),
        _cap("回到對照鏡 — 你現在懂左右兩邊都代表什麼了嗎?", 10.8),
        _cap("左邊:用 1024 行 Python 寫出來的「假 GPU」", 9.3),
        _cap("右邊:你電腦真實的 CPU,用 psutil 即時取樣", 10.8),
        _cap("整個工具就是希望你「看見」抽象概念,而不只是看課本死背", 12.4),
        CinemaAction(
            CinemaActionKind.PARTICLE_BURST,
            payload={"kind": "firework"},
            duration_ms=2000,
        ),
        _cap("🎉 10 分鐘到了 — 謝謝你看完!想自己玩,隨意切分頁就好", 10.8),
        CinemaAction(CinemaActionKind.DONE, payload={}, duration_ms=0),
    )
    return CinemaScript(
        name="10-minute tutorial",
        description="10 分鐘詳細導覽 — 假設零程式基礎,逐個概念講解",
        actions=actions,
    )


# ---------------------------------------------------------------------------
# Player(純資料 + callback)
# ---------------------------------------------------------------------------
class CinemaPlayer:
    """劇本播放器:每個動作走一次 callback,呼叫端負責真正觸發 UI。

    UI 端可用 QTimer 把 :meth:`advance` 串起來,但這支類別本身沒 Qt 相依,
    讓播放邏輯能單獨測試。
    """

    def __init__(
        self,
        script: CinemaScript,
        on_action: Callable[[CinemaAction], None],
    ) -> None:
        self._script = script
        self._on_action = on_action
        self._index = 0
        self._finished = False

    @property
    def is_finished(self) -> bool:
        return self._finished

    @property
    def progress(self) -> float:
        if not self._script.actions:
            return 1.0
        return min(1.0, self._index / len(self._script.actions))

    def advance(self) -> CinemaAction | None:
        """執行下一個動作;回傳剛執行的動作,結束時回 None。"""
        if self._finished or self._index >= len(self._script.actions):
            self._finished = True
            return None
        action = self._script.actions[self._index]
        self._index += 1
        import contextlib

        with contextlib.suppress(Exception):
            # 劇本永遠不該因為 UI handler 異常就崩潰
            self._on_action(action)
        if action.kind is CinemaActionKind.DONE:
            self._finished = True
        return action

    def remaining_actions(self) -> Sequence[CinemaAction]:
        return self._script.actions[self._index :]
