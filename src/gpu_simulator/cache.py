"""簡化版 L1 cache 模擬器。

教學目的:讓使用者看到「為什麼資料的記憶體布局影響效能」。

預設參數:8 條 cache lines × 32 byte = 256 byte 容量,direct-mapped。
你寫的每一次記憶體存取都會被分類成 hit / miss / cold(第一次碰到那條 line)。

提供:

- :class:`CacheModel` — 純 Python state machine,沒有 Qt 相依
- :func:`simulate_access_sequence` — 給一串位址,回傳 stats 摘要
- :class:`CacheStats` — 命中率 / miss rate / 各 line 最後內容

不負責 trace 整個 bridge — UI 端可以在 ``OUT 0x40``/``LD``/``ST`` 發生時
喊一聲 :meth:`CacheModel.access`,自動就有資料可看。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum


class AccessKind(Enum):
    HIT = "hit"
    MISS = "miss"
    COLD = "cold"


@dataclass(frozen=True)
class AccessResult:
    address: int
    line_index: int
    tag: int
    kind: AccessKind


@dataclass
class CacheLine:
    valid: bool = False
    tag: int = -1
    last_address: int = -1


@dataclass
class CacheStats:
    accesses: int = 0
    hits: int = 0
    misses: int = 0
    cold_misses: int = 0

    @property
    def hit_rate(self) -> float:
        return self.hits / self.accesses if self.accesses else 0.0

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

    def to_dict(self) -> dict[str, float | int]:
        return {
            "accesses": self.accesses,
            "hits": self.hits,
            "misses": self.misses,
            "cold_misses": self.cold_misses,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
        }


@dataclass
class CacheModel:
    """Direct-mapped L1 cache。

    參數預設值都選教學常用的小數字,讓你能口算驗證。
    """

    line_size_bytes: int = 32
    num_lines: int = 8
    lines: list[CacheLine] = field(init=False)
    stats: CacheStats = field(init=False)
    history: list[AccessResult] = field(init=False)

    def __post_init__(self) -> None:
        self.lines = [CacheLine() for _ in range(self.num_lines)]
        self.stats = CacheStats()
        self.history = []

    @property
    def capacity_bytes(self) -> int:
        return self.line_size_bytes * self.num_lines

    def reset(self) -> None:
        self.lines = [CacheLine() for _ in range(self.num_lines)]
        self.stats = CacheStats()
        self.history.clear()

    def access(self, address: int) -> AccessResult:
        line_index = (address // self.line_size_bytes) % self.num_lines
        tag = address // self.line_size_bytes // self.num_lines
        line = self.lines[line_index]
        self.stats.accesses += 1
        if not line.valid:
            kind = AccessKind.COLD
            self.stats.cold_misses += 1
            self.stats.misses += 1
        elif line.tag != tag:
            kind = AccessKind.MISS
            self.stats.misses += 1
        else:
            kind = AccessKind.HIT
            self.stats.hits += 1
        line.valid = True
        line.tag = tag
        line.last_address = address
        result = AccessResult(
            address=address, line_index=line_index, tag=tag, kind=kind
        )
        self.history.append(result)
        return result

    def line_snapshots(self) -> list[dict]:
        return [
            {
                "line_index": i,
                "valid": line.valid,
                "tag": line.tag,
                "last_address": line.last_address,
            }
            for i, line in enumerate(self.lines)
        ]


# ---------------------------------------------------------------------------
# 工具:跑一連串 access,給教學 demo 用
# ---------------------------------------------------------------------------
def simulate_access_sequence(
    addresses: Iterable[int],
    line_size_bytes: int = 32,
    num_lines: int = 8,
) -> tuple[CacheModel, CacheStats]:
    cache = CacheModel(line_size_bytes=line_size_bytes, num_lines=num_lines)
    for address in addresses:
        cache.access(int(address))
    return cache, cache.stats


# ---------------------------------------------------------------------------
# Built-in 教學情境
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CacheScenario:
    code: str
    name: str
    description: str
    addresses: tuple[int, ...]


def builtin_scenarios() -> tuple[CacheScenario, ...]:
    return (
        CacheScenario(
            code="sequential",
            name="連續存取",
            description="一個一個位址順著讀(理想 spatial locality)",
            addresses=tuple(range(64)),
        ),
        CacheScenario(
            code="strided",
            name="跨步 32",
            description="每次跳 32(剛好等於一條 line),會把 cache 用滿但每次都打到新 line",
            addresses=tuple(offset * 32 for offset in range(16)),
        ),
        CacheScenario(
            code="hot_loop",
            name="熱迴圈",
            description="只在 0x00..0x3F 反覆讀,完美 temporal locality",
            addresses=tuple((step * 7) % 64 for step in range(40)),
        ),
        CacheScenario(
            code="random",
            name="完全亂讀",
            description="隨機跳全 256 byte,模擬 hash table 最壞情況",
            addresses=tuple(((i * 1103515245 + 12345) >> 8) % 256 for i in range(40)),
        ),
    )
