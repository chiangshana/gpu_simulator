"""GPU 心情日記 — 把每天的 GPU 平均負載做成 GitHub-contributions 風格熱圖。

每結束一天,widget 會呼叫 :meth:`MoodLog.record` 把今天的平均負載 + 主觀 emoji 寫進 SQLite。
:class:`MoodCalendarTab` 是個 QWidget,畫一張 12 週 × 7 天的方格熱圖,
hover 可以看當天的 mood emoji 跟一句評語。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# 資料層
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DayMood:
    """單日心情記錄。"""

    day: date
    average_utilization: float    # 0.0 ~ 100.0
    peak_utilization: float       # 0.0 ~ 100.0
    kernel_count: int             # 當日跑的 kernel 總數
    note: str = ""                # 使用者寫的短評(可空)

    @property
    def emoji(self) -> str:
        """根據 utilization 推一個心情 emoji。"""
        u = self.average_utilization
        if self.kernel_count == 0:
            return "😴"  # 沒在用
        if u < 20:
            return "🌱"  # 輕鬆
        if u < 45:
            return "🙂"  # 還行
        if u < 70:
            return "💪"  # 認真
        if u < 90:
            return "🔥"  # 燃燒
        return "🚀"      # 爆棚

    @property
    def intensity(self) -> int:
        """0..4 — 熱圖格子顏色等級。"""
        if self.kernel_count == 0:
            return 0
        u = self.average_utilization
        if u < 20:
            return 1
        if u < 45:
            return 2
        if u < 70:
            return 3
        return 4

    def summary(self) -> str:
        return (
            f"{self.day.isoformat()} · {self.emoji} · "
            f"平均 {self.average_utilization:.0f}% · 峰值 {self.peak_utilization:.0f}% · "
            f"跑了 {self.kernel_count} 個 kernel"
        )


class MoodLog:
    """SQLite 後端 — 一天一列;同一天再寫會覆蓋。"""

    DDL = """
    CREATE TABLE IF NOT EXISTS mood_log (
        day TEXT PRIMARY KEY,
        avg_util REAL NOT NULL,
        peak_util REAL NOT NULL,
        kernel_count INTEGER NOT NULL,
        note TEXT NOT NULL DEFAULT ''
    );
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        with self._connect() as conn:
            conn.executescript(self.DDL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, mood: DayMood) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mood_log (day, avg_util, peak_util, kernel_count, note)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    avg_util = excluded.avg_util,
                    peak_util = excluded.peak_util,
                    kernel_count = excluded.kernel_count,
                    note = excluded.note
                """,
                (
                    mood.day.isoformat(),
                    float(mood.average_utilization),
                    float(mood.peak_utilization),
                    int(mood.kernel_count),
                    mood.note,
                ),
            )

    def all_days(self) -> list[DayMood]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT day, avg_util, peak_util, kernel_count, note "
                "FROM mood_log ORDER BY day ASC"
            ).fetchall()
        return [
            DayMood(
                day=date.fromisoformat(row["day"]),
                average_utilization=float(row["avg_util"]),
                peak_utilization=float(row["peak_util"]),
                kernel_count=int(row["kernel_count"]),
                note=row["note"] or "",
            )
            for row in rows
        ]

    def get(self, day: date) -> DayMood | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT day, avg_util, peak_util, kernel_count, note "
                "FROM mood_log WHERE day = ?",
                (day.isoformat(),),
            ).fetchone()
        if row is None:
            return None
        return DayMood(
            day=date.fromisoformat(row["day"]),
            average_utilization=float(row["avg_util"]),
            peak_utilization=float(row["peak_util"]),
            kernel_count=int(row["kernel_count"]),
            note=row["note"] or "",
        )


# ---------------------------------------------------------------------------
# Grid 排版邏輯(GitHub 風) — 純資料層
# ---------------------------------------------------------------------------
def build_grid(today: date, days: Iterable[DayMood], weeks: int = 12) -> list[list[DayMood | None]]:
    """回傳 ``weeks × 7`` 的 grid。``grid[w][d]`` = 第 w 週(從左到右)、星期 d(0=週一)。

    最右邊一欄(``weeks-1``)結束於 ``today``。沒記錄的日子 = None。
    """
    if weeks <= 0:
        raise ValueError("weeks 必須是正整數")
    by_day = {m.day: m for m in days}
    grid: list[list[DayMood | None]] = []
    # 找出 today 是星期幾(0=週一);往前推到該週的週一
    today_weekday = today.weekday()
    last_week_start = today - timedelta(days=today_weekday)
    # 先建 weeks 個 week column
    for w in range(weeks):
        week_start = last_week_start - timedelta(weeks=weeks - 1 - w)
        column: list[DayMood | None] = []
        for dow in range(7):
            day = week_start + timedelta(days=dow)
            if day > today:
                column.append(None)
            else:
                column.append(by_day.get(day))
        grid.append(column)
    return grid


# ---------------------------------------------------------------------------
# Qt widget
# ---------------------------------------------------------------------------
INTENSITY_COLORS = [
    "#1f2027",  # 0 — 沒資料
    "#3a3b2c",  # 1 — 輕度
    "#5a6a30",  # 2 — 中度
    "#88a83a",  # 3 — 認真
    "#d8e833",  # 4 — 爆棚
]


def build_mood_calendar_widget(parent, log: MoodLog, weeks: int = 12):
    """畫熱圖 + 上方一行說明;會幫你掛 tooltip。"""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

    today = date.today()
    days = log.all_days()
    grid = build_grid(today, days, weeks=weeks)

    box = QWidget(parent)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(12, 12, 12, 12)
    header = QLabel(
        f"📅 GPU 心情日記 — 最近 {weeks} 週(右下角是今天:{today.isoformat()})",
        box,
    )
    header.setStyleSheet("color: rgba(220,220,230,240); font-size: 11pt;")
    layout.addWidget(header)
    legend = QLabel("less ░ ▒ ▓ █ more", box)
    legend.setStyleSheet("color: rgba(160,160,170,200); font-family: monospace;")
    layout.addWidget(legend)

    cell_size = 18
    cell_gap = 3

    class HeatmapCanvas(QWidget):
        def __init__(self, parent_):
            super().__init__(parent_)
            self.setMinimumHeight((cell_size + cell_gap) * 7 + 8)
            self.setMouseTracking(True)

        def paintEvent(self, _event):  # noqa: N802
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, False)
            for w_idx, column in enumerate(grid):
                for d_idx, mood in enumerate(column):
                    x = w_idx * (cell_size + cell_gap) + 4
                    y = d_idx * (cell_size + cell_gap) + 4
                    if mood is None:
                        color = QColor(35, 38, 44, 80)
                    else:
                        color = QColor(INTENSITY_COLORS[mood.intensity])
                    painter.fillRect(x, y, cell_size, cell_size, color)
            painter.end()

        def mouseMoveEvent(self, event):  # noqa: N802
            pos = event.position() if hasattr(event, "position") else event.pos()
            x = int(pos.x())
            y = int(pos.y())
            w_idx = (x - 4) // (cell_size + cell_gap)
            d_idx = (y - 4) // (cell_size + cell_gap)
            if 0 <= w_idx < len(grid) and 0 <= d_idx < 7:
                mood = grid[w_idx][d_idx]
                if mood is None:
                    self.setToolTip("(這天沒記錄)")
                else:
                    self.setToolTip(mood.summary() + (f"\n備註:{mood.note}" if mood.note else ""))
            else:
                self.setToolTip("")

    canvas = HeatmapCanvas(box)
    canvas.setAttribute(Qt.WA_StyledBackground, True)
    canvas.setStyleSheet("background: rgba(20,22,28,200); border-radius: 8px;")
    layout.addWidget(canvas, 1)

    summary_lbl = QLabel(box)
    summary_lbl.setStyleSheet("color: rgba(200,210,220,230); font-size: 10pt;")
    recent = [m for m in days if (today - m.day).days < weeks * 7]
    if recent:
        total_kernels = sum(m.kernel_count for m in recent)
        avg = sum(m.average_utilization for m in recent) / max(1, len(recent))
        summary_lbl.setText(
            f"近 {weeks} 週共 {len(recent)} 天有紀錄 · {total_kernels} 個 kernel · 平均負載 {avg:.0f}%"
        )
    else:
        summary_lbl.setText("還沒有紀錄;跑一些 kernel 之後每天會自動入帳。")
    layout.addWidget(summary_lbl)

    box._mood_log = log  # type: ignore[attr-defined]
    return box
