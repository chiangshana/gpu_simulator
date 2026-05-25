# 需求變更紀錄 (Requirements Changelog)

本文件用於追蹤使用者對 `gpu_simulator` 專案的需求與設計決策,
目的是讓未來的開發工作(包含新的對話 session)都能快速還原脈絡。

格式:每一則需求以「時間 / 摘要 / 詳情 / 設計決策 / 狀態」呈現,
由上而下依時間遞增。

---

## 2026-04-24 · 初始專案啟動

### 初始摘要

使用者希望以 Tiny8(8-bit CPU 模擬器)為靈感,改寫出一個
「桌面上的小工具,模擬本機 GPU 運行並即時視覺化」的 Python 專案。

### 初始詳細需求(使用者原文摘錄)

1. **改寫目標**:用類似 Tiny8 的方式,做出模擬本機 GPU 運作的視覺化小工具,
   可放在桌面,每當使用者執行一個行為時,顯示目前 GPU 運作的情況。
2. **語言與風格**:全部用 Python 撰寫,全面遵循 PEP 8,
   使用有意義的變數名,善用 class,並將程式拆分成多個模組。
3. **文件要求**:附上隨時更新的 `README.md`,
   以及紀錄需求修改歷程的文件(即本檔案)。

### 已鎖定的設計決策

| 決策項目 | 選擇 | 理由 |
| --- | --- | --- |
| GPU 模型類型 | 純模擬(virtual GPU) | 延續 Tiny8 教學精神;跨平台、不限定 NVIDIA |
| GUI 框架 | PySide6(Qt for Python) | 支援無邊框、半透明、always-on-top,桌面 widget 視覺效果佳 |
| 觸發來源 | 作業系統層級事件(滑鼠、鍵盤、前景視窗切換) | 使用者指定選項 (b);做出「桌面寵物」感 |
| 事件攔截套件 | `pynput` + `psutil` | 跨平台;psutil 用於前景程式查詢 |
| 架構分層 | core / memory / scheduler / kernel / event / widget / visualizer / cli | 對應 Tiny8 的 cpu/memory/assembler/visualizer/cli |

### 預計模組清單

```text
src/gpu_simulator/
├── __init__.py
├── core.py            # GPU、SM (Streaming Multiprocessor)、Warp、Thread
├── memory.py          # VRAM、SharedMemory、RegisterFile
├── scheduler.py       # WarpScheduler、Pipeline 階段
├── kernel.py          # Kernel 定義與樣板工作負載
├── event_listener.py  # OS 事件 → Kernel 提交
├── widget.py          # 桌面 QWidget(主容器)
├── visualizer.py      # 子視覺元件(SM 熱圖、VRAM bar、pipeline、log)
└── cli.py             # 入口點
```

### 使用者行為 → GPU 工作負載對應表(初版)

| 使用者行為 | 觸發的模擬 kernel | 大致語意 |
| --- | --- | --- |
| 滑鼠點擊 | `vector_add_kernel` | 小型向量加法,佔用 1-2 個 SM |
| 滑鼠移動(節流) | `interpolation_kernel` | 線性插值,短週期、低佔用 |
| 鍵盤按鍵 | `hash_kernel` | 對按鍵字元做雜湊,佔用中等 |
| 前景視窗切換 | `texture_load_kernel` | 模擬紋理從 RAM 載入 VRAM,高 I/O |
| 閒置 >5 秒 | `idle_compression` | 模擬記憶體壓縮、低功耗 |

### 初期進度狀態

- [x] 需求確認完成
- [x] 專案骨架建立
- [x] 核心模組實作
- [x] UI 實作
- [x] 測試
- [x] README 完成

---

<!-- 新增需求請在此下方追加區段,格式:## YYYY-MM-DD · 摘要 -->

## 2026-04-24 · 對齊「商管程式設計 114-2 期末專案」規格

### 對齊動機

使用者提供了本學期期末專案的 PDF 規格(PBC114-2_project.pdf)。
本專案 `gpu_simulator` 必須完全對齊該文件的硬性要求,以便作為正式繳交標的。

### 規格關鍵條款摘錄

1. **語言限制**:只能使用 Python(若混用 HTML/JS 等會按 Python 比例打折)。
2. **主題自選**:偏工具類需有「圖形介面、資料庫和某種程度的實用價值」。
3. **六項進階技術至少使用 3 項**,書面報告需說明使用場景:
    - 檔案輸入輸出
    - 進階資料結構(set / tuple / datetime / dictionary 合計算 1 項)
    - 例外處理
    - 自定義類別
    - 圖形化介面(必須是 tkinter 或類似函式庫;matplotlib 畫圖不算)
    - 資料庫(可用 PostgreSQL 或 DuckDB / SQLite via Python)
4. **組員**:4–6 人(本專案暫以 5 人預設分工表設計)。
5. **繳交項目與時程**:

    | 項目 | 截止 | 配分 |
    | --- | --- | --- |
    | 計劃書 proposal.md | 5/10 23:59 | 5 |
    | 展示影片 YouTube | 6/1 23:59 | 35 |
    | 書面報告 (≤8 頁 A4 PDF) + 程式碼 | 6/4 23:59 | 30 |
    | 組間互評回饋 | 6/18 23:59 | 5 |
    | 組內互評 | 6/18 之前 | 15 |
    | 家庭展示錄影 | 6/18 23:59 | 10 |

6. **書面報告**:需說明主題、系統設計、演算法、分工;嚴禁整段貼原始碼,
   可用 pseudocode;每位組員需寫簡短心得。
7. **加分**:組間互評每額外 4 組 +1 分;總分上限 105。

### 現行 gpu_simulator 對六項進階技術的覆蓋現況

| 技術 | 現況 | 備註 |
| --- | --- | --- |
| 自定義類別 | 已用 | `GPU / SM / Warp / VRAM / Kernel / WarpScheduler / EventListener / KernelQueue` 等 |
| 進階資料結構 | 已用 | `deque`、`dict`、`dataclass`、`Enum`、`tuple` 都有用 |
| 圖形化介面 | 已用 | PySide6(Qt 類庫,符合「tkinter 或類似」) |
| 檔案輸入輸出 | 待補 | 目前沒有 |
| 例外處理 | 部分 | 只有 `event_listener.py` 有 try/except,未系統化 |
| 資料庫 | 缺 | 工具類 PDF 強烈建議要有 |

### 決議:補到 6/6 全數使用(超過要求的 3 項)

為了同時強化「實用性」並拿滿書面報告分,會追加:

- **資料庫層**(新模組 `persistence.py`):SQLite(Python 內建 `sqlite3`)
  儲存每次 session 的 event log、snapshot 時間序列、kernel 提交記錄。
  - 新增 UI 頁「Session history」:可列出過去 session,選一筆回放。
- **檔案輸入輸出**(新模組 `config.py` + `exporter.py`):
  - `config.json` 讀取使用者自訂的 GPU 參數與「事件 → kernel 對應表」。
  - 匯出 session 為 CSV / JSON / Markdown 報告。
- **系統化例外處理**(新模組 `exceptions.py`):
  - 定義 `GPUError / VRAMOverflowError / KernelSubmissionError / ConfigError / PersistenceError`。
  - 既有模組改為主動 raise + 在邊界統一 catch。

### 追加的功能(提升「實用性」與「功能強度」分數)

- **分析頁**:用 matplotlib 畫利用率 / VRAM / 吞吐時間序列,可匯出 PNG。
- **Session replay**:從 SQLite 讀取歷史 session,依原時序在 UI 重播。
- **真實 GPU 監控對照模式**(`--real` flag):使用 `pynvml`(若機器有 NVIDIA GPU)
  讀取真實 GPU 狀態並並排顯示,突顯「模擬值 vs 實機值」教學對比;
  沒有 NVIDIA 時自動降級只跑純模擬。

### 分工規劃(5 人預設,可於 4–6 人間微調)

| 角色 | 負責模組 | 負責文件 |
| --- | --- | --- |
| 核心工程師 | `core.py` / `memory.py` / `scheduler.py` / `kernel.py` | 書面報告「系統設計 & 演算法」章節 |
| UI 工程師 | `widget.py` / `visualizer.py` | 書面報告「圖形介面」章節 + 展示影片腳本 |
| 資料工程師 | `persistence.py` / `exporter.py` / `config.py` | 書面報告「資料庫 & 檔案 I/O」章節 |
| 平台工程師 | `event_listener.py` / 多 OS 相容測試 | 書面報告「例外處理 & 可靠度」章節 |
| PM / 統整 | 計劃書、書面報告統整、展示影片剪輯、家庭錄影 | proposal.md / 影片 / 家庭錄影 |

### 對齊後的待辦狀態

- [x] PDF 規格閱讀並記錄
- [ ] 新增 `exceptions.py`
- [ ] 新增 `config.py` + `config.json` 樣本
- [ ] 新增 `persistence.py`(SQLite schema + DAO)
- [ ] 新增 `exporter.py`(CSV / JSON / Markdown)
- [ ] widget 加入「Session history」「Analytics」分頁
- [ ] 新增 `--real` 真實 GPU 對照模式
- [ ] 撰寫 `proposal.md`(5/10 截止)
- [ ] 撰寫 `docs/final_report.md` 骨架(6/4 截止)
- [ ] 家庭展示腳本(6/18 截止)
- [ ] 擴充測試覆蓋到新模組

