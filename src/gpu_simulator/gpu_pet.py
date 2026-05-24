"""GPU 寵物表情元件 + 進化系統。

第十一輪升級:寵物有五個進化階段,跟使用者解鎖的成就數量綁定 —
這隻寵物**隨著使用變強**,提供回頭再玩一次的動機。

階段:
    🥚 蛋(0 成就)
    🐣 雛鳥(1–2)
    🐤 小鳥(3–5)
    🦅 老鷹(6–8)
    🐲 龍(9+)

每個階段都有自己的表情梯:在當前進化階段內,根據 GPU 利用率挑表情。

第十二輪加碼:
    • 寵物可以命名 — :meth:`GPUPetWidget.set_name` / :func:`suggest_random_name`。
    • 閒置動畫 — 沒互動時每 ~6 秒會偷偷眨個眼/抖動一下,讓桌面看起來有靈魂。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gpu_simulator.i18n import t


@dataclass(frozen=True)
class PetMood:
    emoji: str
    chinese_message_key: str
    upper_bound: float  # 嚴格小於這個利用率時用此心情(0..1)


@dataclass(frozen=True)
class PetStage:
    """寵物的一個進化階段。

    每個階段有自己的 5 階表情(對應 0/低/中/高/超高 利用率),
    跟自己的中文小名(例如「雛鳥」)。
    """

    code: str
    name_zh: str
    min_achievements: int
    moods: tuple[PetMood, ...]


# ---------------------------------------------------------------------------
# 五個階段的表情梯
# ---------------------------------------------------------------------------
STAGE_EGG = PetStage(
    code="egg",
    name_zh="蛋",
    min_achievements=0,
    moods=(
        PetMood("🥚", "pet.bored", 0.05),
        PetMood("🥚", "pet.warming", 0.30),
        PetMood("🥚", "pet.busy", 0.65),
        PetMood("🥚", "pet.sweating", 0.90),
        PetMood("🥚", "pet.melting", 1.01),
    ),
)

STAGE_HATCHLING = PetStage(
    code="hatchling",
    name_zh="雛鳥",
    min_achievements=1,
    moods=(
        PetMood("🐣", "pet.bored", 0.05),
        PetMood("🐣", "pet.warming", 0.30),
        PetMood("🐥", "pet.busy", 0.65),
        PetMood("🐥", "pet.sweating", 0.90),
        PetMood("🐥", "pet.melting", 1.01),
    ),
)

STAGE_BIRD = PetStage(
    code="bird",
    name_zh="小鳥",
    min_achievements=3,
    moods=(
        PetMood("🐤", "pet.bored", 0.05),
        PetMood("🐦", "pet.warming", 0.30),
        PetMood("🦆", "pet.busy", 0.65),
        PetMood("🦜", "pet.sweating", 0.90),
        PetMood("🦜", "pet.melting", 1.01),
    ),
)

STAGE_EAGLE = PetStage(
    code="eagle",
    name_zh="老鷹",
    min_achievements=6,
    moods=(
        PetMood("🦅", "pet.bored", 0.05),
        PetMood("🦅", "pet.warming", 0.30),
        PetMood("🦅", "pet.busy", 0.65),
        PetMood("🦉", "pet.sweating", 0.90),
        PetMood("🦉", "pet.melting", 1.01),
    ),
)

STAGE_DRAGON = PetStage(
    code="dragon",
    name_zh="龍",
    min_achievements=9,
    moods=(
        PetMood("🐲", "pet.bored", 0.05),
        PetMood("🐉", "pet.warming", 0.30),
        PetMood("🐉", "pet.busy", 0.65),
        PetMood("🔥", "pet.sweating", 0.90),
        PetMood("🐲", "pet.melting", 1.01),
    ),
)

ALL_STAGES: tuple[PetStage, ...] = (
    STAGE_EGG, STAGE_HATCHLING, STAGE_BIRD, STAGE_EAGLE, STAGE_DRAGON,
)


# ---------------------------------------------------------------------------
# 純資料層:挑階段、挑表情
# ---------------------------------------------------------------------------
def stage_for_achievement_count(count: int) -> PetStage:
    """以解鎖成就數選對應的進化階段。"""
    chosen = ALL_STAGES[0]
    for stage in ALL_STAGES:
        if count >= stage.min_achievements:
            chosen = stage
    return chosen


def mood_for_utilization(utilization: float, stage: PetStage | None = None) -> PetMood:
    """以利用率 + 當前進化階段挑表情。"""
    stage = stage or STAGE_EGG
    for mood in stage.moods:
        if utilization < mood.upper_bound:
            return mood
    return stage.moods[-1]


# 內建的可愛中文小名,使用者沒命名時隨機挑一個 — 不需要 Qt。
_DEFAULT_PET_NAMES: tuple[str, ...] = (
    "小皮", "炎炎", "豆豆", "饅頭", "閃電",
    "麻糬", "波奇", "胖虎", "阿熊", "湯圓",
    "電電", "晶晶", "三角", "草莓",
)


def suggest_random_name(seed: int | None = None) -> str:
    """選一個內建小名;沒給 seed 用系統隨機。"""
    import random

    rng = random.Random(seed) if seed is not None else random.Random()
    return rng.choice(_DEFAULT_PET_NAMES)


def is_valid_pet_name(name: str) -> bool:
    """寵物名規則 — 1..12 字、不全空白。"""
    if not isinstance(name, str):
        return False
    stripped = name.strip()
    return 1 <= len(stripped) <= 12


# ---------------------------------------------------------------------------
# Qt widget
# ---------------------------------------------------------------------------
class GPUPetWidget(QWidget):
    """常駐桌面 widget 頂部的寵物表情 + 中文小語 + 進化階段標籤。

    新增 :meth:`celebrate` — 解鎖成就時呼叫,寵物會跳一下(geometry 動畫)。
    """

    def __init__(self, parent: QWidget | None = None, *, name: str = "") -> None:
        super().__init__(parent)
        self._stage: PetStage = STAGE_EGG
        self._name: str = name or suggest_random_name()
        self._face_label = QLabel("🥚")
        self._face_label.setStyleSheet("font-size: 24px;")
        self._face_label.setAlignment(Qt.AlignCenter)
        self._face_label.setMinimumWidth(48)
        self._stage_label = QLabel(f"🥚 {self._name}(蛋)")
        self._stage_label.setStyleSheet(
            "color: rgba(255, 220, 130, 230); font-size: 9px;"
        )
        self._message_label = QLabel(t("pet.bored"))
        self._message_label.setStyleSheet(
            "color: rgba(220, 224, 236, 230); font-size: 10px;"
        )
        self._message_label.setWordWrap(True)

        from PySide6.QtWidgets import QVBoxLayout

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(0)
        text_column.addWidget(self._stage_label)
        text_column.addWidget(self._message_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(self._face_label, 0)
        layout.addLayout(text_column, 1)

        # 進化轉場 / 解鎖跳動的動畫器,延遲建立
        self._celebrate_timer = QTimer(self)
        self._celebrate_timer.setInterval(80)
        self._celebrate_timer.timeout.connect(self._wiggle_step)
        self._wiggle_remaining = 0
        self._wiggle_base_size = 24

        # 閒置動畫 — 每 ~6 秒偷偷眨眼,讓寵物看起來活著
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(6000)
        self._idle_timer.timeout.connect(self._idle_tick)
        self._idle_timer.start()
        self._idle_blinking = False

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------
    def update_from_snapshot(self, snapshot: dict) -> None:
        utilization = float(snapshot.get("overall_utilization", 0.0))
        mood = mood_for_utilization(utilization, self._stage)
        self._face_label.setText(mood.emoji)
        self._message_label.setText(t(mood.chinese_message_key))

    def set_achievement_count(self, count: int) -> None:
        """更新解鎖成就數;若跨越進化門檻則切換階段並 wiggle。"""
        new_stage = stage_for_achievement_count(count)
        if new_stage.code != self._stage.code:
            self._stage = new_stage
            self._refresh_stage_label()
            self.celebrate()

    def set_name(self, name: str) -> None:
        """改寵物名;空字串或太長字串會被忽略(回傳前自動 strip)。"""
        if not is_valid_pet_name(name):
            return
        self._name = name.strip()
        self._refresh_stage_label()

    @property
    def pet_name(self) -> str:
        return self._name

    def _refresh_stage_label(self) -> None:
        self._stage_label.setText(
            f"{self._stage.moods[0].emoji} {self._name}({self._stage.name_zh})"
        )

    def celebrate(self) -> None:
        """解鎖成就時跳幾下。"""
        self._wiggle_remaining = 6
        self._celebrate_timer.start()

    # ------------------------------------------------------------------
    # 內部:wiggle 動畫
    # ------------------------------------------------------------------
    def _wiggle_step(self) -> None:
        if self._wiggle_remaining <= 0:
            self._celebrate_timer.stop()
            self._face_label.setStyleSheet(f"font-size: {self._wiggle_base_size}px;")
            return
        # 在 +6px 跟 +0px 之間切換,模擬上下跳
        big = self._wiggle_remaining % 2 == 0
        size = self._wiggle_base_size + (6 if big else 0)
        self._face_label.setStyleSheet(f"font-size: {size}px;")
        self._wiggle_remaining -= 1

    # ------------------------------------------------------------------
    # 內部:idle 眨眼
    # ------------------------------------------------------------------
    def _idle_tick(self) -> None:
        """每幾秒一次的閒置動畫 — 顯示一個眨眼 emoji 130ms 再切回原表情。"""
        if self._idle_blinking or self._celebrate_timer.isActive():
            return
        original_text = self._face_label.text()
        # 用 😉 / 💤 / 當前表情 三選一,蛋階段直接微縮放感受不到所以略過 emoji 變化
        blink_emoji = "😉" if self._stage.code != "egg" else "💤"
        self._idle_blinking = True
        self._face_label.setText(blink_emoji)

        def restore():
            self._face_label.setText(original_text)
            self._idle_blinking = False

        QTimer.singleShot(180, restore)


# 向下相容:既有 visualizer.py / tests 可能 import 這個常數
# (改成函式 wrapper,避免讓 mood 在沒指定 stage 時失準)
def _legacy_mood_for_utilization(utilization: float) -> PetMood:
    """legacy helper — 沒指定 stage 時回 egg 階段的表情。"""
    return mood_for_utilization(utilization, STAGE_EGG)


_ = QPropertyAnimation  # 預留給未來更複雜的動畫
