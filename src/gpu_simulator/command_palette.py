"""Command Palette — Ctrl+Shift+P 喚出的 fuzzy 搜尋面板。

收一份 :class:`Command` 清單,使用者輸入文字後即時 fuzzy match 並回排序結果。
資料層(:func:`fuzzy_score` / :func:`rank_commands`)沒 Qt 相依,測試友善。

UI 端 :func:`open_palette` 在 widget 上彈一個 modal QDialog,
使用者選一個 Command 之後呼叫 ``command.run()``。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Command:
    """一個可搜尋、可執行的命令項。"""

    id: str
    title: str
    description: str
    run: Callable[[], None]
    keywords: tuple[str, ...] = field(default_factory=tuple)
    shortcut: str = ""

    def haystack(self) -> str:
        """完整可被搜尋字串 — 用來算 fuzzy score。"""
        parts = [self.title, self.description, " ".join(self.keywords), self.shortcut]
        return " ".join(filter(None, parts)).lower()


def fuzzy_score(query: str, haystack: str) -> float:
    """非常簡化的 fuzzy 分數 — 0 = 完全不 match,1.0 = 完全 prefix 命中。

    規則:
    * 全部字元(忽略大小寫)依序在 haystack 出現 → 給基礎分數;否則 0
    * 連續 match → 加分(越連續越高)
    * Query 命中靠前 → 加分(rewards 前置子字串)
    * 完整子字串命中 → 強加分
    """
    if not query:
        return 0.0
    q = query.lower().strip()
    h = haystack.lower()
    if not q:
        return 0.0
    if q in h:
        # 完整子字串命中,給很高分數;越靠前越好
        position_bonus = max(0.0, 1.0 - h.index(q) / max(1, len(h)))
        return 0.7 + 0.3 * position_bonus
    # 依序匹配每個字元
    h_idx = 0
    matched = 0
    streak = 0
    max_streak = 0
    prev_match_idx = -2
    for ch in q:
        found = h.find(ch, h_idx)
        if found == -1:
            return 0.0
        matched += 1
        if found == prev_match_idx + 1:
            streak += 1
        else:
            max_streak = max(max_streak, streak)
            streak = 1
        prev_match_idx = found
        h_idx = found + 1
    max_streak = max(max_streak, streak)
    base = matched / max(1, len(h))
    streak_bonus = max_streak / max(1, len(q))
    return min(0.65, 0.3 * base + 0.35 * streak_bonus)


def rank_commands(query: str, commands: Iterable[Command]) -> list[Command]:
    """按 fuzzy score 由高到低排;query 為空回原順序。"""
    cmds = list(commands)
    if not query.strip():
        return cmds
    scored = []
    for cmd in cmds:
        score = fuzzy_score(query, cmd.haystack())
        if score > 0:
            scored.append((score, cmd))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [cmd for _, cmd in scored]


# ---------------------------------------------------------------------------
# Qt dialog
# ---------------------------------------------------------------------------
def open_palette(parent, commands: Iterable[Command]) -> Command | None:
    """彈一個 modal palette dialog;使用者選到的 Command 會被執行且回傳。
    使用者按 ESC / 點外面 → 回 None。
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QDialog,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QVBoxLayout,
    )

    cmds = list(commands)
    dialog = QDialog(parent)
    dialog.setWindowTitle("⌨️ 命令面板")
    dialog.setModal(True)
    dialog.resize(560, 420)
    dialog.setWindowFlag(Qt.FramelessWindowHint, True)
    dialog.setStyleSheet(
        """
        QDialog {
            background: rgba(30, 30, 40, 250);
            border: 1px solid rgba(120, 180, 255, 180);
            border-radius: 12px;
        }
        QLineEdit {
            background: rgba(20, 20, 28, 220);
            color: white;
            border: 1px solid rgba(100, 100, 130, 200);
            border-radius: 6px;
            padding: 10px 12px;
            font-size: 14pt;
        }
        QListWidget {
            background: transparent;
            color: rgba(220, 220, 230, 240);
            border: none;
            font-size: 11pt;
        }
        QListWidget::item {
            padding: 8px 10px;
            border-bottom: 1px solid rgba(255,255,255,18);
        }
        QListWidget::item:selected {
            background: rgba(70, 130, 220, 200);
            color: white;
        }
        """
    )

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(14, 14, 14, 14)
    search = QLineEdit(dialog)
    search.setPlaceholderText("輸入要找的功能…")
    layout.addWidget(search)
    listbox = QListWidget(dialog)
    layout.addWidget(listbox, 1)

    selected: dict[str, Command | None] = {"cmd": None}

    def populate(query: str = "") -> None:
        listbox.clear()
        for cmd in rank_commands(query, cmds):
            text = f"{cmd.title}"
            if cmd.shortcut:
                text = f"{cmd.title}    [{cmd.shortcut}]"
            item = QListWidgetItem(text + "\n" + cmd.description)
            item.setData(Qt.UserRole, cmd.id)
            listbox.addItem(item)
        if listbox.count() > 0:
            listbox.setCurrentRow(0)

    def on_text_changed(text: str) -> None:
        populate(text)

    def accept_current() -> None:
        item = listbox.currentItem()
        if item is None:
            return
        cmd_id = item.data(Qt.UserRole)
        for cmd in cmds:
            if cmd.id == cmd_id:
                selected["cmd"] = cmd
                break
        dialog.accept()

    search.textChanged.connect(on_text_changed)
    search.returnPressed.connect(accept_current)
    listbox.itemActivated.connect(lambda _: accept_current())
    populate("")
    search.setFocus()

    import contextlib

    dialog.exec()
    cmd = selected["cmd"]
    if cmd is not None:
        with contextlib.suppress(Exception):
            cmd.run()
    return cmd