---

## 2026-04-24 · 第二輪對齊:擴大行為覆蓋 + 真實 GPU 追蹤

### 使用者回覆

1. 技術覆蓋→ **加到 6/6**(確認)。
2. 行為覆蓋→ **希望模擬「所有」使用者行為**(打開網頁、輸入網址、打開 app),
   並加上追蹤真實 GPU 狀態的選項。
3. 組員分工與 proposal 的隊員名單→ 使用者自行撰寫,程式這邊不產出名單。
4. 要草擬 `proposal.md` 骨架,內容留白讓使用者補組員姓名。

### 行為覆蓋表(擴充)

| 使用者行為 | 偵測方式 | 觸發 kernel | 備註 |
| --- | --- | --- | --- |
| 滑鼠點擊 | `pynput` | `vector_add` | 已存在 |
| 滑鼠移動(節流) | `pynput` | `interpolation` | 已存在 |
| 鍵盤按鍵 | `pynput` | `hash` | 已存在;對網址列輸入自然會觸發 |
| 切換前景視窗 | Win32 / ctypes | `texture_load(app_title)` | 已存在;涵蓋「切換到瀏覽器」 |
| **開啟新 app** | `psutil` polling 新 PID | `app_launch` kernel(高 VRAM、長持續) | **新增** |
| **視窗標題變動**(例:瀏覽器切分頁、輸入 URL) | 前景視窗標題輪詢 | `page_nav` kernel | **新增** |
| 閒置 >5 秒 | timer | `idle_compression` | 已存在 |

### 新增 kernel 類型

- `app_launch_kernel` — memory-heavy + long duration(模擬載入驅動 / 著色器)
- `page_nav_kernel` — mixed profile(模擬 DOM → 紋理 → 合成)

### 真實 GPU 追蹤(新模組 `real_gpu.py`)

| 優先順序 | 方式 | 條件 |
| --- | --- | --- |
| 1 | `pynvml`(NVIDIA) | 偵測到 NVIDIA 卡;回傳利用率/記憶體/溫度/功率 |
| 2 | Windows WMI GPU performance counters | 無 NVIDIA 但 Windows 有 DirectX |
| 3 | `GPUtil` 套件(可選相依) | 上面都不可得 |
| 4 | None(降級純模擬) | 都沒有時 |

UI 切換方式:`--real` flag 或 widget 內 toggle,真實 GPU 資訊會以
獨立的「Real GPU」區塊顯示在模擬區塊下方。

### 模組新增清單

```text
src/gpu_simulator/
├── exceptions.py    # 自定義例外階層
├── config.py        # config.json 讀寫 + 預設設定
├── persistence.py   # SQLite 存取層
├── exporter.py      # CSV / JSON / Markdown / PNG 匯出
├── real_gpu.py      # pynvml / GPUtil 包裝,真實 GPU 取樣
├── process_watcher.py  # psutil 輪詢新 process
└── analytics.py     # matplotlib 時序圖產生(嵌入 Qt 或直接輸出檔)
```

### 第二輪待辦狀態

- [x] 寫 `proposal.md`(組員名單與分工留白由使用者填寫)
- [x] 新增 `exceptions.py`(`GPUVizError` 為根的 7 類例外)
- [x] 新增 `config.py` + `configs/default.json`(JSON load/save、trigger mapping 驗證)
- [x] 新增 `persistence.py`(SQLite,4 張表 + 3 個索引,context-manager)
- [x] 新增 `exporter.py`(CSV / JSON / Markdown / PNG)
- [x] 新增 `real_gpu.py`(pynvml → GPUtil → None 三層降級)
- [x] 擴充 `event_listener.py`(`ProcessWatcher` + 標題變動 + 可由 `AppConfig` 驅動 trigger)
- [x] 新增 `app_launch_kernel` / `page_nav_kernel` 與 `KernelLibrary.build()` dispatcher
- [x] widget 改為 Live / Analytics / History 三分頁 + Real GPU 區;整合 session 記錄、replay、匯出
- [x] 既有模組改為使用自定義例外(`submit_kernel_strict` 會 raise `VRAMOverflowError` / `KernelSubmissionError`)
- [x] 新模組測試(新增 29 個測試,全專案共 53 個測試皆通過)
- [x] README 更新(完整功能、安裝、相依、UI 控制、schema、設定檔、資料流圖、六項技術對照、期末專案分數對照)

### 交付物摘要(第二輪結束時)

| 交付物 | 位置 |
| --- | --- |
| 計劃書骨架(待填組員與分工) | [proposal.md](proposal.md) |
| 持續更新的 README | [README.md](README.md) |
| 需求變更紀錄(本檔) | [CHANGELOG_REQUIREMENTS.md](CHANGELOG_REQUIREMENTS.md) |
| 預設設定檔 | [configs/default.json](configs/default.json) |
| 全部程式碼 | [src/gpu_simulator/](src/gpu_simulator/) — 14 個模組 |
| 測試套件 | [tests/](tests/) — 11 個測試檔,53 tests passing |

### 接下來使用者需要自行處理的事項

1. 在 `proposal.md` 填入組員姓名、學號、分工規劃,於 **5/10 23:59** 前繳交。
2. 於 **6/1 23:59** 前錄製展示影片(10 分鐘以內),把 live / replay / analytics / 真實 GPU 對照都示範到。
3. 於 **6/4 23:59** 前撰寫書面報告(≤ 8 頁 A4 PDF),可直接引用 README 的架構圖、schema、六項進階技術對照表;記得每人各寫一段心得。
4. 於 **6/18 23:59** 前完成家庭展示錄影、組間回饋(每人 ≥ 10 組)、組內回饋。

---

## 2026-04-25 · 第三輪對齊:Tiny8 風格 trace + 純輸入(asm)模式

### 第三輪使用者回覆

1. Trace 顯示風格 → **同 Tiny8**(Cycle 為主鍵的逐步表格,字母代表 pipeline 階段,可上下捲動,變動高亮)。
2. CPU 規模 → **像 Tiny8 一樣完整**(實作 Tiny8 子集 + 自有的 GPU bridge 指令)。
3. 輸入模式 → 採用我推薦預設:**asm 編輯器 + Run/Step/Reset**(輸入即程式碼,跑出 CPU↔GPU 互動)。
4. 進入 asm 模式時 → 採用我推薦預設:**自動暫停 OS 事件監聽**,以免雜訊干擾教學示範。

### 設計決策

- **不 pip 依賴 tiny8 套件**:Python 3.14 wheel 可能還沒出。改在 gpu_simulator 內自寫一個 Tiny8 風格子集 CPU,自有 ISA、自有組譯器,完全控制與相容。
- **GPU bridge 走 IN/OUT port 風格**(與 Tiny8 ISA 一致):
  - `OUT 0x40, Rr` — 把 Rr 當 kernel id,提交對應 kernel 給 GPU
  - `OUT 0x41, Rr` — 把 Rr 當 hint(整數)
  - `IN  Rd, 0x40` — 讀 GPU 狀態(0=idle, 1=busy)
  - `IN  Rd, 0x41` — 讀已完成的 kernel 數
  - 並提供 mnemonic 別名 `KLAUNCH Rr` / `KWAIT` / `KSTAT Rd`
- **Kernel id 對應表**:

  | id | kernel |
  | --- | --- |
  | 0 | vector_add |
  | 1 | interpolation |
  | 2 | hash |
  | 3 | texture_load |
  | 4 | idle_compression |
  | 5 | app_launch |
  | 6 | page_nav |

### 模組新增

```text
src/gpu_simulator/
├── cpu.py        # CPU + 32 暫存器 + SREG + 組譯器 + 子集 ISA
├── bridge.py     # CPUGPUBridge:每 step 產生一筆 TraceRow
└── trace.py      # TraceRow / TraceLog dataclass(可序列化、可寫 SQLite)
```

### widget 新增 2 個分頁

- **Trace** — Tiny8 風格表格(QTableWidget):欄位 = `Cycle / PC / Instruction / SREG / R 變動 / GPU summary`。每筆變動的格子高亮,可上下捲動。
- **Input** — `QPlainTextEdit` 編輯器 + Run/Step/Reset 按鈕。按 Run → 暫停 OS listener、組譯、bridge.step() 直到 HALT 或 cycle 上限,Trace 即時更新。Reset → 回到 Live 模式並重新啟動 listener。

### Tiny8 子集 ISA(實作清單)

| 類別 | 指令 |
| --- | --- |
| 資料移動 | `LDI Rd, K` / `MOV Rd, Rr` / `IN Rd, port` / `OUT port, Rr` |
| 算術 | `ADD Rd, Rr` / `SUB Rd, Rr` / `INC Rd` / `DEC Rd` |
| 比較 | `CP Rd, Rr` / `CPI Rd, K` |
| 控制流 | `JMP label` / `BRNE label` / `BREQ label` / `NOP` / `HALT` |
| GPU bridge(別名) | `KLAUNCH Rr` / `KWAIT` / `KSTAT Rd` |

### 第三輪待辦狀態

