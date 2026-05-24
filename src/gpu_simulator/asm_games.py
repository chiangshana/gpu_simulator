"""ASM 遊戲機 — 真正用 asm + GPU 跑一場 Conway's Game of Life。

設計:
- 8 × 8 的棋盤存在 Tiny8 完整版的 RAM[0x80 .. 0xBF](每 byte 是 0 或 1)
- 每代的演化由 Python(用簡單 numpy-ish 規則)計算
- 計算完直接寫進 :class:`FullTiny8CPU` 的 RAM,**而不是憑空更新 widget 內部狀態**
- 同時為每一列提交一顆 GPU `texture_load` kernel,代表「GPU 渲染這一列」
- 因此 trace、heatmap、cycle cinema 都能正確反映遊戲進度

這樣的設計尊重「真的有跑在 simulator 上」的精神:每一代的記憶體變化跟 kernel
派送都是真實寫進 bridge,任何分頁(Heatmap / Memory Map / Trace)都能看到。

純 Python,沒有 Qt 相依;UI 端在 :mod:`gpu_simulator.visualizer`(下游另寫)
做 8 × 8 棋盤渲染。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gpu_simulator.full_bridge import FullCPUGPUBridge

GRID_BASE_ADDRESS = 0x80
GRID_SIZE = 8  # 8x8 grid
GRID_BYTES = GRID_SIZE * GRID_SIZE
RENDER_KERNEL_ID = 3  # texture_load


# ---------------------------------------------------------------------------
# 棋盤資料(純 Python)
# ---------------------------------------------------------------------------
@dataclass
class LifeBoard:
    """一個 8x8 的 Conway's Life 棋盤。

    儲存:單一 list[int],長度 64,每元素 0 或 1。
    座標:``cells[row * 8 + col]`` — row 0 在最上面。
    """

    cells: list[int] = field(default_factory=lambda: [0] * GRID_BYTES)

    def reset(self) -> None:
        self.cells = [0] * GRID_BYTES

    def seed_glider(self) -> None:
        """經典 glider — 會在 8x8 grid 上斜飛(會繞回因為我們是 wrap 邊界)。"""
        self.reset()
        for row, col in ((0, 1), (1, 2), (2, 0), (2, 1), (2, 2)):
            self.cells[row * GRID_SIZE + col] = 1

    def seed_blinker(self) -> None:
        """三格水平條紋,會週期 2 震盪。"""
        self.reset()
        for row, col in ((3, 2), (3, 3), (3, 4)):
            self.cells[row * GRID_SIZE + col] = 1

    def seed_random(self, seed: int = 42) -> None:
        """偽隨機初始狀態,density ~ 35%。"""
        self.reset()
        accumulator = seed & 0xFFFFFFFF
        for index in range(GRID_BYTES):
            accumulator = (accumulator * 1103515245 + 12345) & 0xFFFFFFFF
            self.cells[index] = 1 if (accumulator >> 16) % 100 < 35 else 0

    def is_alive(self, row: int, col: int) -> bool:
        return bool(self.cells[(row % GRID_SIZE) * GRID_SIZE + (col % GRID_SIZE)])

    def alive_count(self) -> int:
        return sum(self.cells)

    def step(self) -> None:
        """以 wrap-around(toroidal)邊界計算下一代。"""
        new_cells = [0] * GRID_BYTES
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                neighbors = 0
                for delta_row in (-1, 0, 1):
                    for delta_col in (-1, 0, 1):
                        if delta_row == 0 and delta_col == 0:
                            continue
                        if self.is_alive(row + delta_row, col + delta_col):
                            neighbors += 1
                index = row * GRID_SIZE + col
                if self.cells[index] == 1:
                    new_cells[index] = 1 if neighbors in (2, 3) else 0
                else:
                    new_cells[index] = 1 if neighbors == 3 else 0
        self.cells = new_cells

    def snapshot_rows(self) -> list[list[int]]:
        """二維形式(row × col)的 0/1 列表,給 UI 用。"""
        return [
            self.cells[row * GRID_SIZE : (row + 1) * GRID_SIZE]
            for row in range(GRID_SIZE)
        ]


# ---------------------------------------------------------------------------
# 把棋盤跟 simulator 串起來
# ---------------------------------------------------------------------------
LIFE_DRIVER_ASM = """; ASM 驅動 Conway's Life:每代呼叫一次,提交 8 顆 texture_load kernel
; 用全 60+ Tiny8 ISA(完整版分頁才能跑)。
;
; 慣例:r2 是 row 計數器,r0 = render kernel id

    ldi r0, 3              ; 3 = texture_load
    ldi r2, 8              ; 還有 8 列要渲染

