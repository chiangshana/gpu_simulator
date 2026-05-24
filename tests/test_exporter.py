"""Tests for gpu_simulator.exporter."""

import csv
import json

from gpu_simulator.exporter import SessionExporter
from gpu_simulator.persistence import SessionStore


def _seed_session(store: SessionStore) -> int:
    session_id = store.start_session(name="export-test")
    for clock in range(5):
        snapshot = {
            "clock": clock,
            "overall_utilization": 0.1 * clock,
            "vram": {"used_bytes": 1024 * clock, "capacity_bytes": 4096},
            "sms": [
                {"sm_id": 0, "utilization": 0.2, "busy_warps": 1, "warp_count": 2},
                {"sm_id": 1, "utilization": 0.0, "busy_warps": 0, "warp_count": 2},
            ],
            "event_log": [{"clock": clock, "message": f"tick {clock}"}],
        }
        store.record_snapshot(
            clock=clock,
            overall_utilization=0.1 * clock,
            vram_used_bytes=1024 * clock,
            snapshot=snapshot,
        )
        store.record_event(clock=clock, message=f"evt {clock}")
        store.record_kernel_submission(
            clock=clock,
            kernel_name="vector_add",
            profile="compute",
            trigger="mouse_click",
            grid_size=4,
            block_size=64,
            vram_bytes=1024,
        )
    store.end_session(session_id, kernels_seen=5, ticks_observed=5)
    return session_id


def test_to_csv_writes_one_row_per_snapshot(tmp_path):
    with SessionStore(":memory:") as store:
        session_id = _seed_session(store)
        output_path = tmp_path / "export.csv"
        result = SessionExporter(store).to_csv(session_id, output_path)

    assert result.rows_written == 5
    with output_path.open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["clock", "overall_utilization", "vram_used_bytes", "busy_sms"]
    assert len(rows) == 6  # header + 5 rows


def test_to_json_contains_all_sections(tmp_path):
    with SessionStore(":memory:") as store:
        session_id = _seed_session(store)
        output_path = tmp_path / "export.json"
        SessionExporter(store).to_json(session_id, output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["session"]["session_id"] == session_id
    assert len(payload["snapshots"]) == 5
    assert len(payload["events"]) == 5
    assert len(payload["submissions"]) == 5


def test_to_markdown_has_summary_and_tables(tmp_path):
    with SessionStore(":memory:") as store:
        session_id = _seed_session(store)
        output_path = tmp_path / "summary.md"
        SessionExporter(store).to_markdown(session_id, output_path)

    body = output_path.read_text(encoding="utf-8")
    assert f"Session #{session_id}" in body
    assert "Average utilization" in body
    assert "Kernel mix" in body
    assert "vector_add" in body
