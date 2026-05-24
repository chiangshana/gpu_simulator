"""成就(徽章)系統。

10 個內建成就用 SQLite `achievements` 表持久化,跨次開啟保留。
:class:`AchievementTracker` 在 widget 的 ``_on_tick`` / ASM run 結束時被
呼叫,內部追蹤條件達成,首次達成時透過回呼通知 UI 彈出小視窗。

外部 API 都是純 Python 物件,沒有 Qt 相依,可以單獨測試。
"""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from gpu_simulator.exceptions import PersistenceError
from gpu_simulator.i18n import t


# ---------------------------------------------------------------------------
# 成就定義
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Achievement:
    code: str
    name_key: str
    description_key: str

    @property
    def name(self) -> str:
        return t(self.name_key)

    @property
    def description(self) -> str:
        return t(self.description_key)


ACHIEVEMENTS: tuple[Achievement, ...] = (
    Achievement("first_run", "ach.first_run.name", "ach.first_run.desc"),
    Achievement("first_klaunch", "ach.first_klaunch.name", "ach.first_klaunch.desc"),
    Achievement("first_kwait", "ach.first_kwait.name", "ach.first_kwait.desc"),
    Achievement("full_load", "ach.full_load.name", "ach.full_load.desc"),
    Achievement("memory_master", "ach.memory_master.name", "ach.memory_master.desc"),
    Achievement(
        "kernel_collector", "ach.kernel_collector.name", "ach.kernel_collector.desc"
    ),
    Achievement("long_session", "ach.long_session.name", "ach.long_session.desc"),
    Achievement("idle_master", "ach.idle_master.name", "ach.idle_master.desc"),
    Achievement("quiz_pass", "ach.quiz_pass.name", "ach.quiz_pass.desc"),
    Achievement("recorder", "ach.recorder.name", "ach.recorder.desc"),
)

ACHIEVEMENTS_BY_CODE: dict[str, Achievement] = {a.code: a for a in ACHIEVEMENTS}


# ---------------------------------------------------------------------------
# 持久化儲存
# ---------------------------------------------------------------------------
class AchievementStore:
    """SQLite-backed badge persistence."""

    SCHEMA_STATEMENTS: tuple[str, ...] = (
        """
        CREATE TABLE IF NOT EXISTS achievements (
            code        TEXT PRIMARY KEY,
            unlocked_at TEXT NOT NULL
        )
        """,
    )

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = (
            Path(db_path) if db_path != ":memory:" else ":memory:"
        )
        try:
            if self._db_path != ":memory:":
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                str(self._db_path), check_same_thread=False
            )
        except sqlite3.Error as exc:
            raise PersistenceError(f"could not open achievements DB: {exc}") from exc
        for statement in self.SCHEMA_STATEMENTS:
            self._connection.execute(statement)
        self._connection.commit()

    def is_unlocked(self, code: str) -> bool:
        try:
            row = self._connection.execute(
                "SELECT 1 FROM achievements WHERE code = ? LIMIT 1", (code,)
            ).fetchone()
        except sqlite3.Error as exc:
            raise PersistenceError(f"reading achievements: {exc}") from exc
        return row is not None

    def unlock(self, code: str) -> bool:
        """Insert ``code`` if missing.  Returns True if this call did the unlock."""
        if self.is_unlocked(code):
            return False
        try:
            self._connection.execute(
                "INSERT INTO achievements (code, unlocked_at) VALUES (?, ?)",
                (code, datetime.now(tz=timezone.utc).isoformat()),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"writing achievement: {exc}") from exc
        return True

    def all_unlocked(self) -> dict[str, datetime]:
        try:
            rows = self._connection.execute(
                "SELECT code, unlocked_at FROM achievements"
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError(f"reading achievements: {exc}") from exc
        result: dict[str, datetime] = {}
        for code, unlocked_at in rows:
            try:
                result[code] = datetime.fromisoformat(unlocked_at)
            except ValueError:
                continue
        return result

    def reset(self) -> None:
        try:
            self._connection.execute("DELETE FROM achievements")
            self._connection.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"resetting achievements: {exc}") from exc

    def close(self) -> None:
        with contextlib.suppress(sqlite3.Error):
            self._connection.close()


# ---------------------------------------------------------------------------
# Tracker — UI 在每個關鍵事件呼叫對應方法
# ---------------------------------------------------------------------------
UnlockCallback = Callable[[Achievement], None]


class AchievementTracker:
    """偵測達成條件並透過回呼通知 UI。"""

    def __init__(
        self,
        store: AchievementStore,
        on_unlock: UnlockCallback | None = None,
    ) -> None:
        self._store = store
        self._on_unlock = on_unlock or (lambda _achievement: None)

    # 上層直接呼叫的關鍵事件 ---------------------------------------------
    def report_first_run(self) -> None:
        self._maybe_unlock("first_run")

    def report_klaunch(self) -> None:
        self._maybe_unlock("first_klaunch")

    def report_kwait_completed(self) -> None:
        self._maybe_unlock("first_kwait")

    def report_idle_kernel(self) -> None:
        self._maybe_unlock("idle_master")

    def report_recorder_used(self) -> None:
        self._maybe_unlock("recorder")

    def report_quiz_perfect(self) -> None:
        self._maybe_unlock("quiz_pass")

    # 從 snapshot 推得的條件 ---------------------------------------------
    def report_snapshot(self, snapshot: dict, *, cycles_observed: int = 0) -> None:
        utilization = float(snapshot.get("overall_utilization", 0.0))
        if utilization >= 0.999:
            self._maybe_unlock("full_load")
        if int(snapshot.get("kernels_submitted", 0)) >= 5:
            self._maybe_unlock("kernel_collector")
        if cycles_observed >= 100:
            self._maybe_unlock("long_session")

    def report_memory_writes(self, distinct_addresses: int) -> None:
        if distinct_addresses >= 16:
            self._maybe_unlock("memory_master")

    # 共用內部 ---------------------------------------------------------
    def _maybe_unlock(self, code: str) -> None:
        achievement = ACHIEVEMENTS_BY_CODE.get(code)
        if achievement is None:
            return
        try:
            newly_unlocked = self._store.unlock(code)
        except PersistenceError:
            return
        if newly_unlocked:
            with contextlib.suppress(Exception):
                # UI 出錯不影響成就紀錄已寫入
                self._on_unlock(achievement)