- [x] CHANGELOG 第三輪區段(本段)
- [x] `cpu.py`(32 個暫存器、SREG 4 旗標、子集 ISA 執行、組譯器、KLAUNCH/KWAIT/KSTAT 別名)
- [x] `bridge.py`(I/O port 0x40/0x41/0xFF 三個 port、CPU↔GPU 整合、`TraceRow` + `TraceLog`)
- [x] visualizer:`TraceTable`(QTableWidget,Tiny8 風格變動高亮) + `AsmInputPanel`(編輯器+按鈕)
- [x] widget:Trace / Input 兩個分頁 + mode 狀態機(`live` / `replay` / `asm`)+ 進入 asm 自動暫停 OS listener
- [x] `examples/` 加三支 `.asm` 範例(`hello_gpu.asm` / `burst_and_count.asm` / `loop_kernel.asm`)
- [x] 測試 `test_cpu.py`(20 cases)+ `test_bridge.py`(7 cases),全專案共 80 tests passing
- [x] README 更新(新增 Trace / Input 分頁說明、Tiny8 子集 ISA、kernel id 表、3 支範例)
- [x] 版本 bump 到 0.3.0(pyproject + `__version__`)

### 第三輪交付物摘要

| 交付物 | 位置 |
| --- | --- |
| Tiny8 子集 CPU + 組譯器 | [src/gpu_simulator/cpu.py](src/gpu_simulator/cpu.py) |
| CPU↔GPU bridge | [src/gpu_simulator/bridge.py](src/gpu_simulator/bridge.py) |
| Trace 表格 + ASM 編輯器 | [src/gpu_simulator/visualizer.py](src/gpu_simulator/visualizer.py) |
| widget mode 狀態機 | [src/gpu_simulator/widget.py](src/gpu_simulator/widget.py) |
| 三支 .asm 範例 | [examples/hello_gpu.asm](examples/hello_gpu.asm) / [burst_and_count.asm](examples/burst_and_count.asm) / [loop_kernel.asm](examples/loop_kernel.asm) |
| 新測試 | [tests/test_cpu.py](tests/test_cpu.py) / [tests/test_bridge.py](tests/test_bridge.py) |

---

## 2026-04-25 · 第四輪對齊:Tiny8 兩種視覺化風格(Debug + Heatmap)

### 第四輪使用者回覆

使用者貼了 Tiny8 的兩張畫面要求採用同樣風格:

1. **黑底 curses 互動式 debugger**:狀態列(Cycle / PC / SP / 指令)+ 32 個暫存器格子 + SREG 旗標 + 記憶體窗格,變動高亮。
2. **matplotlib 時序熱圖**:SREG flag bar(隨 step 變色)+ 32 暫存器熱圖 + 記憶體 0x60–0x7F 熱圖。

### 前置補強

要讓熱圖的記憶體列有東西可看,先補 CPU 的記憶體 bank 與 Tiny8 對應指令:

- 256 byte 平面記憶體(`memory: list[int]`,初值全 0)
- `LD Rd, Rr` — `Rd ← memory[Rr]`
- `ST Rr, Rs` — `memory[Rr] ← Rs`
- `LDS Rd, K` — `Rd ← memory[K]`(立即位址)
- `STS K, Rr` — `memory[K] ← Rr`(立即位址)
- `CycleResult` 加 `memory_changes: dict[int, int]` 與全量 `memory_snapshot`

### Bridge 擴充

`CPUGPUBridge` 多兩個歷程陣列,給熱圖直接讀:

- `register_history: list[tuple[int, ...]]` — 每 cycle 的 32 暫存器快照
- `memory_history: list[tuple[int, ...]]` — 每 cycle 的 256 byte 記憶體快照
- 兩者都有 `clear()` 方法,跟 trace log 同步重設

### 新 widget

```text
src/gpu_simulator/visualizer.py 內新增
├── DebugView          # 黑底 curses 風格:狀態列 + 暫存器格 + 記憶體格 + 當前指令
└── HeatmapView        # matplotlib 三層熱圖 + step 滑桿
```

兩個視圖都 read-only,從最新一筆 `TraceRow` + `register_history` / `memory_history` 餵資料。

### widget tabs(最終 7 個)

`Live · Analytics · History · Trace · Debug · Heatmap · Input`

### 第四輪待辦狀態

- [x] CHANGELOG 第四輪區段(本段)
- [x] cpu.py 加 256-byte 記憶體 bank + `LD`/`ST`/`LDS`/`STS` 指令 + `memory_changes` snapshot
- [x] bridge.py 加 `register_history` / `memory_history` / `sreg_history`,`reset()` 同步清空
- [x] visualizer.py 加 `DebugView`(QPainter 黑底 + monospace,Tiny8 CLI 風格,SREG / 32 register 格 / 16-寬 memory 格,變動高亮)
- [x] visualizer.py 加 `HeatmapView`(matplotlib `imshow` 三層:SREG / 暫存器 / 記憶體 0x60–0x7F,跟著 step 累積)
- [x] widget.py 加 **Debug** + **Heatmap** 兩個分頁(現共 7 個分頁:Live / Analytics / History / Trace / **Debug** / **Heatmap** / Input)
- [x] examples 加 `memory_copy.asm`(忠實模仿 Tiny8 範例,並接上 KLAUNCH/KWAIT)
- [x] 新測試 `test_memory_ops.py`(9 cases:LD/ST/LDS/STS、wrap-around、`memory_changes`、bridge 三層 history、reset 清空、memory_copy 端到端)
- [x] 全套 89 tests passing
- [x] README 更新

### 第四輪交付物摘要

| 交付物 | 位置 |
| --- | --- |
| 256-byte 記憶體 + 4 個記憶體指令 | [src/gpu_simulator/cpu.py](src/gpu_simulator/cpu.py) |
| 三層 history 紀錄 | [src/gpu_simulator/bridge.py](src/gpu_simulator/bridge.py) |
| Tiny8 CLI 風格 DebugView | [src/gpu_simulator/visualizer.py](src/gpu_simulator/visualizer.py) |
| Tiny8 動畫風格 HeatmapView | [src/gpu_simulator/visualizer.py](src/gpu_simulator/visualizer.py) |
| 主視窗加兩個分頁 + 即時更新 | [src/gpu_simulator/widget.py](src/gpu_simulator/widget.py) |
| memory_copy 示範程式 | [examples/memory_copy.asm](examples/memory_copy.asm) |
| 測試 | [tests/test_memory_ops.py](tests/test_memory_ops.py) |

---

## 2026-05-07 · 第五輪對齊:全面繁中化 + 教育產品級體驗升級

### 第五輪使用者要求

> 「我希望他能更符合期末專案需求,讓畫面有更多繁體中文說明,讓非專業使用者(包含爸媽)
> 能知道如何操作,甚至能用更簡單的方式輸入(例如預設選單)。除此之外請你提議更多
> 讓他更完善、更有創意的建議。 ... 你直接建議吧,我想要的是足夠厲害跟有創意。」

我直接拍板下面這 11 項升級,目標是:同時滿足「家庭錄影 10 分(爸媽看得懂)」、
「展示影片 35 分(視覺驚豔有戲)」、「書面報告 30 分(功能列表豐富)」三個評分點。

### 第五輪鎖定升級

| 編號 | 名稱 | 對應評分 |
| --- | --- | --- |
| L1 | **全面繁中化**(分頁名 / section / 按鈕 / 狀態 / heatmap 軸 / kernel 別名) | 全部 |
| L2 | **範例卡片選單**(Steam 風,卡片含標題、中文說明、難度星星,一鍵載入並執行) | 展示影片、家庭錄影 |
| L3 | **首次啟動歡迎對話**(5 步驟中文導覽,記在 `~/.gpu_simulator/welcomed`) | 家庭錄影 |
| L4 | **成就系統**(10 個徽章 + 獎盃室 dialog;SQLite `achievements` 表持久化) | 展示影片、書面報告 |
| L5 | **考考你小測驗**(asm 跑完彈出 5 題選擇題,計分 + 中文解釋) | 展示影片、書面報告 |
| L6 | **「給爸媽看」模式**(`--easy` flag,大字、隱藏 Trace/Debug/Heatmap/Input,自動跑 demo) | 家庭錄影 |
| L7 | **內建 GIF 錄影鈕**(widget 自錄,輸出到 `~/.gpu_simulator/recordings/`) | 展示影片素材 |
| L8 | **GPU 寵物表情**(隨利用率變表情 `😴→🤔→😅→🔥` + 中文小語) | 全部 |
| L9 | **音效回饋**(kernel 完成、HALT、成就解鎖三種音) | 展示影片 |
| L10 | **4 支新範例 asm**(`sort_three`、`find_max`、`counter`、`mixed_burst`,全中文註解) | 書面報告 |
| L11 | **kernel 中文別名表**(event log 顯示「向量加法」「紋理載入」等) | 家庭錄影、書面報告 |

### 第五輪設計決策

