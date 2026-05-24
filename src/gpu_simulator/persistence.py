"""SQLite-backed session recorder and replay source.

Every desktop-widget launch registers one *session* and streams:

- **events**       — one row per entry written to the GPU's event log
- **snapshots**    — a downsampled time series of SM utilisation & VRAM
- **kernel submissions** — one row per kernel handed to the scheduler

All writes go through :class:`SessionStore`, which hides the SQL and
raises :class:`~gpu_simulator.exceptions.PersistenceError` on any sqlite
failure.  For unit tests pass ``":memory:"`` as the database path.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from gpu_simulator.exceptions import PersistenceError

SCHEMA_VERSION = 1

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_info (
        version INTEGER PRIMARY KEY
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        started_at      TEXT NOT NULL,
        ended_at        TEXT,
        kernels_seen    INTEGER NOT NULL DEFAULT 0,
        ticks_observed  INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        clock       INTEGER NOT NULL,
        message     TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS snapshots (
        session_id         INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        clock              INTEGER NOT NULL,
        overall_utilization REAL NOT NULL,
        vram_used_bytes    INTEGER NOT NULL,
        snapshot_json      TEXT NOT NULL,
        recorded_at        TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kernel_submissions (
        session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        clock        INTEGER NOT NULL,
        kernel_name  TEXT NOT NULL,
        profile      TEXT NOT NULL,
        trigger      TEXT,
        grid_size    INTEGER NOT NULL,
        block_size   INTEGER NOT NULL,
        vram_bytes   INTEGER NOT NULL,
        recorded_at  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, clock)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_session ON snapshots(session_id, clock)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_session ON kernel_submissions(session_id, clock)",
)


@dataclass(frozen=True)
class SessionMeta:
    """Lightweight session header used in the history list."""

    session_id: int
    name: str
    started_at: datetime
    ended_at: datetime | None
    kernels_seen: int
    ticks_observed: int

    def pretty_label(self) -> str:
        stamp = self.started_at.strftime("%Y-%m-%d %H:%M:%S")
        return f"#{self.session_id} · {stamp} · {self.name}"


@dataclass(frozen=True)
class SnapshotRow:
    """One stored snapshot, decoded back into something the UI can use."""

    clock: int
    overall_utilization: float
    vram_used_bytes: int
    snapshot: dict


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------
class SessionStore:
    """Thread-safe SQLite wrapper around the session tables.

    Instances are context managers; :meth:`close` is also safe to call
    manually.  All public methods raise :class:`PersistenceError` on
    failure so callers never have to import ``sqlite3`` themselves.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path) if db_path != ":memory:" else ":memory:"
        try:
            if self._db_path != ":memory:":
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                str(self._db_path),
                detect_types=sqlite3.PARSE_DECLTYPES,
                check_same_thread=False,
            )
            self._connection.execute("PRAGMA foreign_keys = ON")
        except sqlite3.Error as exc:
            raise PersistenceError(f"could not open session DB: {exc}") from exc
        self._active_session_id: int | None = None
        self._bootstrap_schema()

    # ------------------------------------------------------------------
    # session lifecycle
    # ------------------------------------------------------------------
    def start_session(self, name: str = "live") -> int:
        started_at = datetime.now(tz=timezone.utc).isoformat()
        try:
            cursor = self._connection.execute(
                "INSERT INTO sessions (name, started_at) VALUES (?, ?)",
                (name, started_at),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"could not start session: {exc}") from exc
        self._active_session_id = cursor.lastrowid
        assert self._active_session_id is not None
        return self._active_session_id

    def end_session(
        self, session_id: int | None = None, kernels_seen: int = 0, ticks_observed: int = 0
    ) -> None:
        session_id = self._resolve_session(session_id)
        ended_at = datetime.now(tz=timezone.utc).isoformat()
        try:
            self._connection.execute(
                """
                UPDATE sessions
                SET ended_at = ?, kernels_seen = ?, ticks_observed = ?
                WHERE id = ?
                """,
                (ended_at, kernels_seen, ticks_observed, session_id),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"could not end session: {exc}") from exc
        if session_id == self._active_session_id:
            self._active_session_id = None

    # ------------------------------------------------------------------
    # write paths
    # ------------------------------------------------------------------
    def record_event(
        self, clock: int, message: str, session_id: int | None = None
    ) -> None:
        session_id = self._resolve_session(session_id)
        self._execute(
            "INSERT INTO events (session_id, clock, message, recorded_at) VALUES (?, ?, ?, ?)",
            (session_id, clock, message, _now_iso()),
            error_context="recording event",
        )

    def record_snapshot(
        self,
        clock: int,
        overall_utilization: float,
        vram_used_bytes: int,
        snapshot: dict,
        session_id: int | None = None,
    ) -> None:
        session_id = self._resolve_session(session_id)
        self._execute(
            """
            INSERT INTO snapshots
                (session_id, clock, overall_utilization, vram_used_bytes,
                 snapshot_json, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                clock,
                float(overall_utilization),
                int(vram_used_bytes),
                json.dumps(snapshot, ensure_ascii=False),
                _now_iso(),
            ),
            error_context="recording snapshot",
        )

    def record_kernel_submission(
        self,
        clock: int,
        kernel_name: str,
        profile: str,
        trigger: str,
        grid_size: int,
        block_size: int,
        vram_bytes: int,
        session_id: int | None = None,
    ) -> None:
        session_id = self._resolve_session(session_id)
        self._execute(
            """
            INSERT INTO kernel_submissions
                (session_id, clock, kernel_name, profile, trigger,
                 grid_size, block_size, vram_bytes, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                clock,
                kernel_name,
                profile,
                trigger or None,
                grid_size,
                block_size,
                vram_bytes,
                _now_iso(),
            ),
            error_context="recording kernel submission",
        )

    # ------------------------------------------------------------------
    # read paths
    # ------------------------------------------------------------------
    def list_sessions(self, limit: int = 100) -> list[SessionMeta]:
        try:
            rows = self._connection.execute(
                """
                SELECT id, name, started_at, ended_at, kernels_seen, ticks_observed
                FROM sessions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError(f"could not list sessions: {exc}") from exc
        return [_row_to_session_meta(row) for row in rows]

    def iter_snapshots(self, session_id: int) -> Iterator[SnapshotRow]:
        try:
            cursor = self._connection.execute(
                """
                SELECT clock, overall_utilization, vram_used_bytes, snapshot_json
                FROM snapshots
                WHERE session_id = ?
                ORDER BY clock ASC
                """,
                (session_id,),
            )
        except sqlite3.Error as exc:
            raise PersistenceError(f"could not read snapshots: {exc}") from exc
        for clock, utilization, vram_used, payload in cursor:
            yield SnapshotRow(
                clock=clock,
                overall_utilization=utilization,
                vram_used_bytes=vram_used,
                snapshot=json.loads(payload),
            )

    def events_for(self, session_id: int) -> list[tuple[int, str]]:
        try:
            return [
                (row[0], row[1])
                for row in self._connection.execute(
                    "SELECT clock, message FROM events WHERE session_id = ? ORDER BY clock",
                    (session_id,),
                )
            ]
        except sqlite3.Error as exc:
            raise PersistenceError(f"could not read events: {exc}") from exc

    def submissions_for(self, session_id: int) -> list[dict]:
        try:
            rows = self._connection.execute(
                """
                SELECT clock, kernel_name, profile, trigger, grid_size, block_size, vram_bytes
                FROM kernel_submissions
                WHERE session_id = ?
                ORDER BY clock
                """,
                (session_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError(f"could not read submissions: {exc}") from exc
        return [
            {
                "clock": row[0],
                "kernel_name": row[1],
                "profile": row[2],
                "trigger": row[3],
                "grid_size": row[4],
                "block_size": row[5],
                "vram_bytes": row[6],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # housekeeping
    # ------------------------------------------------------------------
    def close(self) -> None:
        try:
            if self._active_session_id is not None:
                self.end_session(self._active_session_id)
        finally:
            with suppress(sqlite3.Error):
                self._connection.close()

    def __enter__(self) -> SessionStore:
        return self

    def __exit__(self, *_excinfo) -> None:
        self.close()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _bootstrap_schema(self) -> None:
        try:
            with closing(self._connection.cursor()) as cursor:
                for statement in _SCHEMA_STATEMENTS:
                    cursor.execute(statement)
                cursor.execute(
                    "INSERT OR IGNORE INTO schema_info (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            self._connection.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"schema bootstrap failed: {exc}") from exc

    def _resolve_session(self, session_id: int | None) -> int:
        resolved = session_id if session_id is not None else self._active_session_id
        if resolved is None:
            raise PersistenceError(
                "no active session — call start_session() first or pass session_id"
            )
        return resolved

    def _execute(
        self, sql: str, params: Iterable, error_context: str
    ) -> None:
        try:
            self._connection.execute(sql, tuple(params))
            self._connection.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"{error_context}: {exc}") from exc


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _row_to_session_meta(row: tuple) -> SessionMeta:
    session_id, name, started_at, ended_at, kernels_seen, ticks_observed = row
    return SessionMeta(
        session_id=session_id,
        name=name,
        started_at=datetime.fromisoformat(started_at),
        ended_at=datetime.fromisoformat(ended_at) if ended_at else None,
        kernels_seen=kernels_seen or 0,
        ticks_observed=ticks_observed or 0,
    )
