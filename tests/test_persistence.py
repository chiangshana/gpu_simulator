"""Tests for gpu_simulator.persistence — SQLite session store."""

import pytest

from gpu_simulator.exceptions import PersistenceError
from gpu_simulator.persistence import SessionStore


def _fabricate_snapshot(clock: int, utilisation: float, vram_bytes: int) -> dict:
    return {
        "clock": clock,
        "overall_utilization": utilisation,
        "vram": {"used_bytes": vram_bytes, "capacity_bytes": 1024 * 1024 * 1024},
        "sms": [{"sm_id": 0, "utilization": utilisation, "busy_warps": 1, "warp_count": 4}],
        "event_log": [{"clock": clock, "message": f"tick {clock}"}],
    }


def test_new_database_can_bootstrap_in_memory():
    store = SessionStore(":memory:")
    assert store.list_sessions() == []
    store.close()


def test_start_and_end_session_persists_metadata(tmp_path):
    db_path = tmp_path / "sessions.sqlite3"
    with SessionStore(db_path) as store:
        session_id = store.start_session(name="unit-test")
        store.end_session(session_id, kernels_seen=3, ticks_observed=10)
        sessions = store.list_sessions()
    assert len(sessions) == 1
    session = sessions[0]
    assert session.session_id == session_id
    assert session.kernels_seen == 3
    assert session.ticks_observed == 10
    assert session.ended_at is not None


def test_write_and_read_snapshots_and_events(tmp_path):
    with SessionStore(tmp_path / "db.sqlite3") as store:
        session_id = store.start_session(name="roundtrip")
        for clock in range(3):
            store.record_snapshot(
                clock=clock,
                overall_utilization=0.25 * (clock + 1),
                vram_used_bytes=1024 * clock,
                snapshot=_fabricate_snapshot(clock, 0.25 * (clock + 1), 1024 * clock),
            )
            store.record_event(clock, f"event {clock}")
        snapshots = list(store.iter_snapshots(session_id))
        events = store.events_for(session_id)

    assert [row.clock for row in snapshots] == [0, 1, 2]
    assert snapshots[1].overall_utilization == pytest.approx(0.5)
    assert events == [(0, "event 0"), (1, "event 1"), (2, "event 2")]


def test_record_without_active_session_raises():
    store = SessionStore(":memory:")
    try:
        with pytest.raises(PersistenceError):
            store.record_event(0, "x")
    finally:
        store.close()


def test_kernel_submission_roundtrip():
    with SessionStore(":memory:") as store:
        session_id = store.start_session(name="kern")
        store.record_kernel_submission(
            clock=5,
            kernel_name="vector_add",
            profile="compute",
            trigger="mouse_click",
            grid_size=4,
            block_size=64,
            vram_bytes=2048,
        )
        submissions = store.submissions_for(session_id)
    assert len(submissions) == 1
    assert submissions[0]["kernel_name"] == "vector_add"
    assert submissions[0]["profile"] == "compute"
    assert submissions[0]["trigger"] == "mouse_click"


def test_close_auto_ends_active_session(tmp_path):
    store = SessionStore(tmp_path / "auto-end.sqlite3")
    session_id = store.start_session(name="auto")
    store.close()

    reopened = SessionStore(tmp_path / "auto-end.sqlite3")
    try:
        sessions = {meta.session_id: meta for meta in reopened.list_sessions()}
        assert sessions[session_id].ended_at is not None
    finally:
        reopened.close()
