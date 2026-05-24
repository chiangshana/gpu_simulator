"""Vendored copy of the upstream **Tiny8** project.

Tiny8 is the educational 8-bit CPU simulator that gpu_simulator spun off from.
We embed it under :mod:`gpu_simulator.tiny8_full` (rather than depending on the
PyPI ``tiny8`` package) for two reasons:

1. **Guaranteed availability** — works on brand-new Python releases that
   may not yet have a ``tiny8`` wheel published.
2. **Hooks** — :mod:`gpu_simulator.full_bridge` subclasses :class:`CPU` and
   overrides :meth:`CPU.write_ram` to intercept GPU-port writes; we
   want a stable, in-tree copy to point that subclass at.

The vendored files live verbatim alongside this ``__init__`` and are
covered by the original Tiny8 MIT licence (see ``LICENSE`` next to this
file).  Upstream project: https://github.com/sql-hkr/tiny8
"""

from gpu_simulator.tiny8_full.assembler import (
    AsmResult,
    assemble,
    assemble_file,
    parse_asm,
)
from gpu_simulator.tiny8_full.cpu import (
    CPU,
    SREG_C,
    SREG_H,
    SREG_I,
    SREG_N,
    SREG_S,
    SREG_T,
    SREG_V,
    SREG_Z,
)
from gpu_simulator.tiny8_full.memory import Memory

__all__ = [
    "CPU",
    "Memory",
    "AsmResult",
    "assemble",
    "assemble_file",
    "parse_asm",
    "SREG_C",
    "SREG_H",
    "SREG_I",
    "SREG_N",
    "SREG_S",
    "SREG_T",
    "SREG_V",
    "SREG_Z",
]
