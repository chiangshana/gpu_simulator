# 期末專題提案書 · GPU Simulator

> 商管程式設計 114-2 期末專題 · 蔣 Shana · `chiangshana@gmail.com`

---

## 一句話定位

**互動式 CPU↔GPU 視覺化教學模擬器 + 個人電腦硬體儀表板** — 把計算機架構課本
裡那些抽象的「register changes」「kernel dispatch」「warp pipeline」概念,
用中文桌面 widget + 真的可以跑的 Tiny8 ASM 變成**看得見、可以操作、可以重來**
的東西;**同一個視窗**還能看自己電腦當下 N 顆 CPU 核心 + 真實 GPU 在幹嘛,
**模擬世界跟真實世界並排比對**。

## 三大支柱

| 支柱 | 主要分頁 | 你會看到 |
| ---- | ---- | ---- |
| ① **模擬層**(教學核心) | 🌡️ 狀態熱圖、🎬 Cycle Cinema、即時 / Trace | 寫 Tiny8 ASM → 看 cycle-by-cycle 暫存器/記憶體/SREG 熱圖、8 顆 SM × 4 warps 平行跑 |
| ② **教學體驗** | 課堂、考考你、AI 解釋、實驗報告 | 中文 5 課教學、互動 quiz、Claude API 解釋 trace、自動產 Markdown 報告 |
| ③ **真實硬體** | 💻 真實硬體 | 你電腦現在 N 顆邏輯 CPU 核心每顆即時負載、頻率、處理程序數;NVIDIA GPU 利用率/記憶體/溫度/功耗 |
| **論述具象化**(第 13 輪) | 🪞 對照鏡 | **第一分頁就是這張**:模擬 GPU 8 SM(左)vs 真實 CPU N 核(右)並排,一鍵觸發模擬工作負載,看左邊飆高、右邊不動,瞬間理解兩個世界的關係 |

---

## 動機(Motivation)

### 痛點一:教材太抽象

大學「計算機概論」「微處理器原理」「平行計算」這幾門課,核心都圍繞著
**CPU 怎麼派工作給 GPU**「每個 cycle 暫存器怎麼變」「8 顆 SM 怎麼平行跑」,
但教材幾乎都是**靜態投影片 + 課本圖**,看完還是不知道實際在發生什麼。

### 痛點二:既有工具門檻高

開源 simulator(NVIDIA PTX visualizer、gem5)門檻太高、英文介面、要 build C++、
看 trace 也是純文字 — 對**初學者**的入門曲線太陡。

### 痛點三:模擬跟真實是兩個世界

教學模擬器跟 Windows 工作管理員 / nvidia-smi **永遠分開兩個視窗**。
看模擬器的時候,學生無從對照「我電腦的 24 核 CPU 現在在做什麼」「我那張
RTX GPU 利用率多少」— 兩個世界拼不起來。

### 我的解法

做一個**純 Python、中文介面、桌面 widget 形式**的工具,涵蓋三件事:

1. **模擬層** — 寫 Tiny8 ASM、按 Run、看 cycle-by-cycle 暫存器/記憶體變化熱圖
2. **教學體驗** — 5 課中文教學、AI 解釋器、自動 Markdown 報告、寵物進化鼓勵長期使用
3. **真實硬體層**(本輪新增) — **同一個視窗**看自己機器當下:
   - N 顆邏輯 CPU 核心,每顆即時利用率(從綠到紅變色 bar)
   - CPU 頻率、處理程序總數
   - 真實 GPU(NVIDIA 透過 pynvml):利用率 / 記憶體 / 溫度 / 功耗

把抽象的「課本」變成具象的「實驗台」,還能即時跟自己的**真實電腦並排對照** —
這就是這個專案的存在意義。

---

## 使用者(Persona)

| 屬性 | 描述 |
| ---- | ---- |
| 主要使用者 | 修「計算機概論」「微處理器原理」「組合語言」課的大學部學生 |
| 次要使用者 | 助教 / 教授(用「電影模式」直接錄一段 60 秒展示影片配進投影片) |
| 程度假設 | 知道什麼是暫存器、知道組合語言大概長怎樣;**不需要**知道 PTX / CUDA |
| 環境假設 | Windows / Mac,Python 3.10+,有桌面螢幕 |

