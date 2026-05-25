"""Tests for the single-instance TCP lock."""

from __future__ import annotations

from gpu_simulator.single_instance import (
    is_lock_held,
    release_lock,
    try_acquire_lock,
)


def test_acquire_lock_succeeds_when_free():
    sock = try_acquire_lock(port=47880)
    try:
        assert sock is not None
    finally:
        release_lock(sock)


def test_second_acquire_fails_when_held():
    first = try_acquire_lock(port=47881)
    try:
        assert first is not None
        second = try_acquire_lock(port=47881)
        assert second is None
    finally:
        release_lock(first)


def test_release_then_reacquire_succeeds():
    sock1 = try_acquire_lock(port=47882)
    assert sock1 is not None
    release_lock(sock1)

    sock2 = try_acquire_lock(port=47882)
    try:
        assert sock2 is not None
    finally:
        release_lock(sock2)


def test_is_lock_held_returns_false_when_free():
    assert is_lock_held(port=47883) is False


def test_is_lock_held_returns_true_when_held():
    holder = try_acquire_lock(port=47884)
    try:
        assert holder is not None
        assert is_lock_held(port=47884) is True
    finally:
        release_lock(holder)


def test_release_lock_none_is_noop():
    # 不應該拋例外
    release_lock(None)
