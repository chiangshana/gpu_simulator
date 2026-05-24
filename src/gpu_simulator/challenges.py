"""每日挑戰 + SQLite leaderboard。

由今日的「日期 hash」決定當日題目,並記錄使用者的最佳分數。
題目分三類(目前各 1 種模板,但日期會變動參數):

- **kernel_count**:在 N cycle 以內提交 K 顆某種 kernel
- **kernel_mix**:提交一組指定的 kernel 種類組合
- **memory_writes**:寫入指定數量的記憶體位址

使用方式::

    from gpu_simulator.challenges import (
        daily_challenge, ChallengeResult, score_attempt, leaderboard
    )

    challenge = daily_challenge()
    print(challenge.title, challenge.description)

    # 在 widget 跑完使用者的 asm 後:
    result = score_attempt(challenge, trace_rows=...,
                           kernels_submitted=..., memory_writes=set())
    if result.passed:
        leaderboard_record(challenge.code, "shana", result.cycles_used)

    # 拿排行榜
    for entry in leaderboard("today"):
        print(entry)
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from gpu_simulator.exceptions import PersistenceError
from gpu_simulator.i18n import kernel_label

KERNEL_NAMES_BY_ID: tuple[str, ...] = (
    "vector_add",
    "interpolation",
    "hash",
    "texture_load",
    "idle_compression",
    "app_launch",
    "page_nav",
)


# ---------------------------------------------------------------------------
# Challenge dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Challenge:
    code: str  # 唯一 id,當日穩定
    kind: str  # "kernel_count" / "kernel_mix" / "memory_writes"
    title: str
    description: str
    target_kernel: str | None
    target_count: int
    cycle_budget: int
    target_set: tuple[str, ...] = ()

    def short_label(self) -> str:
        return f"#{self.code[-6:]}  {self.title}"


@dataclass(frozen=True)
class ChallengeResult:
    passed: bool
    score: int
    cycles_used: int
    detail: str


# ---------------------------------------------------------------------------
# 每日題目產生器
# ---------------------------------------------------------------------------
def daily_challenge(today: date | None = None) -> Challenge:
    """根據日期 hash 產生當日題目。"""
    today = today or date.today()
    seed = int(hashlib.sha256(today.isoformat().encode()).hexdigest(), 16)
    challenge_kind = ("kernel_count", "kernel_mix", "memory_writes")[seed % 3]
    if challenge_kind == "kernel_count":
        kernel = KERNEL_NAMES_BY_ID[seed % len(KERNEL_NAMES_BY_ID)]
        count = 3 + (seed // 7) % 5  # 3..7
        budget = 30 + (seed // 11) % 30  # 30..59
        return Challenge(
            code=_code_for(today, "kc"),
            kind="kernel_count",
            title=f"{count} 顆「{kernel_label(kernel)}」kernel 限 {budget} cycle 內完成",
            description=(
                f"今天的目標:在 {budget} 個 cycle 內提交至少 {count} 顆 "
                f"`{kernel}`(中文:{kernel_label(kernel)})kernel,然後 KWAIT 等它跑完。"
            ),
            target_kernel=kernel,
            target_count=count,
            cycle_budget=budget,
        )
    if challenge_kind == "kernel_mix":
        mix_size = 3 + (seed // 13) % 3  # 3..5
        kernels: list[str] = []
        for offset in range(mix_size):
            kernels.append(KERNEL_NAMES_BY_ID[(seed + offset * 17) % len(KERNEL_NAMES_BY_ID)])
        kernels = list(dict.fromkeys(kernels))
        budget = 50 + (seed // 19) % 30
        return Challenge(
            code=_code_for(today, "km"),
            kind="kernel_mix",
            title=f"湊齊 {len(kernels)} 種 kernel 各至少 1 顆",
            description=(
                f"在 {budget} 個 cycle 內,把這幾種 kernel 各提交至少 1 顆:"
                f"{', '.join(kernel_label(k) for k in kernels)}。"
            ),
            target_kernel=None,
            target_count=len(kernels),
            cycle_budget=budget,
            target_set=tuple(kernels),
        )
    # memory_writes
    target_writes = 6 + (seed // 23) % 8  # 6..13
    budget = 50 + (seed // 29) % 30
    return Challenge(
        code=_code_for(today, "mw"),
        kind="memory_writes",
        title=f"在 {budget} cycle 內寫入 {target_writes} 個不同記憶體位址",
        description=(
            f"用 ST / STS 寫到至少 {target_writes} 個不同的記憶體位址,"
            f"並在 {budget} cycle 內完成。"
        ),
        target_kernel=None,
        target_count=target_writes,
        cycle_budget=budget,
    )


def _code_for(today: date, prefix: str) -> str:
    return f"{prefix}-{today.isoformat()}"


# ---------------------------------------------------------------------------
# 評分
# ---------------------------------------------------------------------------
def score_attempt(
    challenge: Challenge,
    *,
    trace_rows: Sequence,
    kernels_submitted: int,
    memory_writes: set[int] | None = None,
) -> ChallengeResult:
    cycles_used = len(trace_rows)
    memory_writes = memory_writes or set()

    if challenge.kind == "kernel_count":
        target_index = _kernel_name_to_id(challenge.target_kernel or "")
        actual = sum(1 for row in trace_rows for port, val in row.port_writes
                     if port == 0x40 and (val & 0xFF) == target_index)
        passed = actual >= challenge.target_count and cycles_used <= challenge.cycle_budget
        detail = (
            f"提交了 {actual} 顆,目標 {challenge.target_count}; "
            f"cycles={cycles_used}/{challenge.cycle_budget}"
        )
    elif challenge.kind == "kernel_mix":
        seen_ids = {
            val & 0xFF
            for row in trace_rows
            for port, val in row.port_writes
            if port == 0x40
        }
        target_ids = {_kernel_name_to_id(name) for name in challenge.target_set}
        passed = target_ids.issubset(seen_ids) and cycles_used <= challenge.cycle_budget
        detail = (
            f"提交涵蓋 {len(seen_ids & target_ids)}/{len(target_ids)} 種; "
            f"cycles={cycles_used}/{challenge.cycle_budget}"
        )
    else:  # memory_writes
        passed = (
            len(memory_writes) >= challenge.target_count
            and cycles_used <= challenge.cycle_budget
        )
        detail = (
            f"寫入 {len(memory_writes)} 個位址,目標 {challenge.target_count}; "
            f"cycles={cycles_used}/{challenge.cycle_budget}"
        )

    score = max(0, challenge.cycle_budget - cycles_used) if passed else 0
    return ChallengeResult(
        passed=passed, score=score, cycles_used=cycles_used, detail=detail
    )


def _kernel_name_to_id(name: str) -> int:
    try:
        return KERNEL_NAMES_BY_ID.index(name)
    except ValueError:
        return -1


# ---------------------------------------------------------------------------
# Leaderboard(SQLite)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LeaderboardEntry:
    challenge_code: str
    nickname: str
    cycles_used: int
    score: int
    achieved_at: datetime


SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS leaderboard (
        challenge_code TEXT NOT NULL,
        nickname       TEXT NOT NULL,
        cycles_used    INTEGER NOT NULL,
        score          INTEGER NOT NULL,
        achieved_at    TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_lb_challenge ON leaderboard(challenge_code, score DESC)
    """,
)