---

## 核心使用流程(Primary Use Cases)

### 用例 A:教學模擬 — 「R16 跟 0x60 這塊記憶體在這 200 個 cycle 內怎麼變」

1. **啟動** — `pip install -e .` 之後執行 `gpu-simulator`,桌面右下角出現一個半透明 widget
2. **切到 🌡️ 狀態熱圖分頁** — 看到左半邊是 ASM 編輯器,預設裝了一支示範程式
3. **改 ASM** — 寫一段自己的 Tiny8 組語(LDI / ADD / MUL / RJMP / CALL / RET …)
4. **按 ▶️ Run** — 右半邊立刻出現三層 matplotlib 熱圖:
   - 上層:SREG 8 個旗標位(I T H S V N Z C),亮 = 1、暗 = 0
   - 中層:R0–R31 全部 32 個暫存器,熱度 = 0..255 的值
   - 下層:記憶體 0x60–0x7F,熱度 = 該位址當下儲存的 byte
   - x 軸 = step(cycle 編號)
5. **拖時間軸 slider** — 白色游標線在三層同步移動,下方狀態列即時顯示
   `Step / PC / SP / 當前指令 / SREG / R0–R7 值`
6. **想看 GPU 端互動?** — 切到 🎬 Cycle Cinema 分頁,看 CPU 跟 GPU 同框並排
   播,每個 cycle 都有中文導讀

### 用例 B:真實硬體儀表板 — 「我這台筆電現在 N 顆核心忙不忙?」

1. **切到 💻 真實硬體分頁** — 模擬器同一個視窗就能看
2. **CPU 區塊** — 自動偵測你的邏輯核心數(可能 8 / 16 / 24…),每顆畫一條
   bar,從綠(idle)→ 黃 → 橘 → 紅(忙爆)即時變色,每秒更新
3. **CPU 摘要** — 顯示「24 邏輯核心(實體 12)· 4200MHz · 整體 35% · 281 個處理程序」
4. **GPU 區塊** — 自動偵測 NVIDIA(pynvml / GPUtil)後端,顯示利用率 / 記憶體
   used/total / 溫度 / 功耗;沒有 NVIDIA GPU 也不會崩,顯示降級訊息
5. **對照學習** — 跟 🌡️ 狀態熱圖並列開兩個視窗,可以**親眼比對**「模擬器的 8 顆
   SM 跑 kernel」跟「我電腦真實的 12 顆 P-core 跑工作管理員」是同樣的概念

兩個用例都在**同一個視窗、不換工具、可以隨時暫停**的情況下完成 — 這是 PTX
visualizer / gem5 / 工作管理員都做不到的事。

---

## 次要功能(教學體驗加分包)

這些**不是核心**,但提升使用樂趣與教學互動性,適合長期使用:

| 類別 | 功能 | 為什麼有意義 |
| ---- | ---- | ---- |
| 教學深化 | AI 解釋器、5 課中文教學、考考你 | 把 trace 翻成中文白話 |
| 自動化 | 60 秒電影模式、自動 Markdown 實驗報告、Web 鏡像 | 老師錄影 / 學生交報告 |
| 進階概念 | warp divergence 視覺化、memory coalescing、L1 cache、Roofline | 更深的課程主題 |
| 遊戲化 | 寵物五階進化、成就系統、每日挑戰、心情日記、彩蛋 | 鼓勵長期使用 |
| 觀感 | 粒子特效、Matrix code rain、4 種主題、TTS 旁白 | 演示時眼前一亮 |

---

## 系統架構(Module Map)