render_loop:
    out 0x40, r0           ; KLAUNCH 一顆 texture_load
    dec r2
    brne render_loop

    out 0xFF, r0           ; KWAIT 等 GPU 全部完成

done:
    jmp done
"""


@dataclass
class GameStats:
    generations: int
    alive_cells: int
    kernels_submitted: int
    kernels_completed: int
    cycles_executed: int


class LifeGameRunner:
    """同時更新 Python 端棋盤 + Tiny8 RAM + 派送 GPU kernel 的執行器。

    用法::

        runner = LifeGameRunner()
        runner.seed("glider")
        runner.start_simulator()
        for _ in range(20):
            runner.step_one_generation()
        print(runner.stats())
    """

    def __init__(self, bridge: FullCPUGPUBridge | None = None) -> None:
        self._bridge = bridge or FullCPUGPUBridge()
        self.board = LifeBoard()
        self._generations = 0
        self._driver_loaded = False

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    @property
    def bridge(self) -> FullCPUGPUBridge:
        return self._bridge

    def seed(self, mode: str = "glider") -> None:
        if mode == "blinker":
            self.board.seed_blinker()
        elif mode == "random":
            self.board.seed_random()
        else:
            self.board.seed_glider()
        self._generations = 0
        self._sync_board_to_ram()

    def start_simulator(self) -> None:
        """把 driver asm 載入 bridge,讓 RAM 初始狀態跟棋盤同步。"""
        self._bridge.load_source(LIFE_DRIVER_ASM)
        self._driver_loaded = True
        self._sync_board_to_ram()

    def step_one_generation(self, max_steps_per_render: int = 200) -> GameStats:
        """前進一代 + 跑 driver asm 一次,讓 GPU 也派送 8 顆 kernel。"""
        if not self._driver_loaded:
            self.start_simulator()
        # Python 算下一代
        self.board.step()
        self._generations += 1
        # 寫進 Tiny8 RAM(每個 cycle 的 memory_history 會記錄這個變動)
        self._sync_board_to_ram()
        # 重新載入 driver asm 讓 PC 從頭跑(否則會卡在 jmp done 無限迴圈)
        self._bridge.load_source(LIFE_DRIVER_ASM)
        self._sync_board_to_ram()
        # 跑 asm 直到 KWAIT 解除 + 之後幾個 cycle(跑滿 max_steps 或等到 kwait done)
        self._bridge.run_until_halt(max_steps=max_steps_per_render)
        return self.stats()

    def stats(self) -> GameStats:
        return GameStats(
            generations=self._generations,
            alive_cells=self.board.alive_count(),
            kernels_submitted=self._bridge.gpu.kernels_submitted,
            kernels_completed=self._bridge.gpu.kernels_completed,
            cycles_executed=len(self._bridge.trace),
        )

    def reset(self, mode: str = "glider") -> None:
        self._bridge = FullCPUGPUBridge()
        self.board = LifeBoard()
        self._generations = 0
        self._driver_loaded = False
        self.seed(mode)
        self.start_simulator()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _sync_board_to_ram(self) -> None:
        """直接寫 bridge.cpu.memory(skip CPU 的 ST 路徑,但 bridge 還是會
        在下次 step 把它記進 memory_history)。"""
        cpu_memory = self._bridge.cpu.mem
        for offset, value in enumerate(self.board.cells):
            cpu_memory.write_ram(GRID_BASE_ADDRESS + offset, value, 0)


# ===========================================================================
# Snake game
# ===========================================================================
SNAKE_BASE_ADDRESS = 0xC0   # 棋盤(64 byte,8x8)
SNAKE_SIZE = 8              # 8x8


class Direction:
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


@dataclass
class SnakeStats:
    score: int
    moves: int
    alive: bool
    kernels_submitted: int
    kernels_completed: int


SNAKE_RENDER_ASM = """; Snake 遊戲每 frame 用的 driver:每格活著的格子提交一顆 vector_add。
; 對 GPU 而言代表「畫蛇身的這一塊」。
; 這支跑完就會無限迴圈在 done,主程式必須 reset bridge 換下一 frame。

    ldi r0, 0          ; vector_add id
    out 0x40, r0       ; 派一顆 kernel(代表畫頭)
    out 0x40, r0       ; 再一顆(代表畫身)
    out 0xff, r0       ; KWAIT

