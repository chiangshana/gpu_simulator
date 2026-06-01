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
    """10 分鐘詳細導覽 — 假設觀眾無程式背景,逐個介紹 CPU / GPU / 暫存器 / 程式
    執行流程等概念,並搭配各分頁實際示範。

    結構(總時長約 600 秒):
    *   0– 60s  開場與工具介紹
    *  60–180s  概念 1:CPU 與 GPU 的差異
    * 180–300s  概念 2:CPU 內部結構(暫存器與 SREG)
    * 300–420s  概念 3:程式如何執行(指令、cycle)
    * 420–510s  概念 4:GPU 平行運算的原理
    * 510–600s  收尾,回到對照鏡再做一次整合
    """
    actions = (
        # ──────────────────── 0–60s 開場 ────────────────────
        _cap("歡迎使用 GPU 模擬器。接下來 10 分鐘帶你看懂這個工具", 7.8),
        _cap("不需要程式背景,我們會從最基本的計算機架構概念開始介紹", 7.8),
        _cap("本工具的目標是把抽象的 CPU/GPU 運作機制視覺化", 9.3),
        _cap("會介紹四個核心概念:CPU、GPU、暫存器、程式執行流程", 10.8),
        _cap("每個概念都對應一個分頁,看完即能理解現代電腦的運算原理", 10.8),
        _cap("準備好了?開始", 6.2),

        # ──────────────────── 60–180s 概念 1:CPU vs GPU ────────────────────
        _switch("🪞 對照", 2),
        _cap("這是「對照鏡」分頁,左右兩側分別代表兩個獨立的世界", 9.3),
        _cap("左側:本專案以 Python 模擬出來的虛擬 GPU(用於教學)", 9.3),
        _cap("右側:你這台機器真實的 CPU 核心使用率(由 psutil 取樣)", 9.3),
        _cap("CPU(Central Processing Unit)是電腦的中央處理單元", 9.3),
        _cap("GPU(Graphics Processing Unit)是顯示卡,擅長大量平行運算", 10.8),
        _cap("差異:CPU 一般 4–24 核,每核功能完整、可處理任意工作", 10.8),
        _cap("GPU 有數千核心,單核功能較簡單,但「同時做同一件事」的能力極強", 10.8),
        _cap("接下來會派發 kernel 給左側模擬 GPU,觀察反應", 9.3),
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
        _cap("左側 SM 使用率上升,右側真實 CPU 幾乎沒變動", 10.8),
        _cap("這就是本專題的核心論述:模擬端與真實端是兩個獨立世界,可並排比對", 12.4),

        # ──────────────────── 180–300s 概念 2:CPU 內部 ────────────────────
        _switch("🌡️ 變化", 2),
        _cap("現在來看 CPU 內部結構", 7.8),
        _cap("CPU 計算時的中間值存放在何處?答案是「暫存器」(register)", 9.3),
        _cap("暫存器是 CPU 內最快的儲存單元,Tiny8 共有 32 個(R0–R31),每個 8 bit", 10.8),
        _cap("數量少是因為它們必須位於計算單元旁邊,空間與電晶體成本都高", 12.4),
        _cap("除暫存器外,CPU 也有「記憶體」(RAM):容量大但存取速度較慢", 10.8),
        _cap("還有「狀態旗標」(SREG):8 個 bit,記錄上一個運算的結果屬性(零、進位、溢位等)", 12.4),
        _cap("這個分頁的三層 heatmap 即是這三類狀態隨時間的視覺化", 9.3),
        _cap("接下來按「執行並繪製」執行一段範例程式,觀察各值的變化", 9.3),
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
        _cap("暫存器格的顏色由深(0)逐漸變亮(高值),每個 cycle 都被記錄下來", 12.4),
        _cap("這就是「程式執行時 CPU 內部狀態」的具體視覺化", 9.3),
        _cap("拖動下方的時間軸,可定位至任一 cycle 並查看當時所有暫存器的精確值", 10.8),

        # ──────────────────── 300–420s 概念 3:程式怎麼執行 ────────────────────
        _switch("⌨️ 寫程式", 2),
        _cap("剛才執行的是「組合語言」(ASM),屬於最低階、最接近機器的程式語言", 10.8),
        _cap("一行原始碼對應一個指令,CPU 一次處理一個指令", 9.3),
        _cap("例如 ldi r16, 5 表示將數值 5 載入 R16 暫存器", 9.3),
        _cap("add r16, r17 表示將 R16 與 R17 相加,結果寫回 R16", 10.8),
        _cap("CPU 處理完一個指令稱為走完一個 cycle(時脈週期)", 9.3),
        _cap("現代 CPU 每秒可執行數十億個 cycle,這就是電腦運算速度的來源", 10.8),
        _switch("📜 逐拍", 2),
        _cap("這個分頁完整列出每個 cycle CPU 執行的內容", 7.8),
        _cap("有變動的欄位會高亮;點任一列可回溯至該 cycle 的完整狀態", 10.8),
        _switch("🐞 內部", 2),
        _cap("這個分頁呈現 CPU 當前內部狀態:32 個通用暫存器 + 一段記憶體區段", 10.8),
        _cap("黃色代表上一個 cycle 剛變動的欄位,可用來追蹤每個指令的實際效果", 12.4),

        # ──────────────────── 420–510s 概念 4:GPU 與平行運算 ────────────────────
        _switch("⚡ 即時", 2),
        _cap("接下來看 GPU 端", 6.2),
        _cap("本專案模擬的 GPU 包含 8 個 Streaming Multiprocessor(SM)", 9.3),
        _cap("每個 SM 內有 4 條 warp,每條 warp 包含 32 個 thread", 12.4),
        _cap("總共 8 × 4 × 32 = 1024 個 thread 可同時執行", 9.3),
        _cap("GPU 的速度優勢來自大規模平行運算,而非單核效能", 12.4),
        _cap("CPU 派發工作給 GPU 的動作稱為 KLAUNCH(kernel launch)", 10.8),
        _cap("Kernel 是一段在 GPU 上執行的函式,中文常譯為「核函式」", 9.3),
        _switch("🏗️ 3D", 2),
        _cap("以 3D 等距視角呈現 8 個 SM,塔高對應其當前使用率", 9.3),
        _switch("🧠 進階", 2),
        _cap("進階概念:同一條 warp 內的 32 個 thread 若走入不同分支,稱為「分歧」會導致效能下降", 12.4),
        _cap("這個分頁示範分歧情境與非分歧情境的執行效率差異", 9.3),

        # ──────────────────── 510–600s 收尾 ────────────────────
        _switch("💻 硬體", 2),
        _cap("最後看本機真實硬體狀態:各 CPU 邏輯核心與顯卡的即時負載", 10.8),
        _cap("與左側模擬端比較,可看出兩者其實是相同概念的兩個尺度", 10.8),
        _switch("🪞 對照", 2),
        _cap("回到對照鏡 — 你現在應該能說出左右兩側各自代表什麼了", 10.8),
        _cap("左側:本專案以 Python 實作的模擬 GPU(教學用)", 9.3),
        _cap("右側:本機真實 CPU 的各核心使用率(由 psutil 取樣)", 10.8),
        _cap("本工具的目標是讓抽象的計算機架構概念變得可觀察、可操作", 12.4),
        CinemaAction(
            CinemaActionKind.PARTICLE_BURST,
            payload={"kind": "firework"},
            duration_ms=2000,
        ),
        _cap("10 分鐘導覽結束,謝謝觀看。接下來可自由切換分頁探索其他功能", 10.8),
        CinemaAction(CinemaActionKind.DONE, payload={}, duration_ms=0),
    )
    return CinemaScript(
        name="10-minute tutorial",
        description="10 分鐘詳細導覽 — 適合零程式背景觀眾,逐個介紹計算機架構核心概念",
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