```text
src/gpu_simulator/
│
├── 核心引擎(模擬層 — 無 GUI 相依)
│   ├── core.py          GPU / StreamingMultiprocessor / Warp / WarpState
│   ├── cpu.py           Tiny8 子集 CPU + assembler
│   ├── memory.py        VRAM / RegisterFile / SharedMemory
│   ├── kernel.py        Kernel / KernelLibrary
│   ├── bridge.py        基礎 CPU↔GPU bridge
│   ├── full_bridge.py   完整 Tiny8 ISA ↔ GPU bridge(60+ 指令)
│   └── tiny8_full/      vendored Tiny8(MIT license)
│
├── 教育核心(本專題的賣點)
│   ├── cpu_heatmap.py   🌡️ CPU 狀態時間熱圖(SREG / R0–R31 / mem)
│   ├── commentary.py    每行 ASM 的中文解說
│   ├── real_gpu.py      pynvml/GPUtil 後端 — NVIDIA GPU 取樣
│   └── real_hardware.py 💻 真實硬體儀表板(psutil per-core CPU + GPU)
│
├── 視覺化(matplotlib + Qt)
│   ├── visualizer.py    14 個 sub-widget:Analytics / Trace / Heatmap /
│   │                    Sequence / MemoryMap / 3D / Cycle Cinema …
│   └── widget.py        主視窗,整合所有分頁
│
├── 教學體驗
│   ├── lessons.py       5 課中文教學
│   ├── quiz.py          考考你
│   ├── ai_explainer.py  Claude API 解釋器(optional,有 offline fallback)
│   └── lab_report.py    自動 Markdown 報告
│
├── 互動 & 遊戲化
│   ├── gpu_pet.py       🥚→🐲 五階進化寵物
│   ├── achievements.py  成就追蹤
│   ├── challenges.py    每日挑戰 + 排行榜
│   ├── mood_calendar.py 心情日記月曆熱圖
│   └── easter_eggs.py   Konami code + 魔法字
│
├── 視覺特效
│   ├── particle_fx.py   粒子煙火
│   ├── code_rain.py     Matrix code rain
│   ├── sounds.py        多音 chord
│   ├── tts.py           中文語音
│   ├── cinematic.py     60 秒劇本式 showcase
│   ├── recorder.py      GIF 錄影
│   └── themes.py        4 種主題
│
├── UX(第十二輪)
│   ├── toast.py         滑入式通知
│   ├── command_palette.py  Ctrl+Shift+P 命令面板
│   └── status_bar.py    底部即時狀態列
│
├── 基礎設施
│   ├── config.py        AppConfig + 載入/存檔
│   ├── persistence.py   SessionStore(SQLite)
│   ├── exceptions.py    自訂例外階層(11 個)
│   ├── i18n.py          中文字串資源
│   └── event_listener.py  捕捉滑鼠 / 鍵盤,把使用者行為投射成 GPU 工作
│
└── 整合
    ├── cli.py           gpu-simulator 命令列入口
    ├── plugins.py       使用者外掛載入
    ├── kernel_dsl.py    高階 DSL → Tiny8 編譯器
    ├── profiler.py      per-kernel 計時 + Roofline
    ├── real_gpu.py      可選 pynvml/GPUtil 接真實 GPU
    ├── web_mirror.py    stdlib http.server 鏡像
    └── multi_gpu.py     雙 GPU + NVLink 模擬
```

**分層原則:** 上面三層(核心引擎、教育核心、視覺化)**沒有跨層依賴**;測試
可以單獨跑模擬層而不啟動 Qt。

---

## 課程作業需求對照表

> 6 大進階技術,每一項都點到具體檔案/類別作為證據。

### 1. 善用 class(物件導向設計)

| 統計 | 數量 |
| ---- | ---- |
| **`class` 定義總數** | **172** 個(不含 vendored Tiny8) |
| `@dataclass` 數量 | 80 個(以 `frozen=True` 表達 immutable value object) |
| 繼承自定 Exception 的類別 | 11 個 |
| 繼承 PySide6 QWidget 的類別 | 30+ 個 |

**代表性類別舉例:**