- **i18n 策略**:純繁中為主,但把 Tiny8 ISA 助記符(LDI、KLAUNCH 等)保留英文 — 它們是教學重點。
- **成就持久化**:不另開 DB,沿用既有 `~/.gpu_simulator/sessions.sqlite3`,加一張 `achievements(name, unlocked_at)` 表。
- **GIF 錄影**:每幀用 `widget.grab()` 取 QPixmap → PIL `Image` → 累積 → 結束時輸出。
- **音效**:Windows 用 `winsound.MessageBeep` / `Beep` (stdlib);非 Windows 走 PySide6 `QSoundEffect` 或退化為靜音。
- **「給爸媽看」模式**:CLI `--easy`;widget 啟動時切換隱藏 5 個進階分頁,只留 Live + 一個新的「教學秀」分頁,自動每 30 秒切到下一個範例。
- **GPU 寵物臉**:不外加圖檔,純 emoji + Qt label;簡化、零相依、跨平台。

### 第五輪待辦狀態

- [x] CHANGELOG 第五輪區段(本段)
- [x] `i18n.py` 中文字串字典模組(83 條 key,集中管理)
- [x] visualizer.py 全面中文化(分頁標籤、欄位、按鈕、tooltip、event log 中文 kernel 別名)
- [x] widget.py 全面中文化 + tooltip + 模式標籤改用 i18n
- [x] `PresetMenu` 卡片選單(Steam 風,8 張卡 ★ 難度標示)
- [x] 首次啟動歡迎對話(5 步驟導覽,寫 `~/.gpu_simulator/welcomed` 標記)
- [x] `achievements.py` 成就模組 + SQLite `achievements` 表 + `TrophyRoomDialog`
- [x] `quiz.py` 考考你模組 + `QuizDialog`(10 題靜態 + 動態題,選 5 題)
- [x] `--easy` 模式(widget.py 條件渲染 + DemoTab 自動循環播放,30 秒切下一支)
- [x] `recorder.py` GIF 錄影 + 工具列鈕,輸出 `~/.gpu_simulator/recordings/gpu-simulator-*.gif`
- [x] `gpu_pet.py` 寵物表情元件(😴🤔💪😅🔥 五階,中文小語)
- [x] `sounds.py` 音效模組(Windows 內建 winsound,kernel 完成 / HALT / 成就解鎖三種音)
- [x] 4 支新範例 asm:`sort_three` / `find_max` / `counter` / `mixed_burst`,全中文註解
- [x] 新測試:`test_i18n.py` / `test_achievements.py` / `test_quiz.py` / `test_pet_and_sounds.py` / `test_new_examples.py`(共 37 個新案例,全部 126 個 tests passing)
- [x] README 更新
- [x] 版本 bump 到 0.4.0(pyproject + `__version__`)

### 第五輪交付物摘要

| 交付物 | 位置 |
| --- | --- |
| 中文字串字典 | [src/gpu_simulator/i18n.py](src/gpu_simulator/i18n.py) |
| 音效模組 | [src/gpu_simulator/sounds.py](src/gpu_simulator/sounds.py) |
| GPU 寵物臉 | [src/gpu_simulator/gpu_pet.py](src/gpu_simulator/gpu_pet.py) |
| 成就系統 | [src/gpu_simulator/achievements.py](src/gpu_simulator/achievements.py) |
| 考考你題庫 | [src/gpu_simulator/quiz.py](src/gpu_simulator/quiz.py) |
| GIF 錄影 | [src/gpu_simulator/recorder.py](src/gpu_simulator/recorder.py) |
| 對話框 + 預設選單 | [src/gpu_simulator/dialogs.py](src/gpu_simulator/dialogs.py) |
| 4 支新範例 | [examples/sort_three.asm](examples/sort_three.asm) / [find_max.asm](examples/find_max.asm) / [counter.asm](examples/counter.asm) / [mixed_burst.asm](examples/mixed_burst.asm) |
| widget 整合(7 分頁 + 寵物 + 4 顆動作鈕 + 歡迎對話 + easy 模式) | [src/gpu_simulator/widget.py](src/gpu_simulator/widget.py) |
| CLI flags `--easy` / `--no-welcome` | [src/gpu_simulator/cli.py](src/gpu_simulator/cli.py) |

---

## 2026-05-08 · 第六輪對齊:整合「真正的 Tiny8 CPU」與虛擬 GPU

### 第六輪使用者要求

> 「我希望能更完整,能不能考慮把他跟 Tiny8 原本的 CPU 結合在一起,可以看到兩處的交互作用?」

### 第六輪設計決策

- **使用真正的 Tiny8 CPU(60+ 指令完整版)**:延續本專案是 Tiny8 教學延伸的精神。
- **採用 vendor 策略**:把 Tiny8 source 直接內嵌到 `gpu_simulator/tiny8_full/`(MIT 授權允許,且免去 PyPI / Python 3.14 wheel 風險)。
- **不取代既有的子集 CPU**:保留 `cpu.py`(子集版,給 Trace / Heatmap 用),新加 `full_bridge.py` 走完整 Tiny8。使用者可在 widget 上自由切換看哪一邊。
- **CPU↔GPU 串接點**:Tiny8 內部 `OUT port, Rr` 會呼叫 `cpu.write_ram(port, val)`,這是天然的 chokepoint。透過 subclass + override `write_ram` 攔截到 0x40 / 0x41 / 0xFF 三個位址,直接派送對應的 GPU kernel。**完全不用改 Tiny8 的 ISA**。
- **新分頁 `Tiny8 完整版 ↔ GPU`**:左側是 Tiny8 完整暫存器網格 + 記憶體窗 + 當前指令來源行,右側是虛擬 GPU 8 顆 SM 熱圖 + VRAM bar,中間是「流向箭頭」呈現 kernel 從 CPU 流到 GPU。

### 第六輪交付清單

```text
src/gpu_simulator/
├── tiny8_full/                # 從 tiny8-main 內嵌進來的完整 Tiny8 CPU
│   ├── __init__.py            # 我們自己加,re-export CPU / Memory / assemble
│   ├── cpu.py                 # 1250 行,完整 ISA(60+ 指令)
│   ├── assembler.py           # parse/assemble
│   ├── memory.py              # 2 KB RAM 模型
│   ├── utils.py               # progress bar 等
│   └── LICENSE.md             # 保留 Tiny8 原作者 MIT 授權聲明
├── full_bridge.py             # FullCPUGPUBridge:Tiny8 CPU + 虛擬 GPU
├── visualizer.py              # 加 Tiny8FullView(左 CPU 右 GPU 並列)
├── widget.py                  # 加新分頁 + AsmInputPanel 切換為完整 ISA
└── cli.py                     # 新增 `--full-cpu` flag,讓使用者直接以完整模式啟動
examples/
├── full_bubble_sort.asm       # 移植 Tiny8 經典範例 + KLAUNCH/KWAIT
└── full_fibonacci.asm         # 同上
tests/
└── test_full_bridge.py        # 完整 Tiny8 + GPU 端到端測試
```

### 第六輪待辦狀態

- [x] CHANGELOG 第六輪區段(本段)
- [x] vendor Tiny8 source 與 LICENSE 到 `src/gpu_simulator/tiny8_full/`(5 個檔,~1700 行)
- [x] `full_bridge.py`:`FullTiny8CPU` 子類別 override `write_ram` / `read_ram`,`FullCPUGPUBridge` 走 step + tick + history
- [x] `Tiny8FullView` 並列視覺元件:左 Tiny8 完整暫存器格 + 記憶體窗,右 GPU 8 SM 熱圖 + VRAM,中間 kernel 流向箭頭
- [x] widget 新增 `🧬 Tiny8 完整版` 分頁(共 8 個分頁),配第二顆 ASM 編輯器
- [x] 2 支整合示範:
  - `examples/full_fibonacci.asm` — 算 F(10)=55 後丟 GPU hash kernel
  - `examples/full_bubble_sort.asm` — RAM[0x60..0x67] 排序後丟兩種 kernel
- [x] 端到端測試 `test_full_bridge.py`(13 個案例,全套 139 tests passing)
- [x] README 更新
- [x] 版本 bump 到 0.5.0

### 第六輪交付物摘要

| 交付物 | 位置 |
| --- | --- |
| 內嵌 Tiny8 完整源碼 | [src/gpu_simulator/tiny8_full/](src/gpu_simulator/tiny8_full/) |
| Tiny8 ↔ GPU bridge | [src/gpu_simulator/full_bridge.py](src/gpu_simulator/full_bridge.py) |
| 並列視圖元件 | [src/gpu_simulator/visualizer.py](src/gpu_simulator/visualizer.py) |
| widget 新分頁 | [src/gpu_simulator/widget.py](src/gpu_simulator/widget.py) |
| 整合示範 .asm | [examples/full_fibonacci.asm](examples/full_fibonacci.asm) / [examples/full_bubble_sort.asm](examples/full_bubble_sort.asm) |
| 端到端測試 | [tests/test_full_bridge.py](tests/test_full_bridge.py) |

---

## 2026-05-08 · 第七輪對齊:Tiny8 教學等級體驗升級

### 第七輪使用者要求

> 「繼續加強他的視覺化跟 CPU 交互作用,最好能繼續擴充,讓他能有好的教學與學習功能,
> 跟 Tiny8 的目的跟呈現效果一樣。」

### 第七輪鎖定升級

