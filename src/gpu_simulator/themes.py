"""主題系統 — 一鍵切換 widget 整體配色 / 字體。

提供 4 種 builtin 主題:

- ``classic`` — 預設,深藍灰底
- ``cyberpunk`` — 紫粉霓虹
- ``matrix`` — 黑底綠字 The Matrix 風
- ``retro_dos`` — 黑底琥珀色,80 年代終端機感

每個 :class:`Theme` 提供:

- ``stylesheet``  — 整個 widget 的 QSS
- ``palette``     — 給程式內 (QPainter) 取用的色票字典
- ``description`` — 一句中文說明

UI 端用 :func:`apply_theme` 就好;沒指定時 fallback 到 ``classic``。
不依賴 Qt 物件本體,只組裝字串,可單獨 unit test。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    code: str
    name: str
    description: str
    palette: dict[str, str]
    stylesheet: str


# ---------------------------------------------------------------------------
# 4 個 builtin 主題
# ---------------------------------------------------------------------------
def _classic() -> Theme:
    return Theme(
        code="classic",
        name="Classic 經典深藍",
        description="預設深藍灰底,平易近人",
        palette={
            "bg": "#181a22",
            "fg": "#dadfe8",
            "accent": "#5a82c8",
            "warn": "#ffb060",
            "error": "#ff8080",
        },
        stylesheet="""
            QWidget { background: #181a22; color: #dadfe8; }
            QPushButton { background: #3c4258; color: #dadfe8;
                          border: 1px solid #6080d0; border-radius: 4px;
                          padding: 4px 10px; }
            QPushButton:hover { background: #5878a8; }
            QTabBar::tab { background: #2a2e40; color: #c8d0e0;
                           padding: 4px 10px; }
            QTabBar::tab:selected { background: #5a82c8; color: white; }
        """,
    )


def _cyberpunk() -> Theme:
    return Theme(
        code="cyberpunk",
        name="Cyberpunk 賽博龐克",
        description="紫粉霓虹,適合 demo 影片配 chiptune 音樂",
        palette={
            "bg": "#1a0e2c",
            "fg": "#f5b8ff",
            "accent": "#ff36c8",
            "warn": "#ffd24a",
            "error": "#ff5577",
        },
        stylesheet="""
            QWidget { background: #1a0e2c; color: #f5b8ff;
                      font-family: 'Consolas', 'Courier New', monospace; }
            QPushButton { background: #3a1862; color: #ffe0ff;
                          border: 1px solid #ff36c8; border-radius: 4px;
                          padding: 4px 10px; font-weight: bold; }
            QPushButton:hover { background: #56229a; }
            QTabBar::tab { background: #2a0e4e; color: #d090ff;
                           padding: 4px 10px;
                           border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #ff36c8; color: #1a0e2c; }
            QPlainTextEdit, QListWidget, QTableWidget {
                background: #15082a; color: #e0c4ff;
                border: 1px solid #ff36c8;
            }
        """,
    )


def _matrix() -> Theme:
    return Theme(
        code="matrix",
        name="Matrix 駭客任務",
        description="黑底螢光綠字,致敬 The Matrix",
        palette={
            "bg": "#000000",
            "fg": "#00ff5f",
            "accent": "#00ff5f",
            "warn": "#ffd040",
            "error": "#ff5050",
        },
        stylesheet="""
            QWidget { background: #000000; color: #00ff5f;
                      font-family: 'Consolas', monospace; }
            QPushButton { background: #001f0d; color: #00ff5f;
                          border: 1px solid #00ff5f; border-radius: 0;
                          padding: 4px 10px; }
            QPushButton:hover { background: #00351c; }
            QTabBar::tab { background: #001a08; color: #00cc4f;
                           padding: 4px 10px;
                           border: 1px solid #008b35; border-radius: 0; }
            QTabBar::tab:selected { background: #00b248; color: #000000; }
            QPlainTextEdit, QListWidget, QTableWidget {
                background: #000000; color: #00ff5f;
                border: 1px solid #00b248;
            }
        """,
    )


def _retro_dos() -> Theme:
    return Theme(
        code="retro_dos",
        name="Retro DOS 復古終端機",
        description="黑底琥珀色,致敬 80 年代 DOS",
        palette={
            "bg": "#0a0805",
            "fg": "#ffb000",
            "accent": "#ffb000",
            "warn": "#ffd28a",
            "error": "#ff5040",
        },
        stylesheet="""
            QWidget { background: #0a0805; color: #ffb000;
                      font-family: 'Consolas', monospace; }
            QPushButton { background: #2a1f08; color: #ffd060;
                          border: 1px solid #ffb000; border-radius: 0;
                          padding: 4px 10px; }
            QPushButton:hover { background: #4a3010; }
            QTabBar::tab { background: #1a1208; color: #ffb000;
                           padding: 4px 10px; border: 1px solid #804000; }
            QTabBar::tab:selected { background: #ffb000; color: #0a0805; }
            QPlainTextEdit, QListWidget, QTableWidget {
                background: #0a0805; color: #ffb000;
                border: 1px solid #804000;
            }
        """,
    )


# ---------------------------------------------------------------------------
# Registry / public API
# ---------------------------------------------------------------------------
ALL_THEMES: tuple[Theme, ...] = (_classic(), _cyberpunk(), _matrix(), _retro_dos())
DEFAULT_THEME_CODE = "classic"


def get_theme(code: str) -> Theme:
    for theme in ALL_THEMES:
        if theme.code == code:
            return theme
    return ALL_THEMES[0]


def all_codes() -> tuple[str, ...]:
    return tuple(theme.code for theme in ALL_THEMES)


def apply_theme(widget, code: str) -> Theme:
    """把指定主題套到 widget(會覆蓋既有 stylesheet)。"""
    theme = get_theme(code)
    widget.setStyleSheet(theme.stylesheet)
    return theme