| 領域 | 類別 | 檔案 |
| ---- | ---- | ---- |
| 模擬引擎 | `GPU`、`StreamingMultiprocessor`、`Warp` | [src/gpu_simulator/core.py](src/gpu_simulator/core.py) |
| Tiny8 CPU | `CPU`、`Instruction`、`Opcode` | [src/gpu_simulator/cpu.py](src/gpu_simulator/cpu.py) |
| 寵物進化 | `GPUPetWidget`、`PetStage`、`PetMood` | [src/gpu_simulator/gpu_pet.py](src/gpu_simulator/gpu_pet.py) |
| Toast 通知 | `ToastManager`、`ToastSpec`、`ToastLevel` | [src/gpu_simulator/toast.py](src/gpu_simulator/toast.py) |
| 命令面板 | `Command` | [src/gpu_simulator/command_palette.py](src/gpu_simulator/command_palette.py) |
| 心情日記 | `MoodLog`、`DayMood` | [src/gpu_simulator/mood_calendar.py](src/gpu_simulator/mood_calendar.py) |
| 彩蛋偵測器 | `EasterEggDetector` | [src/gpu_simulator/easter_eggs.py](src/gpu_simulator/easter_eggs.py) |
| 熱圖資料層 | `CPUStateHistory` | [src/gpu_simulator/cpu_heatmap.py](src/gpu_simulator/cpu_heatmap.py) |
| 持久層 | `SessionStore`、`AchievementStore`、`LeaderboardStore` | [persistence.py](src/gpu_simulator/persistence.py) / [achievements.py](src/gpu_simulator/achievements.py) / [challenges.py](src/gpu_simulator/challenges.py) |

### 2. 進階資料結構

| 結構 | 用途 | 代表檔案 |
| ---- | ---- | ---- |
| `@dataclass(frozen=True)` | 80 處 — 表達 immutable value object | 全專案 |
| `collections.deque` | trace log ring buffer | [bridge.py](src/gpu_simulator/bridge.py) / [full_bridge.py](src/gpu_simulator/full_bridge.py) |
| `Enum` | `Opcode` / `WarpState` / `ToastLevel` / `CinemaActionKind` | [cpu.py](src/gpu_simulator/cpu.py) / [core.py](src/gpu_simulator/core.py) |
| `tuple` of `dataclass` | `CinemaScript.actions`、`CPUStateHistory.registers` | [cinematic.py](src/gpu_simulator/cinematic.py) / [cpu_heatmap.py](src/gpu_simulator/cpu_heatmap.py) |
| 2D matrix(list-of-list) | 熱圖矩陣、Life board | [cpu_heatmap.py](src/gpu_simulator/cpu_heatmap.py) / [asm_games.py](src/gpu_simulator/asm_games.py) |

### 3. 檔案 I/O

| 用途 | 檔案 | 格式 |
| ---- | ---- | ---- |
| 設定檔載入/存檔 | [config.py](src/gpu_simulator/config.py) | JSON |
| Session export | [exporter.py](src/gpu_simulator/exporter.py) | JSON + CSV |
| 自動實驗報告 | [lab_report.py](src/gpu_simulator/lab_report.py) | Markdown + PNG |
| ASM 檔案載入 | [full_bridge.py](src/gpu_simulator/full_bridge.py) `assemble_file()` | .asm 純文字 |
| GIF 錄影 | [recorder.py](src/gpu_simulator/recorder.py) | GIF |
| CLI 子指令 `run` | [cli.py](src/gpu_simulator/cli.py) | stdin/stdout/file |

### 4. 例外處理(custom exception hierarchy)

`src/gpu_simulator/exceptions.py` 定義了完整的例外階層:

```python
GPUVizError                  # 共同 base
├── ConfigError              # 設定檔錯誤
├── GPUError                 # GPU 相關
│   ├── KernelSubmissionError    # kernel 派送失敗
│   └── VRAMOverflowError        # VRAM 滿
├── PersistenceError         # SQLite 寫失敗
├── RealGPUUnavailableError  # 沒有真實 GPU
└── AssemblerError(cpu.py)   # ASM 組譯失敗
```

加上 23 個檔案有 `try/except` 區塊,常見 pattern:

- `contextlib.suppress(Exception)` — UI 端的 fail-soft(toast 即使例外也不該崩 widget)
- 自訂 `raise GPUVizError(...) from exc` — 把底層例外包裝成領域語意

### 5. GUI(PySide6 / Qt for Python)

- 主視窗 [widget.py](src/gpu_simulator/widget.py) — 2,400+ 行,15 個分頁,12 顆工具列鈕
- 14 個自訂 sub-widget 在 [visualizer.py](src/gpu_simulator/visualizer.py)
- matplotlib FigureCanvasQTAgg 嵌入 — [cpu_heatmap.py](src/gpu_simulator/cpu_heatmap.py)、analytics chart
- 自訂 QPropertyAnimation:toast 淡入淡出、寵物 wiggle、Cycle Cinema 慢動作
- 全域 QShortcut:Ctrl+Shift+P 命令面板、Ctrl+M 心情日記、Ctrl+Shift+E 改名…

