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
