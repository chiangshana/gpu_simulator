"""Export a persisted session to a human-readable artifact.

Supports four output formats:

============  ==============================================================
  format        description
============  ==============================================================
``csv``       one row per snapshot (clock / util / VRAM bytes)
``json``      the full session dump (meta + snapshots + events)
``markdown``  summary report suitable for pasting into a write-up
``png``       matplotlib time-series chart of utilisation and VRAM
============  ==============================================================

Callers pass in an already-opened :class:`~gpu_simulator.persistence.SessionStore`
so that the exporter does not own the database connection.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from gpu_simulator.exceptions import PersistenceError

if TYPE_CHECKING:  # pragma: no cover
    from gpu_simulator.persistence import SessionStore


@dataclass(frozen=True)
class ExportResult:
    path: Path
    rows_written: int


class SessionExporter:
    """Translate stored sessions into CSV / JSON / Markdown / PNG."""

    def __init__(self, store: SessionStore) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------
    def to_csv(self, session_id: int, output_path: Path | str) -> ExportResult:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows_written = 0
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["clock", "overall_utilization", "vram_used_bytes", "busy_sms"]
            )
            for snapshot_row in self._store.iter_snapshots(session_id):
                busy_sms = sum(
                    1
                    for sm in snapshot_row.snapshot.get("sms", [])
                    if sm.get("utilization", 0.0) > 0
                )
                writer.writerow(
                    [
                        snapshot_row.clock,
                        f"{snapshot_row.overall_utilization:.4f}",
                        snapshot_row.vram_used_bytes,
                        busy_sms,
                    ]
                )
                rows_written += 1
        return ExportResult(path=output_path, rows_written=rows_written)

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------
    def to_json(self, session_id: int, output_path: Path | str) -> ExportResult:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        meta = self._meta_for(session_id)
        payload = {
            "session": meta,
            "snapshots": [
                {
                    "clock": row.clock,
                    "overall_utilization": row.overall_utilization,
                    "vram_used_bytes": row.vram_used_bytes,
                    "snapshot": row.snapshot,
                }
                for row in self._store.iter_snapshots(session_id)
            ],
            "events": [
                {"clock": clock, "message": message}
                for clock, message in self._store.events_for(session_id)
            ],
            "submissions": self._store.submissions_for(session_id),
        }
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ExportResult(path=output_path, rows_written=len(payload["snapshots"]))

    # ------------------------------------------------------------------
    # Markdown summary
    # ------------------------------------------------------------------
    def to_markdown(self, session_id: int, output_path: Path | str) -> ExportResult:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        meta = self._meta_for(session_id)
        snapshots = list(self._store.iter_snapshots(session_id))
        submissions = self._store.submissions_for(session_id)
        events = self._store.events_for(session_id)

        utilisations = [row.overall_utilization for row in snapshots]
        util_avg = statistics.fmean(utilisations) if utilisations else 0.0
        util_max = max(utilisations, default=0.0)
        vram_peak = max((row.vram_used_bytes for row in snapshots), default=0)

        kernel_counts = Counter(sub["kernel_name"] for sub in submissions)
        trigger_counts = Counter(sub["trigger"] or "n/a" for sub in submissions)

        lines: list[str] = [
            f"# Session #{meta['session_id']} — {meta['name']}",
            "",
            f"- Started at: `{meta['started_at']}`",
            f"- Ended at:   `{meta['ended_at'] or 'in-progress'}`",
            f"- Snapshots:  **{len(snapshots)}**",
            f"- Kernel submissions: **{len(submissions)}**",
            f"- Average utilization: **{util_avg * 100:.1f}%**",
            f"- Peak utilization:    **{util_max * 100:.1f}%**",
            f"- Peak VRAM used:      **{vram_peak / 1024 / 1024:.2f} MiB**",
            "",
            "## Kernel mix",
            "",
            "| kernel | count |",
            "| ------ | ----- |",
        ]
        for kernel_name, count in kernel_counts.most_common():
            lines.append(f"| {kernel_name} | {count} |")
        lines += [
            "",
            "## Triggers",
            "",
            "| trigger | count |",
            "| ------- | ----- |",
        ]
        for trigger, count in trigger_counts.most_common():
            lines.append(f"| {trigger} | {count} |")

        if events:
            lines += ["", "## First 15 event-log messages", ""]
            for clock, message in events[:15]:
                lines.append(f"- `[{clock:>5}]` {message}")

        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return ExportResult(path=output_path, rows_written=len(snapshots))

    # ------------------------------------------------------------------
    # PNG chart (matplotlib)
    # ------------------------------------------------------------------
    def to_png(self, session_id: int, output_path: Path | str) -> ExportResult:
        try:
            import matplotlib

            matplotlib.use("Agg")  # headless-friendly
            import matplotlib.pyplot as plt
        except ImportError as exc:  # pragma: no cover - optional dep check
            raise PersistenceError(
                "matplotlib is required for PNG export; install it first"
            ) from exc

        snapshots = list(self._store.iter_snapshots(session_id))
        if not snapshots:
            raise PersistenceError(f"session {session_id} has no snapshots to plot")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        clocks = [row.clock for row in snapshots]
        utilisations = [row.overall_utilization * 100 for row in snapshots]
        vram_mib = [row.vram_used_bytes / 1024 / 1024 for row in snapshots]

        figure, util_axis = plt.subplots(figsize=(8, 4.5))
        util_axis.plot(clocks, utilisations, color="#f0a040", label="Utilization (%)")
        util_axis.set_xlabel("clock")
        util_axis.set_ylabel("utilization (%)", color="#f0a040")
        util_axis.set_ylim(0, 100)
        util_axis.tick_params(axis="y", labelcolor="#f0a040")

        vram_axis = util_axis.twinx()
        vram_axis.plot(clocks, vram_mib, color="#78b4ff", label="VRAM (MiB)")
        vram_axis.set_ylabel("VRAM used (MiB)", color="#78b4ff")
        vram_axis.tick_params(axis="y", labelcolor="#78b4ff")

        figure.suptitle(f"gpu_simulator session #{session_id}")
        figure.tight_layout()
        figure.savefig(output_path, dpi=120)
        plt.close(figure)

        return ExportResult(path=output_path, rows_written=len(snapshots))

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _meta_for(self, session_id: int) -> dict:
        for session_meta in self._store.list_sessions(limit=10_000):
            if session_meta.session_id == session_id:
                return {
                    "session_id": session_meta.session_id,
                    "name": session_meta.name,
                    "started_at": session_meta.started_at.isoformat(),
                    "ended_at": session_meta.ended_at.isoformat()
                    if session_meta.ended_at
                    else None,
                    "kernels_seen": session_meta.kernels_seen,
                    "ticks_observed": session_meta.ticks_observed,
                }
        raise PersistenceError(f"session {session_id} not found")
