"""Memory subsystems for the virtual GPU.

The simulated memory hierarchy mirrors a real GPU at a high level:

- :class:`VRAM`           global device memory (large, slow)
- :class:`SharedMemory`   on-chip per-SM scratchpad (small, fast)
- :class:`RegisterFile`   per-thread 32-bit registers

Every class exposes a ``snapshot()`` helper that returns a plain
dictionary suitable for rendering in the UI without holding references
to live objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryBlock:
    """A contiguous VRAM allocation belonging to one kernel."""

    owner_kernel: str
    size_bytes: int
    ticks_remaining: int

    def snapshot(self) -> dict:
        return {
            "owner": self.owner_kernel,
            "size_bytes": self.size_bytes,
            "ticks_remaining": self.ticks_remaining,
        }


@dataclass
class VRAM:
    """Global device memory — simulated as a pool of labelled blocks.

    Rather than tracking individual addresses (which is irrelevant for
    visualization), the pool records named allocations together with how
    many simulation ticks they are expected to survive.
    """

    capacity_bytes: int = 256 * 1024 * 1024  # 256 MiB simulated
    blocks: list[MemoryBlock] = field(default_factory=list)

    @property
    def used_bytes(self) -> int:
        return sum(block.size_bytes for block in self.blocks)

    @property
    def free_bytes(self) -> int:
        return max(self.capacity_bytes - self.used_bytes, 0)

    @property
    def utilization(self) -> float:
        if self.capacity_bytes == 0:
            return 0.0
        return self.used_bytes / self.capacity_bytes

    def allocate(self, owner_kernel: str, size_bytes: int, lifetime_ticks: int) -> bool:
        """Reserve ``size_bytes`` for ``owner_kernel``.

        Returns ``True`` if the allocation fit, ``False`` otherwise.
        """
        if size_bytes <= 0 or size_bytes > self.free_bytes:
            return False
        self.blocks.append(
            MemoryBlock(
                owner_kernel=owner_kernel,
                size_bytes=size_bytes,
                ticks_remaining=lifetime_ticks,
            )
        )
        return True

    def tick(self) -> None:
        """Age every block one tick and drop those that expire."""
        for block in self.blocks:
            block.ticks_remaining -= 1
        self.blocks = [block for block in self.blocks if block.ticks_remaining > 0]

    def free_all_for(self, owner_kernel: str) -> None:
        self.blocks = [
            block for block in self.blocks if block.owner_kernel != owner_kernel
        ]

    def snapshot(self) -> dict:
        return {
            "capacity_bytes": self.capacity_bytes,
            "used_bytes": self.used_bytes,
            "free_bytes": self.free_bytes,
            "utilization": self.utilization,
            "blocks": [block.snapshot() for block in self.blocks],
        }


@dataclass
class SharedMemory:
    """Per-SM on-chip scratchpad (e.g. 48 KiB on a real GPU)."""

    capacity_bytes: int = 48 * 1024
    used_bytes: int = 0

    @property
    def utilization(self) -> float:
        if self.capacity_bytes == 0:
            return 0.0
        return min(self.used_bytes / self.capacity_bytes, 1.0)

    def reserve(self, size_bytes: int) -> bool:
        if self.used_bytes + size_bytes > self.capacity_bytes:
            return False
        self.used_bytes += size_bytes
        return True

    def release(self, size_bytes: int) -> None:
        self.used_bytes = max(self.used_bytes - size_bytes, 0)

    def snapshot(self) -> dict:
        return {
            "capacity_bytes": self.capacity_bytes,
            "used_bytes": self.used_bytes,
            "utilization": self.utilization,
        }


class RegisterFile:
    """Register file with ``registers_per_thread`` 32-bit slots per thread.

    A real GPU uses this for kernel-local variables.  For visualization
    we only track an aggregate busy-ratio so the UI can draw a bar.
    """

    def __init__(self, registers_per_thread: int = 64, thread_count: int = 32) -> None:
        self.registers_per_thread = registers_per_thread
        self.thread_count = thread_count
        self._in_use_registers = 0

    @property
    def total_registers(self) -> int:
        return self.registers_per_thread * self.thread_count

    @property
    def utilization(self) -> float:
        if self.total_registers == 0:
            return 0.0
        return self._in_use_registers / self.total_registers

    def reserve(self, registers: int) -> None:
        self._in_use_registers = min(
            self._in_use_registers + registers, self.total_registers
        )

    def release_all(self) -> None:
        self._in_use_registers = 0

    def snapshot(self) -> dict:
        return {
            "registers_per_thread": self.registers_per_thread,
            "thread_count": self.thread_count,
            "in_use": self._in_use_registers,
            "utilization": self.utilization,
        }
