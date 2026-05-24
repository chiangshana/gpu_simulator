"""gpu_simulator — A desktop virtual-GPU visualization widget.

Public API re-exports the most commonly used types so users can simply do::

    from gpu_simulator import GPU, Kernel, AppConfig, SessionStore, load_config
"""

from gpu_simulator.bridge import CPUGPUBridge, TraceLog, TraceRow, kernel_name_for_id
from gpu_simulator.config import AppConfig, load_config, save_config
from gpu_simulator.core import GPU, StreamingMultiprocessor, Warp, WarpState
from gpu_simulator.cpu import CPU, AssemblerError, CycleResult, Instruction, Opcode, assemble
from gpu_simulator.exceptions import (
    ConfigError,
    GPUError,
    GPUVizError,
    KernelSubmissionError,
    PersistenceError,
    RealGPUUnavailableError,
    VRAMOverflowError,
)
from gpu_simulator.exporter import SessionExporter
from gpu_simulator.kernel import Kernel, KernelLibrary
from gpu_simulator.memory import VRAM, RegisterFile, SharedMemory
from gpu_simulator.persistence import SessionMeta, SessionStore, SnapshotRow
from gpu_simulator.real_gpu import RealGPUSample, RealGPUSampler

__all__ = [
    "AppConfig",
    "AssemblerError",
    "CPU",
    "CPUGPUBridge",
    "ConfigError",
    "CycleResult",
    "GPU",
    "GPUError",
    "GPUVizError",
    "Instruction",
    "Kernel",
    "KernelLibrary",
    "KernelSubmissionError",
    "Opcode",
    "PersistenceError",
    "RealGPUSample",
    "RealGPUSampler",
    "RealGPUUnavailableError",
    "RegisterFile",
    "SessionExporter",
    "SessionMeta",
    "SessionStore",
    "SharedMemory",
    "SnapshotRow",
    "StreamingMultiprocessor",
    "TraceLog",
    "TraceRow",
    "VRAM",
    "VRAMOverflowError",
    "Warp",
    "WarpState",
    "assemble",
    "kernel_name_for_id",
    "load_config",
    "save_config",
]

__version__ = "0.10.0"