| 編號 | 項目 | 教學意義 |
| --- | --- | --- |
| V1 | **時序圖**(新分頁)— CPU 跟 GPU 兩條 lane,KLAUNCH / KWAIT / kernel-done 用箭頭呈現,UML 風格 | 一眼看懂 CPU↔GPU 怎麼合作 |
| V2 | **時光旅行(Time-Travel)**— Trace 表選任一列,Debug 跟 Heatmap 同步顯示那 cycle 的狀態,Vim 鍵盤導航 | Tiny8 招牌功能 |
| V3 | **指令解說(Live Commentary)**— Trace 分頁中文側欄,把每個指令翻成「這一行做了什麼」 | 不查表也能讀 trace |
| V4 | **Trace 行高亮**— KLAUNCH(橘)/ KWAIT(藍)/ HALT(紅)/ stall(灰) | 視覺重點 |
| V5 | **記憶體地圖**(新分頁)— 256 byte 全圖,標示 0x40 / 0x41 / 0xFF 是 GPU 控制暫存器 | 知道為什麼寫到 0x40 會觸發 GPU |
| V6 | **🎓 教學課程**— 5 課中文導覽 | 完整教學流程 |

### 第七輪交付清單

```text
src/gpu_simulator/
├── commentary.py             # 指令 → 中文解說
├── lessons.py                # 5 課教學內容
├── visualizer.py             # 加 SequenceDiagramView / MemoryMapView / LiveCommentaryPanel + 行色碼
├── dialogs.py                # 加 GuidedLessonDialog
└── widget.py                 # 新分頁 + 時光旅行 + Vim 鍵盤
```

### 第七輪待辦狀態

- [x] CHANGELOG 第七輪區段(本段)
- [x] `commentary.py` 中文指令解說模組(`explain_instruction` / `classify_row` / `Commentator`)
- [x] `LiveCommentaryPanel` 在 Trace 分頁右側即時吐中文導讀
- [x] Trace 行依事件種類上色:KLAUNCH(橘)/ KSTAT(淺綠)/ KWAIT(藍)/ stall(灰)/ HALT(紅)/ JMP(紫)/ BRANCH(黃)/ MEMORY(青);右側多一欄「事件 / 說明」放 ← 中文 badge
- [x] `SequenceDiagramView` 新分頁 — CPU + GPU 兩條 lane,KLAUNCH 用橘色實線箭頭往下、kernel 完成用綠色虛線箭頭往上
- [x] `MemoryMapView` 新分頁 — 256 byte 記憶體地圖,GPU 控制暫存器(0x40 / 0x41 / 0xFF)用三種顏色標示,使用者資料區另色
- [x] Trace row 點選 → DebugView / MemoryMapView / SequenceDiagram 同步顯示那個 cycle 的狀態(時光旅行)
- [x] `lessons.py` 5 課中文教學內容 + `GuidedLessonDialog`(雙欄式對話,左清單右內容)
- [x] widget.py 新增 `🎓 教學課程` 工具列鈕、`🔁 時序圖` 分頁、`🗺️ 記憶體` 分頁(現共 10 個分頁)
- [x] 新測試:`test_commentary.py`(17 cases)+ `test_lessons.py`(7 cases),全套 163 tests passing
- [x] README 更新
- [x] 版本 bump 到 0.6.0

### 第七輪交付物摘要

| 交付物 | 位置 |
| --- | --- |
| 中文指令解說模組 | [src/gpu_simulator/commentary.py](src/gpu_simulator/commentary.py) |
| 5 課教學內容 | [src/gpu_simulator/lessons.py](src/gpu_simulator/lessons.py) |
| LiveCommentaryPanel / SequenceDiagramView / MemoryMapView | [src/gpu_simulator/visualizer.py](src/gpu_simulator/visualizer.py) |
| GuidedLessonDialog | [src/gpu_simulator/dialogs.py](src/gpu_simulator/dialogs.py) |
| widget 整合(時光旅行 / 三新分頁 / 教學鈕) | [src/gpu_simulator/widget.py](src/gpu_simulator/widget.py) |
| 新測試 | [tests/test_commentary.py](tests/test_commentary.py) / [tests/test_lessons.py](tests/test_lessons.py) |

---

## 2026-05-08 · 第八輪對齊:CPU↔GPU 內部交互運作 + Tiny8 範例延伸

### 第八輪使用者要求

> 「繼續加強視覺化與互動性,最好能有完整 CPU 和 GPU 內部交互運作的內容,
> 就是 Tiny8 裡面 example 的延伸。」

### 第八輪鎖定

| 編號 | 項目 |
| --- | --- |
| W1 | **🎬 Cycle Cinema 同步劇場**(新分頁)— 頂 CPU 完整狀態、中 kernel 流動、底 8 SM × 4 warps × 5 階 pipeline,VCR 拖桿可拉前後 |
| W2 | **VRAM 區塊圖**(取代純 bar)— 每個 kernel 的 VRAM 佔用畫成有名字的方塊 |
| W3 | **Warp Pipeline 動畫** — 每 warp 5 個 F/D/E/M/W 小方塊,跟著 stage 移動發光 |
| W4 | **5 支 Tiny8 經典範例的 GPU 進階版**:GCD / count-bits / factorial / histogram / matrix-diagonal,全用完整 Tiny8 ISA + GPU bridge |
| W5 | **Source-line 高亮** — Cycle Cinema 左側顯示源碼,正在執行的那行高亮 |

### 第八輪交付清單

```text
src/gpu_simulator/
├── visualizer.py             # 加 VRAMBlocksWidget / WarpPipelineAnimationWidget / CycleCinemaView
└── widget.py                 # 加 🎬 Cycle Cinema 分頁、Live 改用 VRAM 區塊圖
examples/
├── full_gcd_gpu.asm
├── full_count_bits_gpu.asm
├── full_factorial_gpu.asm
├── full_histogram_gpu.asm
└── full_matrix_diagonal_gpu.asm
tests/
└── test_round8_examples.py
```

### 第八輪待辦狀態

- [x] CHANGELOG 第八輪區段(本段)
- [x] 5 支 Tiny8 風格 GPU 整合範例 — `full_gcd_gpu` / `full_count_bits_gpu` / `full_factorial_gpu` / `full_histogram_gpu` / `full_matrix_diagonal_gpu`
- [x] `VRAMBlocksWidget` — 每個 kernel 的 VRAM 佔用畫成有名字的方塊,按 owner 名雜湊取色
- [x] `WarpPipelineAnimationWidget` — 每 warp 5 個 F/D/E/M/W 小方塊,active 階段亮起
- [x] `CycleCinemaView` — VCR 控制(⏮ ◀ ▶ ⏭ + 滑桿 + 自動播放)+ 源碼高亮 + 中文 flow label
- [x] widget.py 加 🎬 Cycle Cinema 分頁(現共 11 個分頁),Live 多兩個元件:VRAM 區塊圖、Warp Pipeline 動畫
- [x] 新範例測試 `tests/test_round8_examples.py`(15 cases),全套 178 tests passing
- [x] README 更新
- [x] 版本 bump 到 0.7.0

### 第八輪交付物摘要

| 交付物 | 位置 |
| --- | --- |
| 5 支 GPU-整合範例 | [examples/full_gcd_gpu.asm](examples/full_gcd_gpu.asm) / [full_count_bits_gpu.asm](examples/full_count_bits_gpu.asm) / [full_factorial_gpu.asm](examples/full_factorial_gpu.asm) / [full_histogram_gpu.asm](examples/full_histogram_gpu.asm) / [full_matrix_diagonal_gpu.asm](examples/full_matrix_diagonal_gpu.asm) |
| VRAM 區塊圖 + Warp 動畫 + Cycle Cinema | [src/gpu_simulator/visualizer.py](src/gpu_simulator/visualizer.py) |
| widget 整合 | [src/gpu_simulator/widget.py](src/gpu_simulator/widget.py) |
| 端到端測試 | [tests/test_round8_examples.py](tests/test_round8_examples.py) |

---

## 2026-05-08 · 第九輪對齊:八項旗艦升級

### 第九輪使用者要求

> 「全部」(對前一輪我提的 8 項擴充建議全做)

### 鎖定的 8 項

