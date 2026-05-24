"""Custom exception hierarchy for gpu_simulator.

Centralising exception types lets every module speak the same
vocabulary when something goes wrong — UI layers only need to
``except GPUVizError`` to catch anything the project intentionally
raises.

Hierarchy::

    GPUVizError
    ├── GPUError
    │   ├── VRAMOverflowError
    │   └── KernelSubmissionError
    ├── ConfigError
    ├── PersistenceError
    └── RealGPUUnavailableError
"""

from __future__ import annotations


class GPUVizError(Exception):
    """Root of every exception raised intentionally by this package."""


# ---------------------------------------------------------------------------
# simulated GPU problems
# ---------------------------------------------------------------------------
class GPUError(GPUVizError):
    """Any failure originating from the simulated GPU core."""


class VRAMOverflowError(GPUError):
    """Raised when a kernel's allocation request does not fit in VRAM."""

    def __init__(self, requested_bytes: int, free_bytes: int) -> None:
        self.requested_bytes = requested_bytes
        self.free_bytes = free_bytes
        super().__init__(
            f"VRAM overflow: requested {requested_bytes} B, only {free_bytes} B free"
        )


class KernelSubmissionError(GPUError):
    """Raised when a kernel cannot be submitted (e.g. malformed)."""


# ---------------------------------------------------------------------------
# configuration problems
# ---------------------------------------------------------------------------
class ConfigError(GPUVizError):
    """Raised when the user's config file is missing or invalid."""


# ---------------------------------------------------------------------------
# persistence problems
# ---------------------------------------------------------------------------
class PersistenceError(GPUVizError):
    """Raised when the SQLite session store cannot fulfil a request."""


# ---------------------------------------------------------------------------
# real-GPU availability
# ---------------------------------------------------------------------------
class RealGPUUnavailableError(GPUVizError):
    """Raised when the ``--real`` mode is requested but no GPU backend works."""
