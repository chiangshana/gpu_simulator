"""Real-hardware GPU sampler with graceful fallbacks.

Priority order when ``preferred_backend`` is ``"auto"``:

1. :mod:`pynvml`   — NVIDIA NVML bindings; gives util/mem/temp/power.
2. :mod:`GPUtil`   — third-party library, also NVIDIA-only but simpler.
3. No-op sampler   — :meth:`RealGPUSampler.available` returns ``False``.

Every sampler method is wrapped in ``try``/``except`` so a transient
hardware or driver hiccup is surfaced as ``None`` rather than crashing
the whole widget.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Protocol

from gpu_simulator.exceptions import RealGPUUnavailableError


@dataclass(frozen=True)
class RealGPUSample:
    """One reading from the local GPU.  Fields may be ``None`` on partial data."""

    backend: str
    name: str
    utilization_percent: float | None
    memory_used_bytes: int | None
    memory_total_bytes: int | None
    temperature_celsius: float | None
    power_watts: float | None

    def snapshot(self) -> dict:
        return {
            "backend": self.backend,
            "name": self.name,
            "utilization_percent": self.utilization_percent,
            "memory_used_bytes": self.memory_used_bytes,
            "memory_total_bytes": self.memory_total_bytes,
            "temperature_celsius": self.temperature_celsius,
            "power_watts": self.power_watts,
        }


class _Backend(Protocol):
    name: str

    def sample(self) -> RealGPUSample | None: ...

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# pynvml backend
# ---------------------------------------------------------------------------
class _NvmlBackend:
    name = "pynvml"

    def __init__(self) -> None:
        import pynvml  # noqa: F401 - imported to validate availability

        self._pynvml = pynvml
        self._pynvml.nvmlInit()
        if self._pynvml.nvmlDeviceGetCount() == 0:
            self._pynvml.nvmlShutdown()
            raise RealGPUUnavailableError("pynvml reported zero GPUs")
        self._handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)

    def sample(self) -> RealGPUSample | None:
        try:
            utilisation = self._pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            memory = self._pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            raw_name = self._pynvml.nvmlDeviceGetName(self._handle)
            name = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else raw_name
            temperature = self._safe_call(
                lambda: self._pynvml.nvmlDeviceGetTemperature(self._handle, 0)
            )
            power_milliwatts = self._safe_call(
                lambda: self._pynvml.nvmlDeviceGetPowerUsage(self._handle)
            )
        except Exception:
            return None
        return RealGPUSample(
            backend=self.name,
            name=name,
            utilization_percent=float(utilisation.gpu),
            memory_used_bytes=int(memory.used),
            memory_total_bytes=int(memory.total),
            temperature_celsius=float(temperature) if temperature is not None else None,
            power_watts=float(power_milliwatts) / 1000.0
            if power_milliwatts is not None
            else None,
        )

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._pynvml.nvmlShutdown()

    @staticmethod
    def _safe_call(call):
        try:
            return call()
        except Exception:
            return None


# ---------------------------------------------------------------------------
# GPUtil backend (third-party, NVIDIA)
# ---------------------------------------------------------------------------
class _GPUtilBackend:
    name = "GPUtil"

    def __init__(self) -> None:
        import GPUtil  # noqa: F401

        self._gputil = GPUtil
        if not self._gputil.getGPUs():
            raise RealGPUUnavailableError("GPUtil reported zero GPUs")

    def sample(self) -> RealGPUSample | None:
        try:
            gpus = self._gputil.getGPUs()
            if not gpus:
                return None
            gpu = gpus[0]
        except Exception:
            return None
        return RealGPUSample(
            backend=self.name,
            name=gpu.name,
            utilization_percent=float(gpu.load) * 100.0,
            memory_used_bytes=int(gpu.memoryUsed) * 1024 * 1024,
            memory_total_bytes=int(gpu.memoryTotal) * 1024 * 1024,
            temperature_celsius=float(gpu.temperature)
            if gpu.temperature is not None
            else None,
            power_watts=None,
        )

    def close(self) -> None:  # pragma: no cover - nothing to close
        return None


# ---------------------------------------------------------------------------
# top-level sampler
# ---------------------------------------------------------------------------
_BACKENDS_IN_PRIORITY: tuple[type[_Backend], ...] = (_NvmlBackend, _GPUtilBackend)


class RealGPUSampler:
    """Discover and wrap whichever real-GPU backend is available.

    Call :meth:`available` to decide whether to draw the "Real GPU"
    panel at all.  :meth:`sample` may return ``None`` at any point if
    the underlying call fails — callers should treat that as "no fresh
    data" and keep their last reading.
    """

    def __init__(self, preferred_backend: str = "auto") -> None:
        self._backend: _Backend | None = None
        self._selected_name: str = "none"
        self._init_backend(preferred_backend)

    def _init_backend(self, preferred_backend: str) -> None:
        if preferred_backend == "none":
            return
        candidates: list[type[_Backend]]
        if preferred_backend == "pynvml":
            candidates = [_NvmlBackend]
        elif preferred_backend == "gputil":
            candidates = [_GPUtilBackend]
        else:
            candidates = list(_BACKENDS_IN_PRIORITY)
        for backend_cls in candidates:
            try:
                self._backend = backend_cls()
                self._selected_name = backend_cls.name
                return
            except Exception:
                continue

    def available(self) -> bool:
        return self._backend is not None

    @property
    def backend_name(self) -> str:
        return self._selected_name

    def sample(self) -> RealGPUSample | None:
        if self._backend is None:
            return None
        return self._backend.sample()

    def close(self) -> None:
        if self._backend is not None:
            self._backend.close()
            self._backend = None