### 6. 資料庫(SQLite,stdlib `sqlite3`)

| 資料表 | 模組 | 用途 |
| ---- | ---- | ---- |
| `sessions` / `snapshots` | [persistence.py](src/gpu_simulator/persistence.py) | 每次跑模擬都存一筆 session,可以重播 |
| `achievements_unlocked` | [achievements.py](src/gpu_simulator/achievements.py) | 解鎖記錄 |
| `leaderboard` | [challenges.py](src/gpu_simulator/challenges.py) | 每日挑戰排名 |
| `mood_log` | [mood_calendar.py](src/gpu_simulator/mood_calendar.py) | 每天的 GPU 平均負載 + 評語 |
| `config_kv` | [config.py](src/gpu_simulator/config.py) | 鍵值對設定 |

全部用 `with sqlite3.connect(...) as conn:` 確保連線正確關閉;DDL 用
`CREATE TABLE IF NOT EXISTS` 自動 migrate。

---

## PEP 8 合規證明

### 工具設定([pyproject.toml](pyproject.toml))

```toml
[tool.ruff]
line-length = 110            # 中文 docstring 多,110 是務實折衷
target-version = "py310"
extend-exclude = ["src/gpu_simulator/tiny8_full"]   # 第三方 vendored 不算

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]
```

選用的規則組:

- `E`, `W` — pycodestyle(就是 PEP 8 本身)
- `F` — pyflakes(unused imports / undefined name)
- `I` — isort(import 排序)
- `N` — pep8-naming(類別 CamelCase、函式 snake_case)
- `UP` — pyupgrade(自動升級到較新語法)
- `B`, `C4`, `SIM` — bugbear / comprehensions / simplify

### 通過證明

```bash
$ python -m ruff check src/gpu_simulator
All checks passed!
```

### 測試覆蓋

```bash
$ python -m pytest -q
289 passed in ~15s
```

| 測試檔 | 案例數 | 覆蓋面 |
| ---- | ---- | ---- |
| `test_round12_ux.py` | 36 | toast / palette / status_bar / mood / eggs / heatmap |
| `test_round11_spectacle.py` | 17 | particles / code rain / cinema / TTS |
| `test_round10_modules.py` | 30+ | plugins / cache / profiler / kernel DSL / themes |
| `test_round9_modules.py` | 25+ | AI / web mirror / leaderboard / lab report |
| `test_cpu.py`、`test_memory.py`、`test_core.py` 等 | 150+ | 模擬引擎單元測試 |

---

## 程式規模統計

| 指標 | 數值 |
| ---- | ---- |
| 自有 Python 檔案 | 48 |
| 自有程式碼行數(含 docstring) | **16,985** |
| 類別定義 | **172** |
| `@dataclass` | 80 |
| 自訂例外類別 | 11 |
| QWidget 子類 | 30+ |
| 測試案例 | **289**(全綠) |
| Ruff lint 問題 | **0** |

---

## 為什麼這個專案符合期末作業要求

| 作業要求 | 本專題如何達成 |
| ---- | ---- |
| 100% 使用 Python | 對。**除了 vendored Tiny8**(MIT 第三方,明確標記)外全部 Python。沒有 C/Rust extension。 |
| 結構明確、善用 class | 172 個類別、80 個 dataclass、11 層例外階層、明確的「模擬層 / 視覺化層 / UX 層」三層分離。 |
| 遵循 PEP 8 | ruff 設定齊全、自動 CI 風格檢查、目前 0 issues。 |
| 6 大進階技術 | class ✓ 進階資料結構 ✓ 檔案 I/O ✓ 例外處理 ✓ GUI ✓ 資料庫 ✓ — 每一項都有對照表 + 檔案連結。 |
| 有教育意義 / 有實用價值 | 解決「計算機架構教材太抽象」這個真實的學習痛點;桌面 widget 可以隨時開、不需要架伺服器、不需要硬體。 |
| 規模適中 | 16,985 行、48 個模組、289 個測試 — 對「期末專題」來說規模偏大,但每塊都對應一個明確需求。 |