class LeaderboardStore:
    """SQLite-backed daily challenge scores."""

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
            raise PersistenceError(f"could not open leaderboard DB: {exc}") from exc
        for statement in SCHEMA_STATEMENTS:
            self._connection.execute(statement)
        self._connection.commit()

    def record(
        self,
        challenge_code: str,
        nickname: str,
        cycles_used: int,
        score: int,
    ) -> None:
        try:
            self._connection.execute(
                "INSERT INTO leaderboard "
                "(challenge_code, nickname, cycles_used, score, achieved_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    challenge_code,
                    nickname,
                    int(cycles_used),
                    int(score),
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"recording score failed: {exc}") from exc

    def top_for(self, challenge_code: str, limit: int = 10) -> list[LeaderboardEntry]:
        try:
            rows = self._connection.execute(
                """
                SELECT challenge_code, nickname, cycles_used, score, achieved_at
                FROM leaderboard
                WHERE challenge_code = ?
                ORDER BY score DESC, cycles_used ASC
                LIMIT ?
                """,
                (challenge_code, limit),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError(f"reading leaderboard failed: {exc}") from exc
        return [
            LeaderboardEntry(
                challenge_code=row[0],
                nickname=row[1],
                cycles_used=int(row[2]),
                score=int(row[3]),
                achieved_at=datetime.fromisoformat(row[4]),
            )
            for row in rows
        ]

    def reset(self) -> None:
        try:
            self._connection.execute("DELETE FROM leaderboard")
            self._connection.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"resetting leaderboard failed: {exc}") from exc

    def close(self) -> None:
        import contextlib

        with contextlib.suppress(sqlite3.Error):
            self._connection.close()
