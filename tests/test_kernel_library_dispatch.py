"""Tests for the new KernelLibrary.build() dispatcher and extra kernels."""

import pytest

from gpu_simulator.kernel import KernelLibrary, WorkloadProfile


def test_app_launch_is_memory_heavy():
    kernel = KernelLibrary.app_launch("chrome.exe")
    assert kernel.profile is WorkloadProfile.MEMORY
    assert kernel.vram_bytes >= 8 * 1024 * 1024
    assert kernel.name.startswith("app_launch:")


def test_page_nav_is_mixed_profile():
    kernel = KernelLibrary.page_nav("GitHub — search")
    assert kernel.profile is WorkloadProfile.MIXED
    assert "GitHub" in kernel.name


def test_build_dispatches_to_known_factories():
    for name in (
        "vector_add",
        "interpolation",
        "hash",
        "texture_load",
        "idle_compression",
        "app_launch",
        "page_nav",
    ):
        kernel = KernelLibrary.build(name, trigger="unit-test", hint="hint")
        assert kernel.trigger == "unit-test"


def test_build_rejects_unknown_kernel():
    with pytest.raises(ValueError):
        KernelLibrary.build("bogus_kernel")


def test_build_propagates_hint_into_name_for_hash_and_texture():
    hash_kernel = KernelLibrary.build("hash", hint="a")
    assert "(a)" in hash_kernel.name
    texture_kernel = KernelLibrary.build("texture_load", hint="notepad.exe")
    assert "notepad.exe" in texture_kernel.name