done:
    jmp done
"""


class SnakeGameRunner:
    """8x8 Snake;每 step 把目前蛇身寫進 RAM[0xC0..0xFF] 並派 GPU kernel。

    跟 LifeGameRunner 同精神:Python 算邏輯,真實 RAM 寫入 + 派 kernel
    讓所有 trace / heatmap 視覺化都能正確反映遊戲。
    """

    def __init__(self, bridge: FullCPUGPUBridge | None = None) -> None:
        self._bridge = bridge or FullCPUGPUBridge()
        self.snake: list[tuple[int, int]] = [(3, 3), (3, 4), (3, 5)]
        self.direction: tuple[int, int] = Direction.LEFT
        self.food: tuple[int, int] = (5, 5)
        self.alive: bool = True
        self.score: int = 0
        self.moves: int = 0

    @property
    def bridge(self) -> FullCPUGPUBridge:
        return self._bridge

    def reset(self) -> None:
        self._bridge = FullCPUGPUBridge()
        self.snake = [(3, 3), (3, 4), (3, 5)]
        self.direction = Direction.LEFT
        self.food = (5, 5)
        self.alive = True
        self.score = 0
        self.moves = 0
        self._sync_to_ram()

    def set_direction(self, direction: tuple[int, int]) -> None:
        # 防止 180 度反向(會立刻撞自己)
        if (
            self.direction[0] + direction[0] == 0
            and self.direction[1] + direction[1] == 0
        ):
            return
        self.direction = direction

    def step(self) -> SnakeStats:
        if not self.alive:
            return self.stats()
        head = self.snake[0]
        new_head = (
            (head[0] + self.direction[0]) % SNAKE_SIZE,
            (head[1] + self.direction[1]) % SNAKE_SIZE,
        )
        # 撞自己?
        if new_head in self.snake:
            self.alive = False
            return self.stats()

        self.snake.insert(0, new_head)
        self.moves += 1
        if new_head == self.food:
            self.score += 1
            self.food = self._spawn_food()
        else:
            self.snake.pop()  # 沒吃到食物 → 尾巴縮一格

        # 派 GPU kernel 代表畫 frame
        self._bridge.load_source(SNAKE_RENDER_ASM)
        self._sync_to_ram()
        self._bridge.run_until_halt(max_steps=80)
        return self.stats()

    def stats(self) -> SnakeStats:
        return SnakeStats(
            score=self.score,
            moves=self.moves,
            alive=self.alive,
            kernels_submitted=self._bridge.gpu.kernels_submitted,
            kernels_completed=self._bridge.gpu.kernels_completed,
        )

    def board_snapshot(self) -> list[list[int]]:
        """0 = empty, 1 = body, 2 = head, 3 = food."""
        rows = [[0] * SNAKE_SIZE for _ in range(SNAKE_SIZE)]
        for index, (col, row) in enumerate(self.snake):
            rows[row][col] = 2 if index == 0 else 1
        food_col, food_row = self.food
        rows[food_row][food_col] = 3
        return rows

    def _spawn_food(self) -> tuple[int, int]:
        # 把第一個沒被蛇佔的格子當食物(deterministic, 不靠 random)
        snake_set = set(self.snake)
        for offset in range(SNAKE_SIZE * SNAKE_SIZE):
            position = ((self.score * 7 + offset) % SNAKE_SIZE,
                        (self.score * 13 + offset) % SNAKE_SIZE)
            if position not in snake_set:
                return position
        return (0, 0)

    def _sync_to_ram(self) -> None:
        """把目前棋盤(snake + food)寫進 Tiny8 RAM[0xC0..0xFF]。"""
        cpu_memory = self._bridge.cpu.mem
        # 全部清成 0
        for offset in range(SNAKE_SIZE * SNAKE_SIZE):
            cpu_memory.write_ram(SNAKE_BASE_ADDRESS + offset, 0, 0)
        # 寫 snake body
        for index, (col, row) in enumerate(self.snake):
            value = 2 if index == 0 else 1
            cpu_memory.write_ram(
                SNAKE_BASE_ADDRESS + row * SNAKE_SIZE + col, value, 0
            )
        # 食物
        food_col, food_row = self.food
        cpu_memory.write_ram(
            SNAKE_BASE_ADDRESS + food_row * SNAKE_SIZE + food_col, 3, 0
        )
