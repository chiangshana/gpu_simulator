"""Config file loader for gpu_simulator.

The config file is a JSON document that describes the GPU shape, the
widget's UI knobs, the event-listener throttles, and — most
importantly — the *trigger mapping* dictionary that tells the runtime
which kernel to emit for each observed user action.

The schema is intentionally forgiving: missing keys fall back to the
built-in defaults so a partial config never crashes the tool.  Invalid
structure, however, raises :class:`~gpu_simulator.exceptions.ConfigError`.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gpu_simulator.exceptions import ConfigError

# ---------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------
DEFAULT_TRIGGER_MAPPING: dict[str, str] = {
    "mouse_click": "vector_add",
    "mouse_move": "interpolation",
    "key_press": "hash",
    "focus_change": "texture_load",
    "page_nav": "page_nav",
    "app_launch": "app_launch",
    "idle": "idle_compression",
}

VALID_KERNEL_NAMES: frozenset[str] = frozenset(
    {
        "vector_add",
        "interpolation",
        "hash",
        "texture_load",
        "page_nav",
        "app_launch",
        "idle_compression",
    }
)


# ---------------------------------------------------------------------------
# config dataclasses — one for each logical section
# ---------------------------------------------------------------------------
@dataclass
class GPUSection:
    num_sms: int = 8
    warps_per_sm: int = 4
    threads_per_warp: int = 32
    vram_capacity_mib: int = 256
    shared_memory_per_sm_kib: int = 48
    registers_per_thread: int = 64
    event_log_size: int = 48


@dataclass
class WidgetSection:
    tick_interval_ms: int = 100
    kernels_per_tick: int = 4
    window_width: int = 380
    window_height: int = 560
    background_alpha: int = 210


@dataclass
class EventListenerSection:
    mouse_move_throttle_seconds: float = 0.4
    idle_threshold_seconds: float = 5.0
    focus_poll_interval_seconds: float = 1.0
    process_poll_interval_seconds: float = 2.0


@dataclass
class PersistenceSection:
    enabled: bool = True
    database_filename: str = "sessions.sqlite3"


@dataclass
class RealGPUSection:
    enabled: bool = False
    preferred_backend: str = "auto"  # "auto" | "pynvml" | "gputil" | "none"
    sample_interval_seconds: float = 1.0


@dataclass
class AppConfig:
    """Top-level config object handed around by the runtime."""

    version: int = 1
    gpu: GPUSection = field(default_factory=GPUSection)
    widget: WidgetSection = field(default_factory=WidgetSection)
    event_listener: EventListenerSection = field(default_factory=EventListenerSection)
    trigger_mapping: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_TRIGGER_MAPPING)
    )
    persistence: PersistenceSection = field(default_factory=PersistenceSection)
    real_gpu: RealGPUSection = field(default_factory=RealGPUSection)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "gpu": asdict(self.gpu),
            "widget": asdict(self.widget),
            "event_listener": asdict(self.event_listener),
            "trigger_mapping": dict(self.trigger_mapping),
            "persistence": asdict(self.persistence),
            "real_gpu": asdict(self.real_gpu),
        }


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
def user_config_dir() -> Path:
    """Return the writable per-user config directory (``~/.gpu_simulator``)."""
    override = os.environ.get("GPU_SIMULATOR_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".gpu_simulator"


def default_config_path() -> Path:
    return user_config_dir() / "config.json"


def bundled_default_config_path() -> Path:
    """Path to the config shipped with the source tree."""
    return Path(__file__).resolve().parent.parent.parent / "configs" / "default.json"


# ---------------------------------------------------------------------------
# load / save
# ---------------------------------------------------------------------------
def load_config(path: Path | str | None = None) -> AppConfig:
    """Load ``path`` (or the user's default config) and return an :class:`AppConfig`.

    Missing file → returns built-in defaults.  Invalid JSON → raises
    :class:`ConfigError`.  Unknown top-level keys are ignored rather
    than rejected so hand-written files are forgiving.
    """
    if path is None:
        candidate = default_config_path()
        if not candidate.exists():
            candidate = bundled_default_config_path()
        path = candidate
    path = Path(path)
    if not path.exists():
        return AppConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a JSON object at the top level")
    return _parse_config_dict(raw)


def save_config(config: AppConfig, path: Path | str | None = None) -> Path:
    """Write ``config`` to ``path`` (default: per-user config path)."""
    path = Path(path) if path is not None else default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(
            json.dumps(config.to_dict(), indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        raise ConfigError(f"could not write config to {path}: {exc}") from exc
    return path


# ---------------------------------------------------------------------------
# internal parsing helpers
# ---------------------------------------------------------------------------
def _parse_config_dict(raw: dict[str, Any]) -> AppConfig:
    config = AppConfig(version=int(raw.get("version", 1)))
    config.gpu = _merge_section(GPUSection, raw.get("gpu"), "gpu")
    config.widget = _merge_section(WidgetSection, raw.get("widget"), "widget")
    config.event_listener = _merge_section(
        EventListenerSection, raw.get("event_listener"), "event_listener"
    )
    config.persistence = _merge_section(
        PersistenceSection, raw.get("persistence"), "persistence"
    )
    config.real_gpu = _merge_section(
        RealGPUSection, raw.get("real_gpu"), "real_gpu"
    )
    trigger_mapping = raw.get("trigger_mapping")
    if trigger_mapping is not None:
        config.trigger_mapping = _parse_trigger_mapping(trigger_mapping)
    return config


def _merge_section(section_cls, raw_section: Any, section_name: str):
    """Return an instance of ``section_cls`` overridden by fields in ``raw_section``."""
    section = section_cls()
    if raw_section is None:
        return section
    if not isinstance(raw_section, dict):
        raise ConfigError(f"config section {section_name!r} must be a JSON object")
    allowed_fields = set(vars(section).keys())
    for key, value in raw_section.items():
        if key not in allowed_fields:
            continue
        setattr(section, key, value)
    return section


def _parse_trigger_mapping(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ConfigError("'trigger_mapping' must be an object of {event: {kernel: ...}}")
    result: dict[str, str] = {}
    for event_name, value in raw.items():
        kernel_name = value.get("kernel") if isinstance(value, dict) else value
        if not isinstance(kernel_name, str):
            raise ConfigError(
                f"trigger_mapping[{event_name!r}] must map to a kernel name string"
            )
        if kernel_name not in VALID_KERNEL_NAMES:
            raise ConfigError(
                f"trigger_mapping[{event_name!r}] references unknown kernel "
                f"{kernel_name!r}. Valid choices: {sorted(VALID_KERNEL_NAMES)}"
            )
        result[event_name] = kernel_name
    return result
