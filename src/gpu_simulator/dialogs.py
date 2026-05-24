"""集中放主視窗會用到的子對話框與卡片元件。

包含:

- :class:`WelcomeDialog` — 第一次啟動的 5 步驟中文導覽
- :class:`TrophyRoomDialog` — 已解鎖成就清單
- :class:`QuizDialog` — 5 題選擇題小考
- :class:`PresetCard` / :class:`PresetMenu` — Steam 風的範例卡片庫
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gpu_simulator.achievements import ACHIEVEMENTS, Achievement
from gpu_simulator.i18n import t
from gpu_simulator.quiz import QuizQuestion


# ===========================================================================
# Welcome dialog
# ===========================================================================
class WelcomeDialog(QDialog):
    """首次啟動時跳出的 5 步驟導覽。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("welcome.title"))
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setStyleSheet(
            """
            QDialog {
                background: rgb(24, 26, 34);
            }
            QLabel { color: rgb(220, 224, 236); }
            QLabel[role="title"] { font-size: 16px; font-weight: bold; }
            QLabel[role="step"] { font-size: 11px; padding: 4px 0; }
            QPushButton {
                background: rgb(80, 130, 200);
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgb(100, 160, 230); }
            QCheckBox { color: rgb(180, 186, 204); }
            """
        )
        self._dont_show_again_checkbox = QCheckBox(t("welcome.dont_show"))
        self._build_layout()

    def _build_layout(self) -> None:
        title = QLabel(t("welcome.title"))
        title.setProperty("role", "title")
        intro = QLabel(t("welcome.intro"))
        intro.setWordWrap(True)
        intro.setProperty("role", "step")

        steps_container = QVBoxLayout()
        steps_container.setSpacing(2)
        for step_key in (
            "welcome.step1",
            "welcome.step2",
            "welcome.step3",
            "welcome.step4",
            "welcome.step5",
        ):
            label = QLabel(t(step_key))
            label.setProperty("role", "step")
            label.setWordWrap(True)
            steps_container.addWidget(label)

        cta = QLabel(t("welcome.cta"))
        cta.setWordWrap(True)
        cta.setStyleSheet("color: rgb(180, 200, 255); font-size: 11px; padding: 6px 0;")

        ok_button = QPushButton(t("welcome.start"))
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)

        button_row = QHBoxLayout()
        button_row.addWidget(self._dont_show_again_checkbox)
        button_row.addStretch(1)
        button_row.addWidget(ok_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addLayout(steps_container)
        layout.addWidget(cta)
        layout.addLayout(button_row)

    @property
    def should_skip_next_time(self) -> bool:
        return self._dont_show_again_checkbox.isChecked()


# ===========================================================================
# Trophy room
# ===========================================================================
class TrophyRoomDialog(QDialog):
    """已解鎖成就的視覺化展示。"""

    def __init__(
        self,
        unlocked_at_by_code: dict[str, datetime],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("trophy.title"))
        self.setModal(True)
        self.setMinimumSize(460, 420)
        self.setStyleSheet(
            """
            QDialog { background: rgb(20, 22, 30); }
            QLabel  { color: rgb(220, 224, 236); }
            QLabel[role="title"] { font-size: 16px; font-weight: bold; }
            QLabel[role="subtitle"] { color: rgb(180, 186, 204); font-size: 11px; }
            QFrame[role="card"] {
                background: rgba(40, 46, 64, 220);
                border: 1px solid rgba(120, 180, 255, 90);
                border-radius: 6px;
            }
            QFrame[role="card-locked"] {
                background: rgba(28, 30, 38, 220);
                border: 1px solid rgba(80, 90, 110, 90);
                border-radius: 6px;
            }
            QPushButton {
                background: rgb(80, 130, 200);
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
            }
            """
        )

        unlocked_count = len(unlocked_at_by_code)
        title = QLabel(t("trophy.title"))
        title.setProperty("role", "title")
        subtitle = QLabel(
            t("trophy.subtitle", unlocked=unlocked_count, total=len(ACHIEVEMENTS))
        )
        subtitle.setProperty("role", "subtitle")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        grid = QGridLayout(scroll_content)
        grid.setSpacing(6)
        for index, achievement in enumerate(ACHIEVEMENTS):
            unlocked_at = unlocked_at_by_code.get(achievement.code)
            grid.addWidget(
                self._build_card(achievement, unlocked_at),
                index // 2,
                index % 2,
            )
        scroll.setWidget(scroll_content)

        close_button = QPushButton(t("btn.close"))
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(6)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(scroll, 1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    @staticmethod
    def _build_card(achievement: Achievement, unlocked_at: datetime | None) -> QFrame:
        frame = QFrame()
        frame.setProperty("role", "card" if unlocked_at else "card-locked")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        title = QLabel(("🏆 " if unlocked_at else "🔒 ") + achievement.name)
        title.setStyleSheet(
            "font-weight: bold; font-size: 11px; color: rgb(255, 220, 130);"
            if unlocked_at
            else "font-weight: bold; font-size: 11px; color: rgb(160, 168, 184);"
        )
        description = QLabel(achievement.description)
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 10px; color: rgb(200, 206, 220);")
        layout.addWidget(title)
        layout.addWidget(description)
        if unlocked_at:
            timestamp = QLabel(
                t("trophy.unlocked_at", when=unlocked_at.strftime("%Y-%m-%d %H:%M"))
            )
            timestamp.setStyleSheet("font-size: 9px; color: rgb(140, 160, 200);")
            layout.addWidget(timestamp)
        else:
            timestamp = QLabel(t("trophy.locked"))
            timestamp.setStyleSheet("font-size: 9px; color: rgb(110, 116, 132);")
            layout.addWidget(timestamp)
        return frame


# ===========================================================================
# Quiz dialog
# ===========================================================================
class QuizDialog(QDialog):
    """每次顯示一題,共 5 題,結束時顯示分數與解釋。"""

    def __init__(
        self,
        questions: Sequence[QuizQuestion],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("quiz.title"))
        self.setModal(True)
        self.setMinimumSize(480, 360)
        self.setStyleSheet(
            """
            QDialog { background: rgb(24, 26, 34); }
            QLabel  { color: rgb(220, 224, 236); }
            QLabel[role="title"]    { font-size: 14px; font-weight: bold; }
            QLabel[role="prompt"]   { font-size: 12px; padding: 8px 0; }
            QRadioButton {
                color: rgb(220, 224, 236);
                padding: 4px 0;
                font-size: 11px;
            }
            QPushButton {
                background: rgb(80, 130, 200);
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:disabled { background: rgb(60, 70, 90); color: rgb(140, 150, 170); }
            QPushButton:hover:!disabled { background: rgb(100, 160, 230); }
            """
        )
        self._questions = list(questions)
        self._current_index = 0
        self._user_choices: list[int] = []
        self._stack = QStackedWidget()

        intro_label = QLabel(t("quiz.intro"))
        intro_label.setWordWrap(True)
        intro_label.setProperty("role", "title")

        # 一頁一題,最後再加一頁顯示總成績
        self._radio_groups: list[QButtonGroup] = []
        for question in self._questions:
            self._stack.addWidget(self._build_question_page(question))
        self._result_page = self._build_result_page_placeholder()
        self._stack.addWidget(self._result_page)

        self._next_button = QPushButton(t("quiz.next"))
        self._next_button.clicked.connect(self._on_next)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.addWidget(intro_label)
        layout.addWidget(self._stack, 1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._next_button)
        layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------
    @property
    def score(self) -> int:
        score = 0
        for question, choice in zip(self._questions, self._user_choices, strict=False):
            if choice == question.correct_index:
                score += 1
        return score

    @property
    def total(self) -> int:
        return len(self._questions)

    # ------------------------------------------------------------------
    # 建頁面
    # ------------------------------------------------------------------
    def _build_question_page(self, question: QuizQuestion) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        prompt = QLabel(question.prompt)
        prompt.setWordWrap(True)
        prompt.setProperty("role", "prompt")
        layout.addWidget(prompt)
        button_group = QButtonGroup(page)
        for index, option in enumerate(question.options):
            radio = QRadioButton(option)
            button_group.addButton(radio, index)
            layout.addWidget(radio)
        layout.addStretch(1)
        self._radio_groups.append(button_group)
        return page

    def _build_result_page_placeholder(self) -> QWidget:
        page = QWidget()
        page.setLayout(QVBoxLayout())
        return page

    def _populate_result_page(self) -> None:
        page = self._result_page
        old_layout = page.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        layout = old_layout if old_layout is not None else QVBoxLayout(page)

        score_label = QLabel(t("quiz.score", score=self.score, total=self.total))
        score_label.setProperty("role", "title")
        layout.addWidget(score_label)
        review_title = QLabel(t("quiz.review_title"))
        review_title.setStyleSheet("font-weight: bold; padding-top: 8px;")
        layout.addWidget(review_title)

        for index, question in enumerate(self._questions):
            choice = self._user_choices[index] if index < len(self._user_choices) else -1
            is_correct = choice == question.correct_index
            mark = "✅" if is_correct else "❌"
            choice_text = (
                question.options[choice] if 0 <= choice < len(question.options) else "—"
            )
            correct_text = question.options[question.correct_index]
            review = QLabel(
                f"{mark} {question.prompt}\n"
                f"   你選:{choice_text}\n"
                f"   正確:{correct_text}\n"
                f"   說明:{question.explanation}"
            )
            review.setWordWrap(True)
            review.setStyleSheet("color: rgb(200, 206, 220); font-size: 10px; padding: 4px 0;")
            layout.addWidget(review)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    # 互動
    # ------------------------------------------------------------------
    def _on_next(self) -> None:
        is_question_page = self._current_index < len(self._questions)
        if is_question_page:
            group = self._radio_groups[self._current_index]
            self._user_choices.append(group.checkedId())
            self._current_index += 1
            if self._current_index >= len(self._questions):
                self._populate_result_page()
                self._stack.setCurrentWidget(self._result_page)
                self._next_button.setText(t("btn.close"))
            else:
                self._stack.setCurrentIndex(self._current_index)
                if self._current_index == len(self._questions) - 1:
                    self._next_button.setText(t("quiz.finish"))
        else:
            self.accept()


# ===========================================================================
# Preset menu (Steam-style cards)
# ===========================================================================
@dataclass(frozen=True)
class PresetEntry:
    asm_filename: str
    name_key: str
    description_key: str
    stars_key: str


# 內建範例對應到 examples/<filename>
BUILT_IN_PRESETS: tuple[PresetEntry, ...] = (
    PresetEntry("hello_gpu.asm", "preset.hello.name", "preset.hello.desc", "preset.hello.stars"),
    PresetEntry("burst_and_count.asm", "preset.burst.name", "preset.burst.desc", "preset.burst.stars"),
    PresetEntry("loop_kernel.asm", "preset.loop.name", "preset.loop.desc", "preset.loop.stars"),
    PresetEntry("memory_copy.asm", "preset.memory_copy.name", "preset.memory_copy.desc", "preset.memory_copy.stars"),
    PresetEntry("sort_three.asm", "preset.sort_three.name", "preset.sort_three.desc", "preset.sort_three.stars"),
    PresetEntry("find_max.asm", "preset.find_max.name", "preset.find_max.desc", "preset.find_max.stars"),
    PresetEntry("counter.asm", "preset.counter.name", "preset.counter.desc", "preset.counter.stars"),
    PresetEntry("mixed_burst.asm", "preset.mixed_burst.name", "preset.mixed_burst.desc", "preset.mixed_burst.stars"),
)


class PresetCard(QFrame):
    """單張範例卡片 — 點 `▶ 執行` 直接跑、點 `📝 編輯器` 只載入。"""

    run_requested = Signal(str)   # raw asm source
    load_requested = Signal(str)  # raw asm source

    def __init__(
        self,
        entry: PresetEntry,
        examples_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entry = entry
        self._examples_dir = Path(examples_dir)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            """
            QFrame {
                background: rgba(40, 46, 64, 220);
                border: 1px solid rgba(120, 180, 255, 100);
                border-radius: 6px;
            }
            QLabel { color: rgb(220, 224, 236); }
            QLabel[role="card-title"] { font-weight: bold; font-size: 12px; }
            QLabel[role="card-stars"] { color: rgb(255, 200, 100); font-size: 11px; }
            QLabel[role="card-desc"] {
                color: rgb(190, 200, 220);
                font-size: 10px;
            }
            QPushButton {
                background: rgba(80, 130, 200, 230);
                color: white;
                border: none;
                padding: 4px 10px;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(100, 160, 230, 255); }
            QPushButton[role="ghost"] {
                background: transparent;
                color: rgb(180, 200, 230);
                border: 1px solid rgba(120, 180, 255, 120);
                font-weight: normal;
            }
            QPushButton[role="ghost"]:hover {
                background: rgba(120, 180, 255, 40);
            }
            """
        )
        title = QLabel(t(entry.name_key))
        title.setProperty("role", "card-title")
        stars = QLabel(t(entry.stars_key))
        stars.setProperty("role", "card-stars")
        description = QLabel(t(entry.description_key))
        description.setProperty("role", "card-desc")
        description.setWordWrap(True)

        run_button = QPushButton(t("btn.run"))
        run_button.clicked.connect(self._emit_run)
        load_button = QPushButton(t("btn.load_example"))
        load_button.setProperty("role", "ghost")
        load_button.clicked.connect(self._emit_load)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addWidget(title, 1)
        title_row.addWidget(stars, 0)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(4)
        button_row.addWidget(run_button)
        button_row.addWidget(load_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        layout.addLayout(title_row)
        layout.addWidget(description)
        layout.addLayout(button_row)

    def _read_source(self) -> str | None:
        path = self._examples_dir / self._entry.asm_filename
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def _emit_run(self) -> None:
        source = self._read_source()
        if source is not None:
            self.run_requested.emit(source)

    def _emit_load(self) -> None:
        source = self._read_source()
        if source is not None:
            self.load_requested.emit(source)


class PresetMenu(QWidget):
    """範例卡片庫(Input 分頁頂部)。"""

    run_requested = Signal(str)
    load_requested = Signal(str)

    def __init__(
        self,
        examples_dir: Path | str,
        entries: Sequence[PresetEntry] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._examples_dir = Path(examples_dir)
        entries = list(entries or BUILT_IN_PRESETS)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        grid = QVBoxLayout(content)
        grid.setSpacing(6)
        for entry in entries:
            card = PresetCard(entry, self._examples_dir, content)
            card.run_requested.connect(self.run_requested.emit)
            card.load_requested.connect(self.load_requested.emit)
            grid.addWidget(card)
        grid.addStretch(1)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll, 1)


# ===========================================================================
# Achievement popup (small toast-style modal-less notification)
# ===========================================================================
class AchievementToast(QDialog):
    """成就解鎖時跳出來的小通知,點任意處關閉。"""

    def __init__(
        self,
        achievement: Achievement,
        parent: QWidget | None = None,
        auto_close_ms: int = 2200,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("trophy.popup_title"))
        self.setModal(False)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(
            """
            QDialog { background: transparent; }
            QFrame {
                background: rgba(255, 200, 90, 240);
                border-radius: 8px;
            }
            QLabel { color: rgb(40, 30, 0); }
            QLabel[role="title"] { font-size: 14px; font-weight: bold; }
            QLabel[role="body"] { font-size: 11px; }
            """
        )
        frame = QFrame(self)
        title = QLabel(t("trophy.popup_title"))
        title.setProperty("role", "title")
        body = QLabel(t("trophy.popup_body", name=achievement.name, desc=achievement.description))
        body.setProperty("role", "body")
        body.setWordWrap(True)
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.addWidget(title)
        inner.addWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        self.adjustSize()

        from PySide6.QtCore import QTimer

        QTimer.singleShot(auto_close_ms, self.accept)


# ===========================================================================
# 給爸媽看的「教學秀」
# ===========================================================================
class DemoTab(QWidget):
    """easy 模式下使用的自動播放分頁。

    UI 上只放兩個元件:當下播放中的範例名稱、倒數秒數;
    後端切換邏輯由主 widget 控制(用 QTimer 在固定間隔換 program)。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        title = QLabel(t("demo.title"))
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: rgb(255, 220, 130); padding: 8px 0;"
        )
        subtitle = QLabel(t("demo.subtitle"))
        subtitle.setStyleSheet("color: rgb(220, 224, 236); font-size: 13px;")
        subtitle.setWordWrap(True)
        self._now_playing_label = QLabel(t("demo.now_playing", name="—"))
        self._now_playing_label.setStyleSheet(
            "color: rgb(120, 220, 140); font-size: 14px; padding-top: 12px;"
        )
        self._countdown_label = QLabel(t("demo.next_in", seconds=30))
        self._countdown_label.setStyleSheet("color: rgb(180, 200, 230); font-size: 12px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._now_playing_label)
        layout.addWidget(self._countdown_label)
        layout.addStretch(1)

    def update_state(self, *, current_name: str, seconds_remaining: int) -> None:
        self._now_playing_label.setText(t("demo.now_playing", name=current_name))
        self._countdown_label.setText(t("demo.next_in", seconds=max(0, seconds_remaining)))


# ===========================================================================
# Helpers
# ===========================================================================
def make_help_button(tooltip_key: str, on_click: Callable[[], None]) -> QPushButton:
    button = QPushButton("?")
    button.setFixedSize(20, 20)
    button.setToolTip(t(tooltip_key))
    button.setStyleSheet(
        """
        QPushButton {
            background: rgba(120, 180, 255, 200);
            color: white;
            border: none;
            border-radius: 10px;
            font-weight: bold;
        }
        QPushButton:hover { background: rgba(150, 200, 255, 240); }
        """
    )
    button.clicked.connect(on_click)
    return button


# ===========================================================================
# Guided lesson dialog — 5 中文課
# ===========================================================================
class GuidedLessonDialog(QDialog):
    """5 課中文導覽,左側課程清單,右側內容 + 載入/直接執行按鈕。"""

    lesson_selected = Signal(str, bool)  # (annotated_asm_source, use_full_tiny8)

    def __init__(self, lessons, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lessons = list(lessons)
        self.setWindowTitle("🎓 教學課程")
        self.setModal(True)
        self.setMinimumSize(640, 460)
        self.setStyleSheet(
            """
            QDialog { background: rgb(20, 22, 30); }
            QLabel  { color: rgb(220, 224, 236); }
            QListWidget {
                background: rgba(28, 30, 38, 220);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(120, 180, 255, 90);
                border-radius: 6px;
                font-size: 11px;
            }
            QListWidget::item { padding: 6px 8px; }
            QListWidget::item:selected { background: rgba(120, 180, 255, 130); }
            QPushButton {
                background: rgb(80, 130, 200);
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgb(100, 160, 230); }
            QPushButton[role="ghost"] {
                background: transparent;
                color: rgb(180, 200, 230);
                border: 1px solid rgba(120, 180, 255, 120);
                font-weight: normal;
            }
            QPushButton[role="ghost"]:hover { background: rgba(120, 180, 255, 40); }
            """
        )

        self._list_widget = QListWidget()
        for lesson in self._lessons:
            self._list_widget.addItem(QListWidgetItem(lesson.title))
        self._list_widget.currentRowChanged.connect(self._on_row_changed)

        self._title_label = QLabel("")
        self._title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._title_label.setWordWrap(True)
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet("color: rgb(200, 206, 220); font-size: 11px;")
        self._bullets_label = QLabel("")
        self._bullets_label.setWordWrap(True)
        self._bullets_label.setStyleSheet(
            "color: rgb(255, 220, 130); font-size: 11px; padding-top: 6px;"
        )

        self._load_button = QPushButton("📥 載入到 ASM 編輯器")
        self._run_button = QPushButton("▶ 直接執行這課")
        self._close_button = QPushButton("關閉")
        self._close_button.setProperty("role", "ghost")

        self._load_button.clicked.connect(lambda: self._emit_selection(run=False))
        self._run_button.clicked.connect(lambda: self._emit_selection(run=True))
        self._close_button.clicked.connect(self.accept)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(6)
        right_layout.addWidget(self._title_label)
        right_layout.addWidget(self._summary_label)
        right_layout.addWidget(self._bullets_label, 1)
        button_row = QHBoxLayout()
        button_row.addWidget(self._load_button)
        button_row.addWidget(self._run_button)
        button_row.addStretch(1)
        button_row.addWidget(self._close_button)
        right_layout.addLayout(button_row)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        outer.addWidget(self._list_widget, 2)
        outer.addWidget(right_panel, 5)

        if self._lessons:
            self._list_widget.setCurrentRow(0)

    def _on_row_changed(self, row: int) -> None:
        if not 0 <= row < len(self._lessons):
            return
        lesson = self._lessons[row]
        self._title_label.setText(lesson.title)
        self._summary_label.setText(lesson.summary)
        bullets_text = "🔍 重點觀察:\n" + "\n".join(f"  • {bullet}" for bullet in lesson.bullets)
        self._bullets_label.setText(bullets_text)

    def _emit_selection(self, *, run: bool) -> None:
        row = self._list_widget.currentRow()
        if not 0 <= row < len(self._lessons):
            return
        lesson = self._lessons[row]
        marker = "RUN" if run else "LOAD"
        annotated_source = f"{marker}\n{lesson.asm_source}"
        self.lesson_selected.emit(annotated_source, lesson.use_full_tiny8)
        self.accept()


# ===========================================================================
# 第九輪 #6 · AI 解釋器對話框
# ===========================================================================
class AIExplainerDialog(QDialog):
    """顯示 :class:`Explainer` 給的中文解說。"""

    def __init__(self, body_text: str, used_ai: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🤖 AI 解釋這支程式")
        self.setModal(True)
        self.setMinimumSize(640, 460)
        self.setStyleSheet(
            """
            QDialog { background: rgb(20, 22, 30); }
            QLabel  { color: rgb(220, 224, 236); }
            QPlainTextEdit {
                background: rgba(15, 17, 24, 240);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(120, 180, 255, 90);
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton {
                background: rgb(80, 130, 200);
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgb(100, 160, 230); }
            """
        )
        from PySide6.QtWidgets import QPlainTextEdit

        title = QLabel(
            "🤖 AI 解釋(使用 Claude API)" if used_ai else "📝 離線解說(規則式)"
        )
        title.setStyleSheet(
            "font-size: 14px; font-weight: bold; "
            f"color: {'rgb(120, 220, 140)' if used_ai else 'rgb(255, 200, 100)'};"
        )
        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setPlainText(body_text)
        close_button = QPushButton("關閉")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(body, 1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)


# ===========================================================================
# 第九輪 #5 · 每日挑戰對話框 + leaderboard
# ===========================================================================
class ChallengeDialog(QDialog):
    """顯示今日挑戰、最近排行榜,以及挑戰結果(若使用者剛跑完)。"""

    submit_score_requested = Signal(str)  # nickname

    def __init__(
        self,
        challenge,
        latest_result=None,
        leaderboard=(),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("🏁 每日挑戰")
        self.setModal(True)
        self.setMinimumSize(580, 420)
        self.setStyleSheet(
            """
            QDialog { background: rgb(20, 22, 30); }
            QLabel  { color: rgb(220, 224, 236); }
            QListWidget {
                background: rgba(28, 30, 38, 220);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(120, 180, 255, 90);
                border-radius: 6px;
                font-size: 11px;
            }
            QListWidget::item { padding: 4px 8px; }
            QPushButton {
                background: rgb(80, 130, 200);
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgb(100, 160, 230); }
            QLineEdit {
                background: rgba(28, 30, 38, 220);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(120, 180, 255, 90);
                border-radius: 4px;
                padding: 4px 8px;
            }
            """
        )
        from PySide6.QtWidgets import QLineEdit

        title = QLabel(challenge.title)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: rgb(255, 220, 130);")
        title.setWordWrap(True)
        description = QLabel(challenge.description)
        description.setWordWrap(True)
        description.setStyleSheet("color: rgb(200, 206, 220); font-size: 11px;")
        code_label = QLabel(f"挑戰代號:{challenge.code}")
        code_label.setStyleSheet("color: rgb(150, 156, 176); font-size: 10px;")

        result_label = QLabel("(尚未提交分數)")
        if latest_result is not None:
            tag = "✅ 通過" if latest_result.passed else "❌ 未通過"
            result_label.setText(
                f"{tag}  ·  cycles={latest_result.cycles_used}  ·  "
                f"score={latest_result.score}  ·  {latest_result.detail}"
            )
            result_label.setStyleSheet(
                "color: rgb(120, 220, 140); font-size: 11px;"
                if latest_result.passed
                else "color: rgb(255, 130, 130); font-size: 11px;"
            )

        leaderboard_widget = QListWidget()
        if leaderboard:
            for index, entry in enumerate(leaderboard, start=1):
                leaderboard_widget.addItem(
                    QListWidgetItem(
                        f"{index:>2}.  {entry.nickname:>12}  "
                        f"score={entry.score:>3}  cycles={entry.cycles_used:>3}"
                    )
                )
        else:
            leaderboard_widget.addItem(QListWidgetItem("(目前還沒有人提交分數)"))

        nickname_label = QLabel("你的暱稱:")
        self._nickname_field = QLineEdit("玩家")
        submit_button = QPushButton("📤 提交分數到排行榜")
        submit_button.clicked.connect(
            lambda: self.submit_score_requested.emit(self._nickname_field.text() or "玩家")
        )
        if latest_result is None or not latest_result.passed:
            submit_button.setEnabled(False)
            submit_button.setToolTip("先在 widget 跑一次能通過挑戰的 ASM,再回來提交分數")
        close_button = QPushButton("關閉")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(6)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(code_label)
        layout.addWidget(result_label)
        layout.addWidget(QLabel("🏆 今日排行榜:"))
        layout.addWidget(leaderboard_widget, 1)
        submit_row = QHBoxLayout()
        submit_row.addWidget(nickname_label)
        submit_row.addWidget(self._nickname_field, 1)
        submit_row.addWidget(submit_button)
        submit_row.addWidget(close_button)
        layout.addLayout(submit_row)


# Avoid unused-imports complaints from optional pieces ----------------------
_ = QFont  # font is used implicitly via stylesheet; keep import for static tools