| # | 項目 | 模組 |
| --- | --- | --- |
| 1 | 🎮 ASM 遊戲機(Conway's Game of Life,asm 寫的遊戲跑在虛擬 GPU) | `asm_games.py` + game widget |
| 2 | 🏗️ 3D GPU 視覺化(等距 2.5D,QPainter 自繪;不依賴 OpenGL) | `gpu_3d.py` |
| 3 | 📜 自動實驗報告產生器(Markdown + 嵌入 matplotlib 圖) | `lab_report.py` |
| 4 | 🎵 真正的音效合成(每種 kernel 一段 chord、idle BGM) | `sounds.py` 升級 |
| 5 | 📰 每日挑戰 + SQLite leaderboard | `challenges.py` |
| 6 | 🤖 Claude API 解釋器(optional anthropic dep,沒 key 自動降級) | `ai_explainer.py` |
| 7 | 🌐 Web 鏡像(stdlib http.server,瀏覽器看 GPU 狀態) | `web_mirror.py` |
| 8 | 🧠 進階 GPU 概念:warp divergence + memory coalescing 視覺化 | `divergence.py` |

### 第九輪設計決策

- **3D 視圖不引進 OpenGL/Qt3D**:用 QPainter 畫等距方塊,效果接近 3D 但維持零相依加碼,容易跨平台。
- **Web mirror 不引 Flask**:用 stdlib `http.server` + 一個 polling JSON endpoint,降低安裝負擔。
- **AI 解釋器**:optional dep `anthropic`,沒裝/沒 key 時 UI 上的按鈕保留但點下去顯示「請設定 ANTHROPIC_API_KEY」,不會崩潰。
- **音效**:Windows 維持 winsound 但用「多音 chord」變化(每 kernel 不同音階組合);其他平台 fallback 用 QSoundEffect 或靜默。
- **遊戲**:首發 Conway's Life — 8×8 棋盤,asm 邏輯每代產生新狀態並提交一顆 kernel,widget 用色塊渲染。

### 第九輪待辦狀態

- [x] CHANGELOG 第九輪區段(本段)
- [x] sounds.py 升級 — 7 種 kernel 各有專屬 chord 動機,新 API `play_kernel_chord(name)` / `play_idle_pulse()`
- [x] lab_report.py — Markdown 報告,自動產出 3 張 PNG(CPU 狀態 timeline / register heatmap / memory heatmap)
- [x] challenges.py — 每日題目 hash 自當日日期 + SQLite leaderboard
- [x] ai_explainer.py — optional anthropic;沒 key 時降級為純規則中文導讀
- [x] asm_games.py — Conway's Life,blinker / glider / random 三種 seed,每代派 8 顆 GPU kernel
- [x] divergence.py — warp 發散 + memory coalescing 模擬與分析(builtin 4+4 預設情境)
- [x] visualizer 加 `GPU3DView`(等距投影自繪 8 SM 立方體 + KLAUNCH 光球)
- [x] visualizer 加 `LifeBoardWidget`(8×8 棋盤 + 點擊編輯 + 顯示)
- [x] visualizer 加 `DivergenceView`(32 thread 網格 + 中文摘要)
- [x] dialogs 加 `AIExplainerDialog` / `ChallengeDialog`
- [x] web_mirror.py — stdlib http.server,`/snapshot` JSON + `/` HTML(內嵌 JS poll)
- [x] widget.py 整合 — 11 → **14 個分頁**,工具列加 4 顆按鈕(🤖 AI / 🏁 挑戰 / 📜 報告 / 🌐 鏡像)
- [x] cli.py 加 `--serve-web PORT` flag,啟動時直接開鏡像 server
- [x] 新模組測試 — `tests/test_round9_modules.py` 25 cases,**全套 203 tests passing**
- [x] ruff check 0 issues
- [x] 版本 bump 到 0.8.0
- [x] README 更新

### 第九輪交付物摘要

| 模組 | 行數 | 用途 |
| --- | --- | --- |
| `sounds.py` | 130 | 7 kernel chord + UI 音效 |
| `lab_report.py` | 290 | Markdown + matplotlib 圖 |
| `challenges.py` | 290 | 每日題 + leaderboard |
| `ai_explainer.py` | 220 | Claude + 離線 fallback |
| `asm_games.py` | 220 | Conway's Life runner |
| `divergence.py` | 280 | warp 發散 + coalescing |
| `web_mirror.py` | 200 | stdlib http.server |
| widget 內新增的 visualizer 元件 | ~600 | GPU3DView, LifeBoardWidget, DivergenceView |
| dialogs 內新增 | ~250 | AIExplainerDialog, ChallengeDialog |
| widget 整合 | ~400 增量 | 14 分頁、9 顆工具列鈕、Mirror 整合 |
| 新測試 | 25 cases | round 9 全功能覆蓋 |

---

## 2026-05-08 · 第十輪對齊:從 toy 走向 mini-platform 的 8 個深度擴充

### 第十輪使用者要求

> 「繼續把專案變大」(對 v0.8 之後)

### 鎖定的 8 項

| # | 項目 | 系統等級 |
| --- | --- | --- |
| X1 | 🔌 Plugin 系統 — `~/.gpu_simulator/plugins/*.py` 自動載入 | 平台化 |
| X2 | 🛠️ Kernel DSL 編譯器 — Python-like → Tiny8 asm | 編譯器 |
| X3 | 🐍 Snake 遊戲 — asm + 鍵盤輸入 | 遊戲 |
| X4 | 💾 L1 Cache 模擬器 + 可視化 | 系統教學 |
| X5 | 📈 效能分析器(per-kernel / Roofline) | 工程實務 |
| X6 | 🎨 主題系統(Cyberpunk / Matrix / Retro / Light) | 美感 |
| X7 | 🖥️ Headless `gpu-simulator run` 子指令 | 自動化 |
| X8 | 🤝 Multi-GPU + NVLink 跨卡傳輸 | 進階架構 |

### 第十輪交付清單

```text
src/gpu_simulator/
├── plugins.py             # 自動載入使用者外掛
├── kernel_dsl.py          # 高階 → asm 編譯器
├── cache.py               # L1 cache 模型 + 統計
├── profiler.py            # per-kernel 計時 + Roofline
├── themes.py              # 4 主題 stylesheet
├── multi_gpu.py           # 雙 GPU + NVLink
└── cli.py                 # 加 `run` 子指令(headless)
examples/
└── snake.asm              # 用 Tiny8 完整版寫的 Snake 主迴圈
```

### 第十輪待辦狀態

- [x] CHANGELOG 第十輪區段(本段)
- [ ] themes.py + 主題切換
- [ ] cli.py 加 `run` 子指令
- [ ] plugins.py
- [ ] cache.py
- [ ] profiler.py
- [ ] kernel_dsl.py
- [ ] Snake 遊戲(extend asm_games.py)
- [ ] multi_gpu.py
- [ ] 測試
- [ ] README 更新

---

## 2026-05-08 · 第十一輪對齊:5 個「眼前一亮」視覺特效

### 第十一輪使用者要求

> 「我希望這個專案可以更有趣 更有讓人眼前一亮的感覺」

不再加技術深度,專做視覺特效跟趣味性。

### 鎖定 5 項

| # | 特效 | 模組 |
| --- | --- | --- |
| W1 | ✨ 粒子特效系統(KLAUNCH 粒子飛行 / kernel 完成煙火) | `particle_fx.py` |
| W2 | 🥚→🐲 寵物五階進化(蛋 → 雛雞 → 小鳥 → 老鷹 → 龍) | `gpu_pet.py` 升級 |
| W3 | 🎬 電影模式 `--cinema`(60 秒劇本式 showcase) | `cinematic.py` |
| W4 | 🟢 Matrix Code Rain 背景(高利用率時下雨) | `code_rain.py` |
| W5 | 🗣️ TTS 中文旁白(optional pyttsx3) | `tts.py` |

### 第十一輪待辦狀態

- [x] CHANGELOG round 11 區段
- [x] `particle_fx.py` — 3 種發射模式(LAUNCH / FIREWORK / RIPPLE),純資料層 + Qt overlay
- [x] `gpu_pet.py` 進化 — 5 階段(🥚→🐣→🐤→🦅→🐲),wiggle 動畫
- [x] `cinematic.py` — 60.5 秒 23 個動作劇本 + `--cinema` CLI flag
- [x] `code_rain.py` — Matrix 字元雨,>70% util 啟動、<40% 自動關閉
- [x] `tts.py` — pyttsx3 背景 thread 朗讀,無阻塞,無 dep 也可 import
- [x] widget.py 整合:overlay 重疊 / cinema 字幕 / 2 顆新工具列按鈕(電影 / TTS) / pet 進化 hook
- [x] cli.py 加 `--cinema` flag
- [x] 新測試:`test_round11_spectacle.py`(17 cases)+ `test_pet_and_sounds.py` 改寫成 7 cases
- [x] 全套 **253 tests passing,ruff 0 issues**
- [x] 版本 bump 到 0.9.0

### 第十一輪交付物摘要

| 交付物 | 位置 |
| --- | --- |
| 粒子特效 | [src/gpu_simulator/particle_fx.py](src/gpu_simulator/particle_fx.py) |
| 寵物進化 | [src/gpu_simulator/gpu_pet.py](src/gpu_simulator/gpu_pet.py) |
| Matrix 雨 | [src/gpu_simulator/code_rain.py](src/gpu_simulator/code_rain.py) |
| TTS 旁白 | [src/gpu_simulator/tts.py](src/gpu_simulator/tts.py) |
| 電影模式 | [src/gpu_simulator/cinematic.py](src/gpu_simulator/cinematic.py) |
| widget 整合 | [src/gpu_simulator/widget.py](src/gpu_simulator/widget.py) |
| CLI `--cinema` | [src/gpu_simulator/cli.py](src/gpu_simulator/cli.py) |
| 新測試 | [tests/test_round11_spectacle.py](tests/test_round11_spectacle.py) / [tests/test_pet_and_sounds.py](tests/test_pet_and_sounds.py) |

---

## 2026-05-08 · 第十二輪對齊:樂趣 + UX polish 六連發

### 第十二輪使用者要求

> 「繼續加有趣的東西跟加強使用者頁面」

3 個 UX、3 個樂趣特效,搭配全域鍵盤快捷鍵。

### 鎖定 6 項 + 加碼

| # | 項目 | 類別 |
| --- | --- | --- |
| Y1 | 🍞 Toast 通知(取代 QMessageBox.info) | UX |
| Y2 | ⌨️ Command Palette (Ctrl+Shift+P) | UX |
| Y3 | 📊 底部狀態列 | UX |
| Y4 | 📅 GPU 心情日記(月曆熱圖) | 樂趣 |
| Y5 | 🥚 彩蛋系統(Konami code、magic words) | 樂趣 |
| Y6 | 🐱 寵物命名 + idle 動畫 | 樂趣 |
| 加碼 | 全域鍵盤快捷鍵 | UX |

### 第十二輪待辦狀態

- [x] CHANGELOG round 12 區段
- [x] `toast.py` — slide-in 通知,4 種等級
- [x] `command_palette.py` — Ctrl+Shift+P fuzzy 搜尋
- [x] `status_bar.py` — 底部永遠顯示版本/模式/kernel 數/利用率/FPS
- [x] `mood_calendar.py` — SQLite + GitHub-style 月曆熱圖
- [x] `easter_eggs.py` — Konami code + matrix/dragon/rainbow/boom 魔法字
- [x] `gpu_pet.py` — 寵物命名 + 閒置眨眼 + Ctrl+Shift+E rename
- [x] widget.py 整合:7 個全域 QShortcut + keyPressEvent 餵 detector + toast 替代 QMessageBox.info
- [x] **加碼:`cpu_heatmap.py`** — CPU 狀態時間熱圖(SREG / R0–R31 / mem 0x60–0x7f)
- [x] 全套 **289 tests passing,ruff 0 issues**
- [x] 版本 bump 到 0.10.0

### 第十二輪交付物摘要

| 交付物 | 位置 |
| --- | --- |
| Toast 通知 | [src/gpu_simulator/toast.py](src/gpu_simulator/toast.py) |
| Command Palette | [src/gpu_simulator/command_palette.py](src/gpu_simulator/command_palette.py) |
| 底部狀態列 | [src/gpu_simulator/status_bar.py](src/gpu_simulator/status_bar.py) |
| 心情日記 | [src/gpu_simulator/mood_calendar.py](src/gpu_simulator/mood_calendar.py) |
| 彩蛋系統 | [src/gpu_simulator/easter_eggs.py](src/gpu_simulator/easter_eggs.py) |
| 寵物命名 + 閒置動畫 | [src/gpu_simulator/gpu_pet.py](src/gpu_simulator/gpu_pet.py) |
| **CPU 狀態熱圖(教育核心)** | [src/gpu_simulator/cpu_heatmap.py](src/gpu_simulator/cpu_heatmap.py) |
| widget 整合 + 全域快捷鍵 | [src/gpu_simulator/widget.py](src/gpu_simulator/widget.py) |
| 新測試 | [tests/test_round12_ux.py](tests/test_round12_ux.py)(36 cases) |

### 全域快捷鍵速查

| 組合 | 動作 |
| --- | --- |
| Ctrl+Shift+P | 開命令面板 |
| Ctrl+/ / F1 | 顯示快捷鍵清單 |
| Ctrl+M | 開心情日記 |
| Ctrl+Shift+E | 幫寵物改名 |
| Ctrl+Shift+T | 切 TTS 旁白 |

### 教學意義:狀態熱圖分頁

新分頁 **🌡️ 狀態熱圖** 接受任意 Tiny8 完整版 ASM,跑完後渲染三層熱圖 +
時間軸 slider,讓學生可以「看到」每個 cycle 的暫存器 / 記憶體 / SREG 變化 —
直接對應大學「微處理器原理」課程裡常見的 state-trace 作業。

---

## 2026-05-24 · 第十三輪對齊:🪞 對照鏡(把專題論述具象化)

### 第十三輪使用者要求

> 「下一輪」

使用者只給一個字,沒有具體方向 — 但前幾輪剛把專案重新定位成「模擬 vs 真實」
三大支柱,要把核心論述具象化還缺**第一眼就看到的對照畫面**。

### 鎖定目標

把「模擬 GPU 8 SM」跟「真實 CPU N 核」並排畫在**第一分頁**,讓專題的論述
變成第一眼就看到的圖。次要:加一顆「觸發模擬工作負載」按鈕,讓使用者親眼
看到左邊跳起來右邊不動,瞬間理解「啊!這是兩個不同的世界」。

### 第十三輪交付清單

```text
src/gpu_simulator/
├── mirror_dashboard.py    # 🪞 對照鏡 — 模擬 vs 真實並排
│                          # ComparisonSnapshot / SimulatedSMSummary / compose_snapshot
│                          # divergence_score(0..100 教學分數)
│                          # build_mirror_dashboard(Qt 分頁)
├── widget.py              # 把 🪞 對照鏡 設為第 1 個分頁(預設打開即見)
                            並接 Kernel queue 讓「觸發負載」按鈕真的會跑 3 個 kernel
tests/
└── test_mirror_dashboard.py  # 9 cases 純資料層
```

### 第十三輪待辦狀態

- [x] CHANGELOG round 13 區段(本段)
- [x] `mirror_dashboard.py` — 純資料層 `ComparisonSnapshot` + `compose_snapshot` + `divergence_score`
- [x] Qt 分頁 — 左 SM bars / 右 CPU bars / 下 GPU 行 / 觸發按鈕
- [x] widget.py 整合 — 設為第 1 個分頁,接 `_kernel_queue.push` 真的派 kernel
- [x] 測試 `test_mirror_dashboard.py`(9 cases,跑模擬 + mock 都涵蓋)
- [x] PROJECT_BRIEF / QUICKSTART / README 更新
- [x] 全套 **308 tests passing,ruff 0 issues**

### 教學意義:🪞 對照鏡

這分頁是整個專題論述的**視覺化證據**:

- 模擬 GPU(本專題建的)是**抽象、可控、可慢動作回放**的世界
- 真實 CPU(你這台機器)是**具體、不可控、即時變動**的世界
- **同一個視窗、同一時刻、並排**看到這兩個世界,讓學生第一次親身體會兩者的關係 —
  模擬器不是「假的 GPU」,而是用來理解「真實 GPU 在更深層次也是這樣運作」的工具。

按下「▶️ 觸發模擬工作負載」按鈕後,左邊的 SM bar 會飆高,右邊 CPU 完全不動。
這 1 秒的視覺反差直接讓觀眾理解「模擬器跟你電腦是兩件事」。

---

## 2026-05-24 · 第十四輪對齊:demo 影片衝刺(6/1 截止剩 8 天)

### 第十四輪使用者要求

> 「下一輪」

距離 demo 影片 6/1 截止只剩 8 天,但既有的 60 秒 cinema 劇本是第十一輪寫的,
完全沒提到第十三輪新加的 🪞 對照鏡(專題論述的視覺核心)。本輪做衝刺準備。

### 鎖定 3 件事

1. **改 cinema 劇本** — 60 秒劇本重新編排,**🪞 對照鏡 變開場**,前 18 秒就把
   專題論述演完,後 42 秒帶過支柱 ① / ③ 跟其他亮點
2. **加 integration smoke test** — 證明關鍵模組可以互相 import + 基礎物件能
   建構 + 對照鏡 / cinema / 完整 Tiny8 ISA 後端都能跑;給期末報告「驗證」章節
   一個強硬證據
3. **寫 SCREENSHOTS_GUIDE.md** — demo 影片 / 期末報告 / 家庭錄影 三個 deadline
   各需要哪些畫面的 checklist,本人手動截圖時當對照表

### 第十四輪交付清單

```text
src/gpu_simulator/
└── cinematic.py             # builtin_60_second_script() 改寫:
                              # 0–18s 對照鏡 → 18–28s 狀態熱圖 → 28–38s 真實硬體
                              # → 38–55s 其他亮點 → 55–60s 收尾
tests/
└── test_widget_smoke.py     # 10 cases — module import / GPU 建構 /
                              # kernel queue pipeline / 對照鏡 end-to-end /
                              # cinema 劇本結構驗證 / 完整 Tiny8 ISA 跑短程式
SCREENSHOTS_GUIDE.md         # 三個 deadline 各自需要的畫面 checklist
```

### 第十四輪待辦狀態

- [x] CHANGELOG round 14 區段(本段)
- [x] `cinematic.py` 改寫 — 🪞 對照鏡 開場 + 重新分配時段
- [x] `test_widget_smoke.py` — 10 case integration smoke
- [x] `SCREENSHOTS_GUIDE.md` — demo / 報告 / 家庭錄影 截圖清單
- [x] 全套 **318 tests passing(308 + 10),ruff 0 issues**

### 教學意義:demo 影片就緒度

`gpu-simulator --cinema` 現在的 60 秒劇本**第一個畫面就是專題論述**。
觀眾看完前 18 秒就能講出「啊,這個是模擬 GPU 跟真實 CPU 並排對照」 — 比
舊版開場就跳到「即時」分頁(看不出特色)強多了。

`SCREENSHOTS_GUIDE.md` 把三份截圖需求(demo / 報告 / 家庭)拆開列,
按 checklist 拍完就可以直接交。

---

## 2026-05-24 · 第十五輪對齊:一鍵安裝(給組員用)

### 第十五輪使用者要求

> 「能不能直接幫我打包成一鍵安裝 這樣對每個人都方便」

組員是 商管系學生,不一定會用 PowerShell。
目標:**雙擊 `.bat` 檔就跑完**,不用打開終端機。

### 兩條路徑的取捨

| 方案 | 工作量 | 組員需要什麼 | 輸出 | 風險 |
| ---- | ---- | ---- | ---- | ---- |
| `.bat` / `.sh` 安裝腳本 | 30 分鐘 | 預裝 Python 3.10+ | 4 個小腳本 | 低 |
| PyInstaller `.exe` 打包 | 1–2 小時(首次往往要排錯) | **完全不用 Python** | 150 MB 單檔 | 中:PySide6 + matplotlib + pynvml 都要手動 bundle |

**選 `.bat`** — 99% 案例夠用,工作量小、可預測。PyInstaller 留作後續。

### 第十五輪交付清單

```text
gpu_simulator/                        ← repo 根目錄(組員下載後就看到這些)
├── 安裝.bat            # 一鍵安裝(自動 venv + pip install)
├── 啟動.bat            # 雙擊一般啟動
├── 錄影模式.bat        # 雙擊跑 60 秒 demo
├── 硬體儀表板.bat      # 雙擊開到「💻 真實硬體」分頁
├── install.sh          # Mac / Linux 版安裝
└── start.sh            # Mac / Linux 版啟動(吃 --cinema / --monitor 等 arg)
```

### `.bat` 設計重點

- 全部用 `chcp 65001` 確保中文 / emoji 正確顯示
- 自動偵測 Python 是否存在;沒裝會 `start https://www.python.org/downloads/`
  幫使用者開瀏覽器
- 自動進入 .bat 所在資料夾(`cd /d "%~dp0"`),不管使用者從哪雙擊
- 用 errorlevel 偵測每步是否成功,出錯時 pause 讓使用者看得到訊息
- 啟動類的 .bat 會先檢查 .venv 是否存在,沒裝會引導使用者去跑安裝

### 第十五輪待辦狀態

- [x] CHANGELOG round 15 區段(本段)
- [x] `安裝.bat` — Python 偵測 + venv + pip install
- [x] `啟動.bat` — 一般模式
- [x] `錄影模式.bat` — `--cinema` flag
- [x] `硬體儀表板.bat` — `--monitor` flag
- [x] `install.sh` + `start.sh` — Mac/Linux 版
- [x] `組員使用指南.md` 更新 — 雙擊路徑變第一順位、命令列路徑退為進階
- [x] 318 tests still passing, ruff 0 issues

### 教學意義:對組員 / 對非技術使用者

之前的安裝步驟對 商管系學生太陡:他們可能從沒打開過 PowerShell。
現在的流程是:

1. 從 GitHub 下載 ZIP → 解壓縮
2. 雙擊 `安裝.bat`(看著它跑一分鐘)
3. 雙擊 `啟動.bat`

**完全沒打字、沒看到任何命令列**。
讓專題的可及性從「會寫 Python 的人」拓寬到「會雙擊滑鼠的人」。

---

## 2026-05-24 · 第十六輪對齊:真正的「免 Python」一鍵 .exe

### 第十六輪使用者要求

> 「要」(同意把 .bat 路徑進階成 PyInstaller .exe 打包)

讓組員從「需要先裝 Python」升級到「下載 .zip → 解壓 → 雙擊 .exe → 跑起來」,
真正不需要任何前置條件。

### 過程紀錄

1. **準備 entry point** — `gpu_simulator_main.py`(repo 根目錄)直接 import
   `gpu_simulator.cli.main`,讓 PyInstaller 有一個明確的 freeze 起點
2. **寫 `gpu_simulator.spec`** —
   - `collect_submodules("gpu_simulator")` 抓所有子模組(含 vendored tiny8_full)
   - 顯式加 `matplotlib.backends.backend_qtagg` / `PySide6.QtSvg` 等 hidden imports
   - 排除可選相依(pynvml / GPUtil / pyttsx3 / anthropic)減肥
   - `console=False`:雙擊 .exe 不會跳黑色 console 視窗
   - `--onedir` 而非 `--onefile`:啟動快、出錯好除錯
3. **首次打包** — 7 萬行 PyInstaller log 後跑出 `dist/GPU-Simulator/`,8.4 MB .exe + 177 MB folder
4. **首次測試** — `.exe --version` 印出 `0.10.0`(過);`.exe` 啟動 widget 印出 traceback:
   `WidgetConfig 沒有 refresh_ms 屬性`(這是第十二輪埋的 bug,因為 smoke test 沒完整啟動 widget 抓不到)
5. **修 bug** — `widget.py:2248` 改 `refresh_ms` → `tick_interval_ms`
6. **重新打包** — 重跑 PyInstaller,`.exe`、`.exe --cinema`、`.exe --monitor` 三種模式都乾淨啟動

### 第十六輪交付清單

```text
gpu_simulator/                        ← repo 根目錄
├── gpu_simulator_main.py             # PyInstaller entry point
├── gpu_simulator.spec                # PyInstaller spec(commit)
├── 打包.bat                          # 一鍵打包(call pyinstaller)
├── .gitignore                        # 新增 build/ dist/ *.exe *.zip
└── (build/ dist/ 不進 git)
```

### 修掉的 bug

- `widget.py:2248` — `self._widget_config.refresh_ms` 應為 `tick_interval_ms`
  (從 PyInstaller 跑出的 traceback 抓到的;單元測試覆蓋不到 status bar refresh tick)

### 第十六輪待辦狀態

- [x] CHANGELOG round 16 區段(本段)
- [x] `gpu_simulator_main.py` PyInstaller entry point
- [x] `gpu_simulator.spec` config
- [x] `打包.bat` 一鍵打包腳本
- [x] `.gitignore` 加 build/ dist/ *.exe
- [x] 修 widget.py refresh_ms bug
- [x] 實際打包 + 三種啟動模式測試通過
- [x] `組員使用指南.md` 加「最簡單路徑:下載 .exe」段落
- [x] 318 tests passing, ruff 0 issues

### 教學意義:可及性的最後一哩路

組員 / 觀眾現在有 **3 層難度** 可選:

| 難度 | 步驟 | 適合誰 |
| ---- | ---- | ---- |
| 🏆 最簡單 | 下載 .zip → 解壓 → 雙擊 .exe | 完全不會程式的人,連 Python 都不裝 |
| 🚀 中等 | 下載 repo → 雙擊 安裝.bat → 雙擊 啟動.bat | 有 Python,不會 PowerShell |
| 🛠️ 進階 | `git clone` → `python -m venv .venv` → `pip install -e .` → `gpu-simulator` | 一般開發者 |

打包流程本身(`打包.bat`)讓 Shana 之後改完程式碼後,**雙擊一次就能重出新版 .exe**
上傳到 GitHub Releases。從程式碼到可分發產品的距離從以前的「先教組員裝 Python」變成
「上傳一個 .zip」。

---

## 2026-05-24 · 第十七輪對齊:從 onedir 改成 --onefile 單一檔

### 第十七輪使用者要求

> 「不行 你打包成單一安裝檔 exe」

第十六輪輸出的是 onedir(177 MB 資料夾 + 一個 8.4 MB .exe),要組員下載整個 zip
解壓 → 雙擊。使用者要更直接的:**單一檔案,下載一個 .exe,雙擊**。

### 兩種模式對比

| 項目 | --onedir(R16) | **--onefile(R17 新)** |
| ---- | ---- | ---- |
| 輸出檔案 | `dist/GPU-Simulator/` 整個資料夾 | `dist/GPU-Simulator.exe` 單檔 |
| 總大小 | 177 MB(資料夾) | **75 MB**(自動 dedupe + 內部壓縮) |
| 首次啟動 | 2–3 秒 | **5–10 秒**(內部解壓到 %TEMP%) |
| 第二次同 boot 啟動 | 2–3 秒 | 2–3 秒(快取在 %TEMP%) |
| 分發 | 整個資料夾要 zip | **直接傳一個 .exe 給組員** |
| GitHub Release | 上傳 .zip | **上傳 .exe** |

對組員體驗來說 onefile 顯著勝出:沒有「解壓」這個步驟、沒有「.exe 在哪個資料夾」的混淆。

### `gpu_simulator.spec` 改動

```diff
 exe = EXE(
     pyz,
     a.scripts,
+    a.binaries,        # binaries 直接塞進 .exe
+    a.datas,           # datas 直接塞進 .exe
     [],
-    exclude_binaries=True,
     name="GPU-Simulator",
+    runtime_tmpdir=None,
     ...
 )
-coll = COLLECT(exe, a.binaries, a.datas, ...)  # 移除
```

### 第十七輪驗證

```text
$ ./dist/GPU-Simulator.exe --version
0.10.0

$ ls -lh dist/
total 75M
-rwxr-xr-x ... 75M ... GPU-Simulator.exe
```

單一 75 MB 檔案,`--version` 1.9 秒回覆。

### 第十七輪待辦狀態

- [x] CHANGELOG round 17 區段(本段)
- [x] `gpu_simulator.spec` 改 --onefile
- [x] 重新打包驗證
- [x] `打包.bat` 更新訊息(75 MB 單檔)
- [x] `組員使用指南.md` 更新 — 不再需要解壓、加 SmartScreen 提示
- [x] 318 tests still passing, ruff 0 issues
