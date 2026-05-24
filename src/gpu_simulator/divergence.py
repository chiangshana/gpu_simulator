"""進階 GPU 概念示範:warp divergence + memory coalescing。

這支模組純 Python(沒 Qt),負責**模擬 + 統計**:給一個「kernel 描述符」
(每條 thread 走哪條分支、每條 thread 讀哪個記憶體位址),回傳教學用的
分析結果(divergence 比例、coalesced ratio、預估的 cycle 數)。

UI 端在 :mod:`gpu_simulator.visualizer` 另寫 :class:`DivergenceView` 來把這份
資料畫成圖。

兩個核心觀念:

- **Warp divergence**:一個 warp 的 32 條 thread 在 GPU 是 lockstep 執行,
  如果條件分支讓不同 thread 走不同 path,GPU 會逐 path 序列執行,
  divergence 越多 → 真實效能越差。
- **Memory coalescing**:32 條 thread 同時讀記憶體,如果讀的位址連續(或同一條 cache line),
  GPU 一次 transaction 就搞定;如果四散,要分多次 transaction,延遲拉長。
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

WARP_SIZE = 32  # threads per warp (real GPU; tutorial value)
COALESCED_LINE_BYTES = 32  # 一條 cache line 寬度(教學用簡化)


# ---------------------------------------------------------------------------
# Warp divergence
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DivergenceAnalysis:
    """Warp 分支發散分析結果。"""

    branch_paths: tuple[tuple[int, ...], ...]  # 每個 path 的 thread id list
    diverged: bool
    divergence_factor: float  # 1.0 = 沒發散;n = 真實要跑 n 個 path
    estimated_cycles: int
    chinese_explanation: str


def analyze_branch(
    branch_decisions: Sequence[int], base_cycles: int = 4
) -> DivergenceAnalysis:
    """``branch_decisions`` 長度應該是 :data:`WARP_SIZE` 或更短(會自動截尾)。

    每個元素代表那條 thread 選的 path id(0, 1, 2, ...)。
    回傳:多少個 unique path、divergence factor、估計 cycle 數。
    """
    decisions = list(branch_decisions)[:WARP_SIZE]
    if not decisions:
        return DivergenceAnalysis(
            branch_paths=(),
            diverged=False,
            divergence_factor=1.0,
            estimated_cycles=0,
            chinese_explanation="(空 warp)",
        )
    paths_dict: dict[int, list[int]] = {}
    for thread_id, path_id in enumerate(decisions):
        paths_dict.setdefault(path_id, []).append(thread_id)
    paths = tuple(tuple(threads) for threads in paths_dict.values())
    unique_paths = len(paths)
    diverged = unique_paths > 1
    divergence_factor = float(unique_paths)
    estimated = base_cycles * unique_paths
    if not diverged:
        explanation = (
            "✅ 沒有發散:整個 warp 32 條 thread 走同一條路徑,"
            f"GPU 用 {base_cycles} cycle 一次解決。"
        )
    else:
        explanation = (
            f"⚠️ 發散!warp 內被切成 {unique_paths} 條路徑,"
            f"GPU 必須序列跑每一條 → 預估要 {estimated} cycle"
            f"({base_cycles} × {unique_paths},比理想多 {(unique_paths - 1) * base_cycles})。"
        )
    return DivergenceAnalysis(
        branch_paths=paths,
        diverged=diverged,
        divergence_factor=divergence_factor,
        estimated_cycles=estimated,
        chinese_explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Memory coalescing
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CoalescingAnalysis:
    """memory access pattern 分析結果。"""

    addresses: tuple[int, ...]
    distinct_lines: int
    coalesced_ratio: float
    transactions: int
    chinese_explanation: str


def analyze_memory_access(
    addresses: Sequence[int],
    line_size_bytes: int = COALESCED_LINE_BYTES,
) -> CoalescingAnalysis:
    """``addresses`` 是 32 條 thread 各自要讀的 byte 位址。

    結果:不同 cache line 的數量(transactions)= 較少越好。
    coalesced_ratio = 1.0 / transactions,越接近 1 越好。
    """
    addresses = list(addresses)[:WARP_SIZE]
    if not addresses:
        return CoalescingAnalysis(
            addresses=(),
            distinct_lines=0,
            coalesced_ratio=1.0,
            transactions=0,
            chinese_explanation="(空 access)",
        )
    distinct_lines = {addr // line_size_bytes for addr in addresses}
    transactions = len(distinct_lines)
    threads_count = len(addresses)
    coalesced_ratio = 1.0 / transactions if transactions else 1.0

    if transactions == 1:
        explanation = (
            "✅ 完美 coalesced:32 條 thread 都讀同一條 cache line,"
            "GPU 一次 transaction 搞定,記憶體頻寬全發揮。"
        )
    elif transactions <= max(2, threads_count // 16):
        explanation = (
            f"🟡 部分 coalesced:32 條 thread 觸到 {transactions} 條 cache line,"
            f"GPU 要做 {transactions} 次 transaction(大致還可接受)。"
        )
    else:
        explanation = (
            f"❌ 嚴重 uncoalesced:32 條 thread 觸到 {transactions} 條 cache line!"
            f"GPU 要做 {transactions} 次 transaction,記憶體頻寬只用到 1/{transactions}。"
            "建議重新安排資料布局,讓相鄰 thread 讀相鄰位址。"
        )
    return CoalescingAnalysis(
        addresses=tuple(addresses),
        distinct_lines=transactions,
        coalesced_ratio=coalesced_ratio,
        transactions=transactions,
        chinese_explanation=explanation,
    )


# ---------------------------------------------------------------------------
# 預設範例:讓 UI 一打開就有東西可看
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DivergencePreset:
    name: str
    chinese_description: str
    branch_decisions: tuple[int, ...]


@dataclass(frozen=True)
class CoalescingPreset:
    name: str
    chinese_description: str
    addresses: tuple[int, ...]


def builtin_divergence_presets() -> tuple[DivergencePreset, ...]:
    return (
        DivergencePreset(
            name="all_same",
            chinese_description="32 條 thread 全部走 path 0(理想 SIMD)",
            branch_decisions=tuple(0 for _ in range(WARP_SIZE)),
        ),
        DivergencePreset(
            name="two_way",
            chinese_description="奇偶分流:奇數 thread 走 path 0,偶數走 path 1",
            branch_decisions=tuple(thread_id % 2 for thread_id in range(WARP_SIZE)),
        ),
        DivergencePreset(
            name="four_way",
            chinese_description="四分流:依 thread_id mod 4,GPU 必須跑 4 次",
            branch_decisions=tuple(thread_id % 4 for thread_id in range(WARP_SIZE)),
        ),
        DivergencePreset(
            name="worst_case",
            chinese_description="最壞情況:每條 thread 都走自己的 path",
            branch_decisions=tuple(range(WARP_SIZE)),
        ),
    )


def builtin_coalescing_presets() -> tuple[CoalescingPreset, ...]:
    return (
        CoalescingPreset(
            name="coalesced",
            chinese_description="完美:thread t 讀位址 t",
            addresses=tuple(range(WARP_SIZE)),
        ),
        CoalescingPreset(
            name="strided_2",
            chinese_description="跨步 2:thread t 讀位址 2t(穿過 2 條 line)",
            addresses=tuple(thread_id * 2 for thread_id in range(WARP_SIZE)),
        ),
        CoalescingPreset(
            name="strided_8",
            chinese_description="跨步 8:thread t 讀位址 8t(嚴重發散)",
            addresses=tuple(thread_id * 8 for thread_id in range(WARP_SIZE)),
        ),
        CoalescingPreset(
            name="random",
            chinese_description="完全亂讀(模擬 hash table)",
            addresses=tuple(
                ((thread_id * 1103515245 + 12345) >> 4) & 0xFF
                for thread_id in range(WARP_SIZE)
            ),
        ),
    )


def summary(divergence: DivergenceAnalysis, coalescing: CoalescingAnalysis) -> str:
    """組合兩種分析的中文摘要,給 UI 一行字顯示。"""
    parts = []
    if divergence.diverged:
        parts.append(f"⚠️ 發散 {divergence.divergence_factor:.0f}×")
    else:
        parts.append("✅ 無發散")
    if coalescing.transactions <= 1:
        parts.append("✅ 完美 coalesced")
    elif coalescing.transactions <= 4:
        parts.append(f"🟡 {coalescing.transactions} 次 transaction")
    else:
        parts.append(f"❌ {coalescing.transactions} 次 transaction")
    if not divergence.diverged and coalescing.transactions <= 1:
        parts.append("→ GPU 跑得超快")
    return "  ·  ".join(parts)


# Helper for visualizer to draw a per-thread decision/address grid -----------
def thread_to_path_color_index(decisions: Sequence[int], thread_id: int) -> int:
    """0..n-1 colour index for the path the given thread takes."""
    decisions = list(decisions)
    if 0 <= thread_id < len(decisions):
        return decisions[thread_id]
    return 0


def average_addresses_per_line(
    addresses: Sequence[int],
    line_size_bytes: int = COALESCED_LINE_BYTES,
) -> float:
    """Average density on touched cache lines — higher is better."""
    if not addresses:
        return 0.0
    lines: dict[int, int] = {}
    for addr in addresses:
        key = addr // line_size_bytes
        lines[key] = lines.get(key, 0) + 1
    return statistics.fmean(lines.values())
