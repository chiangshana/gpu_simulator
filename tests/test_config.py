"""Tests for gpu_simulator.config — JSON load/save and trigger-mapping validation."""

import json

import pytest

from gpu_simulator.config import (
    DEFAULT_TRIGGER_MAPPING,
    AppConfig,
    load_config,
    save_config,
)
from gpu_simulator.exceptions import ConfigError


def test_default_config_is_fully_populated():
    config = AppConfig()
    assert config.gpu.num_sms == 8
    assert config.widget.tick_interval_ms == 100
    assert config.trigger_mapping == DEFAULT_TRIGGER_MAPPING
    assert config.real_gpu.enabled is False


def test_missing_file_returns_defaults(tmp_path):
    config = load_config(tmp_path / "absent.json")
    assert isinstance(config, AppConfig)
    assert config.trigger_mapping == DEFAULT_TRIGGER_MAPPING


def test_invalid_json_raises_config_error(tmp_path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad_path)


def test_non_object_top_level_raises(tmp_path):
    bad_path = tmp_path / "top.json"
    bad_path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad_path)


def test_unknown_kernel_in_trigger_mapping_raises(tmp_path):
    bad_path = tmp_path / "mapping.json"
    bad_path.write_text(
        json.dumps({"trigger_mapping": {"mouse_click": "bogus_kernel"}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(bad_path)
    assert "bogus_kernel" in str(excinfo.value)


def test_trigger_mapping_accepts_nested_form(tmp_path):
    path = tmp_path / "nested.json"
    path.write_text(
        json.dumps({"trigger_mapping": {"mouse_click": {"kernel": "vector_add"}}}),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.trigger_mapping["mouse_click"] == "vector_add"


def test_save_and_reload_roundtrip(tmp_path):
    config = AppConfig()
    config.gpu.num_sms = 16
    config.real_gpu.enabled = True
    config.trigger_mapping["mouse_click"] = "interpolation"

    path = tmp_path / "config.json"
    save_config(config, path)
    reloaded = load_config(path)

    assert reloaded.gpu.num_sms == 16
    assert reloaded.real_gpu.enabled is True
    assert reloaded.trigger_mapping["mouse_click"] == "interpolation"


def test_unknown_top_level_keys_are_ignored(tmp_path):
    path = tmp_path / "extra.json"
    path.write_text(
        json.dumps({"gpu": {"num_sms": 4}, "mystery_section": {"whatever": 1}}),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.gpu.num_sms == 4
