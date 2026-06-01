# gpu_simulator

> **互動式 CPU↔GPU 視覺化教學模擬器 + 個人電腦硬體儀表板。**
> 把計算機架構課本裡那些抽象的概念(暫存器、kernel、warp pipeline),
> 用白話中文介面 + 真的可以跑的程式指令,變成**看得見、可以操作、可以重來**的東西;
> 同一個視窗還能看自己電腦當下 N 顆 CPU 核心 + 真實顯卡在幹嘛。
>
> 商管程式設計 114-2 期末專題 · 100% Python · PEP 8 · 315 個測試 · 全綠。
> 完整提案見 [PROJECT_BRIEF.md](PROJECT_BRIEF.md)。

## 🎯 14 個核心分頁(第 23 輪精簡)

打開 widget 看到的順序:

```
🪞 對照     左:模擬 GPU 8 SM    右:真實 CPU N 核 並排
🌡️ 變化     寫程式 → 看 CPU 內部小格子(暫存器)隨每一拍變化色塊圖
💻 硬體     你電腦每顆 CPU 核心 + NVIDIA 顯卡即時負載
⚡ 即時     滑鼠/鍵盤觸發 GPU 工作,看 8 顆 SM 反應
🎬 Cinema   CPU/GPU 同框慢動作播放
🧬 完整 CPU  內嵌真正的 Tiny8 CPU,60+ 條指令
⌨️ 寫程式   組合語言(ASM)編輯器
📜 逐拍     每一拍紀錄表,點任一列時光旅行
🐞 內部     CPU 內部觀察(暫存器格 + 記憶體格)
📊 演化     暫存器/記憶體隨時間演化色塊圖
🔁 對話     CPU/GPU 兩條時間線時序圖
🗺️ 記憶     256 byte 記憶體地圖
🏗️ 3D      8 顆 SM 立體高塔
🧠 進階     warp 分歧 / 記憶體合併存取
```

**第 23 輪砍掉**:🎮 ASM 遊戲機(Conway's Life)/ 📈 Analytics 趨勢圖 / 📚 過去執行紀錄 — 與主論述關聯較少,留下 14 個聚焦的分頁讓觀眾更專注。

## 🚀 三秒啟動(給組員)

**最簡單** — 從 GitHub 下載 [`一鍵安裝包.exe`](一鍵安裝包.exe)(約 75 MB),
雙擊執行。完全不用裝 Python,完全不用解壓任何資料夾。

第一次跑可能要等 5–10 秒(內部自我解壓),之後就快。
Windows SmartScreen 跳警告就點「其他資訊」→「仍要執行」。

| 想做什麼 | 怎麼跑 |
| ---- | ---- |
| 一般啟動 | 雙擊 `一鍵安裝包.exe` |
| 60 秒自動 demo | 同資料夾 Shift+右鍵 → 開啟 PowerShell → `.\一鍵安裝包.exe --cinema` |
| 純看 CPU/GPU 儀表板 | `.\一鍵安裝包.exe --monitor` |

### 🐛 如果打開後跑不動 / 點不到任何東西

**最有可能的原因** — 之前的版本用了「無邊框 + 半透明 + 永遠置頂」的桌面 widget 風格,
在某些 Windows 環境會視窗存在但無法接收滑鼠點擊。**第 20 輪起改用標準視窗**
(有標題列、X 鈕、在 taskbar 看得到、不透明),這個問題應該不會再發生。

**如果還是有問題**:

| 症狀 | 解法 |
| ---- | ---- |
| 雙擊 `.exe` 完全沒反應 | 開 Task Manager(Ctrl+Shift+Esc),殺所有殘留的 `GPU-Simulator.exe` / `一鍵安裝包.exe`,再雙擊一次 |
| 視窗看得到但點不到 | 把視窗拖一下、或從工作列右鍵「最大化」一次再恢復 |
| 視窗開不出來 | 確認 `.exe` 不是被防毒軟體鎖住、或被 SmartScreen 擋下;改用 `啟動.bat`(dev 模式)會更穩 |
| 「GPU Simulator 已經在執行」訊息框 | 桌面已經有一份在跑,從工作列找已開的視窗 |

## 三大支柱 + 對照鏡(這個專案到底在幹嘛)

| 支柱 | 主要分頁 | 你會看到 |
| ---- | ---- | ---- |
| ① **模擬層**(教學核心) | 🌡️ 狀態熱圖、🎬 Cycle Cinema、即時 / Trace | 寫 Tiny8 ASM → cycle-by-cycle 暫存器/記憶體/SREG 熱圖、8 SM × 4 warps 平行跑 |
| ② **教學體驗** | 課堂、考考你、AI 解釋、實驗報告 | 中文 5 課教學、互動 quiz、Claude API 解釋 trace、自動 Markdown 報告 |
| ③ **真實硬體** | 💻 真實硬體 | 你電腦現在 N 顆邏輯 CPU 核心每顆即時負載、頻率、處理程序數;NVIDIA GPU 利用率/記憶體/溫度/功耗 |
| **🪞 對照鏡** | 🪞 對照鏡(第 1 分頁) | 上面三支柱的整合畫面:左邊模擬 GPU 8 SM、右邊真實 CPU N 核並排,按一鍵觸發模擬負載,看左邊飆高右邊不動 — 30 秒看完整個專題論述 |

---

## ✨ 功能一覽

- **完整模擬 GPU 架構**:Streaming Multiprocessor × 8、每 SM 4 warps、每 warp 32 threads(可調)。
- **5 階 pipeline**:fetch → decode → execute → memory → writeback。
- **幾乎所有 OS 行為都會觸發對應 kernel**:

  | 行為 | 觸發的 kernel | 特性 |
  | ---- | ------------- | ---- |
  | 滑鼠點擊 | `vector_add` | compute-bound |
  | 滑鼠移動 (節流) | `interpolation` | 極短、低佔用 |
  | 鍵盤按鍵 | `hash(<key>)` | 中等 mixed |
  | 切換前景視窗 (換 app) | `texture_load:<app>` | memory-bound、高 VRAM |
  | 同一 app 內切換分頁/輸入網址 | `page_nav:<title>` | 混合 |
  | 系統出現新 process (開新 app) | `app_launch:<name>` | 大型 + 長持續 |
  | 閒置 ≥ 5 秒 | `idle_compression` | 背景、低功耗 |

- **十四個分頁**:Live / Analytics / History / Trace / Debug / Heatmap / 🔁 時序圖 / 🗺️ 記憶體 / 🎬 Cycle Cinema / 🏗️ 3D 視圖 / 🎮 遊戲機 / 🧠 進階 GPU / Input / 🧬 Tiny8 完整版
  - **Live** — SM 熱圖、VRAM bar、pipeline、event log
  - **Analytics** — 以 matplotlib 畫 SM 利用率 + VRAM 時序曲線(嵌入 Qt)
  - **History** — 列出過去 session,可 Replay 或匯出 CSV / Markdown / PNG
  - **Trace**(**v0.6 升級**)— 逐 cycle 表格 + **行色碼**(KLAUNCH 橘 / KWAIT 藍 / HALT 紅 / stall 灰 / 分支黃 / 記憶體青)+ 右側 **中文導讀**側欄即時吐解說。**點任一列即可時光旅行** — Debug / 記憶體 / 時序圖 同步顯示那個 cycle 的狀態
  - **Debug** — Tiny8 CLI debugger 風格:黑底 monospace + 32 個暫存器格 + 0x60–0x7F 記憶體格,變動格子高亮
  - **Heatmap** — Tiny8 動畫風格:matplotlib 三層 imshow(SREG / R0–R31 / 記憶體 0x60–0x7F 隨 step 演化)
  - **🔁 時序圖**(**v0.6 新**)— UML 風 CPU/GPU 兩條 lane,KLAUNCH 用橘色實線箭頭往下、kernel 完成用綠色虛線箭頭往上;點 Trace 列 → 這裡用黃色亮線標出對應位置
  - **🗺️ 記憶體**(**v0.6 新**)— 256 byte 全圖,GPU 控制暫存器(0x40 LAUNCH / 0x41 HINT / 0xFF KWAIT)三色標示,使用者資料區(0x60–0x7F)另色
  - **Input** — ASM 編輯器(子集 ISA)+ Steam 風範例庫
  - **🧬 Tiny8 完整版**(v0.5)— 並排視圖:左是**內嵌的真正 Tiny8 CPU**(60+ 指令完整 ISA);右是虛擬 GPU;中間是 kernel 流向箭頭。寫到 RAM 0x40 / 0xFF 即觸發 GPU 工作。

- **Tiny8 子集 CPU + 組譯器**(模組 `cpu.py`):32 個暫存器、SREG 4 旗標(Z/N/C/V)、
  ISA 涵蓋 LDI / MOV / ADD / SUB / INC / DEC / CP / CPI / JMP / BRNE / BREQ / NOP / HALT / IN / OUT,
  並提供 GPU bridge 別名 `KLAUNCH Rr` / `KWAIT` / `KSTAT Rd`。

- **CPU↔GPU bridge**(模組 `bridge.py`):用 I/O port 風格(0x40 / 0x41 / 0xFF)
  把 CPU 跟虛擬 GPU 串起來,每個 cycle 產生一筆 `TraceRow`,給 Trace 分頁即時顯示。

> **逐輪累積的功能(v0.4 → v0.10)整理在文件底部的
> [「📚 各版本累積功能歷程」](#各版本累積功能歷程) 章節**,以免主敘事被淹沒。

- **Real GPU 並排監控** (`--real`):用 `pynvml` / `GPUtil` 讀取本機 NVIDIA GPU
  的 util / 記憶體 / 溫度 / 功耗,顯示於 widget 下方;沒有 NVIDIA 時自動降級,
  不影響虛擬 GPU 區塊運作。

- **SQLite session store**:每次開啟都自動建立一個 session,紀錄
  events、snapshots、kernel 提交;關閉時自動收尾。可完整回放。

- **JSON 可擴充設定檔**:`~/.gpu_simulator/config.json`(或自選檔案)
  可改 GPU 規格、widget 尺寸、idle 閾值、以及「事件 → kernel 對應表」。

- **無邊框、半透明、永遠置頂、可拖曳**的桌面 widget,
  關閉鈕在右上角。

---

## 🧱 專案結構

```text
gpu_simulator/
├── proposal.md                   # 期末專案計劃書(5/10 截止)
├── CHANGELOG_REQUIREMENTS.md     # 使用者需求逐條鎖定(持續更新)
├── README.md                     # 本檔
├── pyproject.toml
├── configs/
│   └── default.json              # 預設設定檔
├── src/gpu_simulator/
│   ├── __init__.py
│   ├── core.py                   # GPU / SM / Warp / 模擬主迴圈
│   ├── memory.py                 # VRAM / SharedMemory / RegisterFile
│   ├── scheduler.py              # WarpScheduler + 5 階 pipeline
│   ├── kernel.py                 # Kernel + KernelLibrary(7 種 kernel)
│   ├── cpu.py                    # Tiny8 子集 CPU + 256-byte 記憶體 + 組譯器
│   ├── bridge.py                 # 子集 CPU↔GPU bridge,產生 TraceRow / 三層 history
│   ├── tiny8_full/               # vendor 進來的真正 Tiny8 CPU(60+ 指令)+ MIT LICENSE
│   ├── full_bridge.py            # 完整 Tiny8 ↔ GPU bridge(subclass + write_ram 攔截)
│   ├── exceptions.py             # 自定義例外階層
│   ├── config.py                 # JSON 設定檔讀寫 + trigger mapping 驗證
│   ├── persistence.py            # SQLite session store (4 張表)
│   ├── exporter.py               # CSV / JSON / Markdown / PNG 匯出
│   ├── real_gpu.py               # pynvml / GPUtil 包裝,真實 GPU 取樣
│   ├── event_listener.py         # OS 事件攔截 + ProcessWatcher + 標題變動
│   ├── i18n.py                   # 中文字串字典(集中管理 80+ 條)
│   ├── sounds.py                 # 音效模組(winsound + Qt 降級)
│   ├── gpu_pet.py                # GPU 寵物表情元件
│   ├── achievements.py           # 成就 + SQLite achievements 表 + tracker
│   ├── quiz.py                   # 考考你題庫 + 動態題目
│   ├── recorder.py               # 內建 GIF 錄影
│   ├── dialogs.py                # 歡迎 / 獎盃室 / 考試 / 成就通知 / PresetMenu / DemoTab
│   ├── visualizer.py             # 子視覺化 Qt 元件(matplotlib + TraceTable + AsmInputPanel + DebugView + HeatmapView)
│   ├── widget.py                 # 主桌面視窗(7 分頁 + 寵物 + 工具列 + mode 狀態機 + easy 模式)
│   └── cli.py                    # `gpu-simulator` 進入點(`--easy` / `--no-welcome` / `--real` / …)
├── examples/
│   ├── hello_gpu.asm             # 最小 CPU↔GPU 範例 ★☆☆☆☆
│   ├── burst_and_count.asm       # 連發三顆 + 讀回完成數 ★★☆☆☆
│   ├── loop_kernel.asm           # DEC/BRNE 迴圈發 kernel ★★☆☆☆
│   ├── memory_copy.asm           # 記憶體 copy(LD/ST 示範)★★★☆☆
│   ├── sort_three.asm            # 比較與條件分支(SREG 旗標教學)★★★☆☆
│   ├── find_max.asm              # 掃過記憶體陣列 + 連續提交 ★★★☆☆
│   ├── counter.asm               # 倒數計時器 + 階梯狀記憶體軌跡 ★★☆☆☆
│   ├── mixed_burst.asm           # 一次提交 7 種 kernel,混合工作負載 ★★★★☆
│   ├── full_fibonacci.asm        # 完整 Tiny8:F(10)=55 + GPU hash kernel ★★★☆☆
│   ├── full_bubble_sort.asm      # 完整 Tiny8:RJMP/BRCS bubble sort + 雙 kernel ★★★★☆
│   ├── full_gcd_gpu.asm          # GCD + 每 iter checkpoint kernel ★★★☆☆
│   ├── full_count_bits_gpu.asm   # popcount + 每 set-bit 一顆 kernel(用 LSR / ANDI)★★★☆☆
│   ├── full_factorial_gpu.asm    # 用 MUL 算 5! + 5 顆 kernel ★★★★☆
│   ├── full_histogram_gpu.asm    # 16 sample 分 4 桶 + 16 顆 kernel ★★★★☆
│   └── full_matrix_diagonal_gpu.asm  # 8×8 對角線寫 1 + 每列一顆 kernel ★★★★☆
└── tests/
    ├── test_core.py / test_memory.py / test_scheduler.py
    ├── test_kernel.py / test_kernel_library_dispatch.py
    ├── test_cpu.py / test_bridge.py / test_memory_ops.py
    ├── test_exceptions.py / test_config.py / test_persistence.py
    ├── test_exporter.py / test_real_gpu.py / test_event_listener.py
    ├── test_i18n.py                     ← 新
    ├── test_achievements.py             ← 新
    ├── test_quiz.py                     ← 新
    ├── test_pet_and_sounds.py           ← 新
    ├── test_new_examples.py             ← 新
    └── test_full_bridge.py              ← v0.5 新(完整 Tiny8 ↔ GPU 端到端)
```

**模組分層理念**:`core / memory / scheduler / kernel / exceptions / config /
persistence / exporter / real_gpu` 都只用 Python stdlib(或 matplotlib);
`event_listener` 用 `pynput` + `psutil`;`visualizer / widget` 用 `PySide6`。

- 只想用 library / 跑測試 → 不用裝 Qt。
- CI / headless 環境下,上述所有模組都能正常測試。
- 想自己做 UI → 接 `GPU.snapshot()` + `SessionStore` 就好。

---

## 🎓 對應課堂六項進階技術 · 6/6 全數使用

這份專案的重要設計目標是把課堂教的六項進階技術**全部**在合情合理的地方用上:

| 進階技術 | 使用位置 |
| -------- | -------- |
| **自定義類別** | 幾乎每個檔案都有 class:`GPU / StreamingMultiprocessor / Warp / VRAM / SharedMemory / RegisterFile / Kernel / KernelLibrary / WarpScheduler / EventListener / KernelQueue / AppConfig / SessionStore / SessionExporter / RealGPUSampler / GPUVizWidget` 等 |
| **進階資料結構** | `deque`(event log、分析頁歷史)、`dict`(trigger mapping、snapshot 樹)、`Enum`(`WarpState` / `PipelineStage` / `WorkloadProfile`)、`dataclass`、`tuple`、`datetime`(session 時間戳) |
| **檔案輸入輸出** | `config.json` 讀寫;session 匯出 CSV / JSON / Markdown / PNG;載入歷史 session |
| **例外處理** | [`exceptions.py`](src/gpu_simulator/exceptions.py) 自定義階層 `GPUVizError → GPUError / VRAMOverflowError / KernelSubmissionError / ConfigError / PersistenceError / RealGPUUnavailableError`;各模組邊界統一 raise/catch |
| **圖形化介面** | [PySide6](src/gpu_simulator/widget.py)(Qt for Python,符合課綱「tkinter 或類似」之規定);三個分頁 + matplotlib 嵌入 Qt |
| **資料庫** | [`persistence.py`](src/gpu_simulator/persistence.py) 用 Python 內建 `sqlite3`;schema 含 `sessions / events / snapshots / kernel_submissions` 四張表 + 索引 |

---

## 🚀 安裝

需要 **Python ≥ 3.10**。

```bash
cd gpu_simulator
python -m pip install -e .
```

若要啟用 `--real` 真實 GPU 對照模式:

```bash
python -m pip install -e ".[realgpu]"
```

主要相依套件:

| 套件 | 用途 |
| ---- | ---- |
| `PySide6` | 桌面 UI(Qt 6) |
| `pynput` | 跨平台鍵鼠事件攔截 |
| `psutil` | 前景視窗行程名 / 偵測新 process |
| `matplotlib` | Analytics 分頁 + PNG 匯出 |
| `pynvml` / `GPUtil`(可選) | 真實 GPU 讀值 |

> **Windows**:第一次執行前景視窗偵測時可能需要授權。
> **macOS**:需要在「系統設定 → 隱私權 → 輔助使用 / 輸入監控」開放終端機。
> **Linux(X11)**:前景視窗偵測需要 `xdotool`;Wayland 目前不支援。

---

## ▶️ 執行

### 一、啟動小工具

```bash
gpu-simulator                         # 桌面上出現永遠置頂 widget
python -m gpu_simulator.cli           # 同上,不依賴 entry point
```

### 二、常用 flag

```bash
gpu-simulator --easy                  # 給爸媽看模式:UI 簡化、自動循環播範例
gpu-simulator --no-welcome            # 不要顯示首次啟動的歡迎對話
gpu-simulator --real                  # 真實 GPU 對照模式
gpu-simulator --no-db                 # 本次不寫 SQLite
gpu-simulator --config path/to/x.json # 載入自訂設定檔
gpu-simulator --sms 16 --vram 1024    # 臨時改 GPU 規格
gpu-simulator --tick 50               # 更流暢(50 ms / tick)
gpu-simulator --version
```

### 三、程式庫 API

```python
from gpu_simulator import GPU, KernelLibrary, SessionStore, SessionExporter

gpu = GPU()
gpu.submit_kernel(KernelLibrary.vector_add())
for _ in range(30):
    gpu.tick()

# 直接取 snapshot 餵你自己的 UI
snapshot = gpu.snapshot()
print("overall utilization:", snapshot["overall_utilization"])

# 或把 session 存起來之後匯出 Markdown 報告
with SessionStore(":memory:") as store:
    session_id = store.start_session("demo")
    store.record_snapshot(
        clock=snapshot["clock"],
        overall_utilization=snapshot["overall_utilization"],
        vram_used_bytes=snapshot["vram"]["used_bytes"],
        snapshot=snapshot,
    )
    store.end_session(session_id)
    SessionExporter(store).to_markdown(session_id, "session.md")
```

---

## 🗃️ SQLite Schema

```sql
sessions(id, name, started_at, ended_at, kernels_seen, ticks_observed)
events(session_id, clock, message, recorded_at)
snapshots(session_id, clock, overall_utilization, vram_used_bytes, snapshot_json, recorded_at)
kernel_submissions(session_id, clock, kernel_name, profile, trigger,
                   grid_size, block_size, vram_bytes, recorded_at)
```

Index:`(session_id, clock)` 覆蓋 3 張子表。

預設 DB 位置:`~/.gpu_simulator/sessions.sqlite3`
(可在 `config.json` 的 `persistence.database_filename` 改)。

---

## ⚙️ 設定檔

預設優先序:**CLI `--config` > `~/.gpu_simulator/config.json` > `configs/default.json`**。

`configs/default.json` 內容自文件化,關鍵區塊:

```json
{
    "trigger_mapping": {
        "mouse_click":  {"kernel": "vector_add"},
        "mouse_move":   {"kernel": "interpolation"},
        "key_press":    {"kernel": "hash"},
        "focus_change": {"kernel": "texture_load"},
        "page_nav":     {"kernel": "page_nav"},
        "app_launch":   {"kernel": "app_launch"},
        "idle":         {"kernel": "idle_compression"}
    }
}
```

想改成「每次打字都觸發 `vector_add`」只要把 `key_press.kernel` 改成 `vector_add`
即可,不用改程式。未知 kernel 名會在啟動時 raise `ConfigError` 直接告訴你。

---

## 🎛️ UI 控制

| 操作 | 效果 |
| ---- | ---- |
| 拖曳視窗 | 移動小工具 |
| 點右上角 `×` | 關閉並停止事件攔截、收尾 session |
| 切換上方分頁 | Live / Analytics / History / Trace / Input |
| 在 History 選 session → Replay | 載入歷史 snapshots 並在 Live 分頁重播 |
| 在 History 選 session → CSV/Markdown/PNG | 匯出至 `~/.gpu_simulator/exports/` |
| 任何 OS 操作 | 自動觸發對應 kernel |
| 在 Input 分頁按 Run | 暫停 OS 事件監聽,組譯 + 執行 asm,Trace 分頁即時更新 |
| 按 Step | 單步執行,可逐 cycle 觀察 |
| 按 Reset | 清除 trace、退回 Live 模式、重新啟動 OS 監聽 |

---

## 🧮 Tiny8 風格 CPU + ASM 模式(Trace / Input 分頁)

### Tiny8 子集 ISA

| 類別 | 指令 |
| ---- | ---- |
| 資料移動 | `LDI Rd, K` / `MOV Rd, Rr` / `IN Rd, port` / `OUT port, Rr` |
| 記憶體存取 | `LD Rd, Rr` / `ST Rr, Rs` / `LDS Rd, K` / `STS K, Rr` |
| 算術 | `ADD Rd, Rr` / `SUB Rd, Rr` / `INC Rd` / `DEC Rd` |
| 比較 | `CP Rd, Rr` / `CPI Rd, K` |
| 控制流 | `JMP label` / `BRNE label` / `BREQ label` / `NOP` / `HALT` |
| GPU bridge 別名 | `KLAUNCH Rr` / `KWAIT` / `KSTAT Rd` |

CPU 自有一塊 **256 byte 平面記憶體**(`LD`/`ST` 用暫存器當位址,`LDS`/`STS` 用立即位址),
這也是 Heatmap 分頁第三層熱圖的資料來源。

- **暫存器**:R0–R31(32 個 8-bit)
- **狀態旗標**:Z(zero)/ N(negative)/ C(carry)/ V(overflow)
- **立即數**:支援十進位、`0xFF` / `$FF`(16 進位)、`0b1111`(2 進位)
- **註解**:`;` 開頭至行尾
- **標籤**:`my_label:` 自成一行

### CPU↔GPU port 對應(I/O 風格,與 Tiny8 一致)

| port | OUT 寫入時 | IN 讀取時 |
| ---- | ---------- | --------- |
| `0x40` | 提交對應 id 的 kernel(就是 `KLAUNCH`) | 回報尚未完成的 kernel 數(`KSTAT`) |
| `0x41` | 設定下一個 kernel 的整數 hint | 回報已完成 kernel 數 mod 256 |
| `0xFF` | 觸發 KWAIT,CPU 停在原地直到 GPU 全部完成 | — |

### Kernel id 對應表

| id | kernel |
| -- | ------ |
| 0 | vector_add |
| 1 | interpolation |
| 2 | hash |
| 3 | texture_load |
| 4 | idle_compression |
| 5 | app_launch |
| 6 | page_nav |

### 範例 .asm(在 `examples/` 內)

[hello_gpu.asm](examples/hello_gpu.asm) — 最小可用的 CPU↔GPU 程式:

```asm
    ldi r16, 0          ; r16 = vector_add id
    klaunch r16         ; 提交一顆 vector_add
    kwait               ; CPU 卡到 GPU 完成
    halt
```

[burst_and_count.asm](examples/burst_and_count.asm) — 連續發三顆不同 kernel,KWAIT 後讀回完成數量。

[loop_kernel.asm](examples/loop_kernel.asm) — 用 `DEC` + `BRNE` 迴圈三次發 interpolation kernel,展示控制流。

[memory_copy.asm](examples/memory_copy.asm) — **Tiny8 經典範例的 GPU 加強版**:把 RAM[0x60..0x65] 複製到
RAM[0x70..0x75],最後再丟一顆 `vector_add` 給 GPU。把這支貼進 Input 跑,**Heatmap** 分頁的記憶體
熱圖會顯示出跟 Tiny8 動畫同款的階梯狀填色。

> 把這些檔案的內容貼進 widget 的 **Input** 分頁,按 **Run**,就會切到 **Trace** 分頁看到 Tiny8 風格的逐 cycle 執行表(變動格子高亮)。
> 同時 **Debug** 分頁顯示當下狀態(類似 Tiny8 CLI debugger),**Heatmap** 分頁顯示時序熱圖(類似 Tiny8 `-m ani` 輸出)。

### Trace 表格欄位

| 欄位 | 說明 |
| ---- | ---- |
| Cycle | 從 1 起算的累計 cycle 數(`C0001`、`C0002`…) |
| PC | 該 cycle 執行的指令位址(16 進位) |
| Instruction | 原始指令文字(KWAIT 期間顯示 `; KWAIT (stalled)`) |
| SREG | 4 旗標目前狀態,字母為設、`-` 為清(例:`Z-C-`) |
| R changes | 該 cycle 發生變動的暫存器(以 `R16=42` 列出) |
| GPU | 各 SM 上忙碌 warp 的 pipeline 階段(`F`/`D`/`E`/`M`/`W`) |

---

## 🧪 測試

```bash
python -m pytest
# 或取得覆蓋率
python -m pytest --cov=src/gpu_simulator --cov-report=term-missing
```

目前 **203 個測試案例全數通過**(`ruff check` 也是 0 issues),覆蓋非 Qt 的所有模組:

| 測試檔 | 內容 |
| ------ | ---- |
| `test_memory.py` | VRAM / SharedMemory / RegisterFile |
| `test_kernel.py` | Kernel dataclass + library |
| `test_kernel_library_dispatch.py` | 新增的 `app_launch` / `page_nav` / `build()` dispatcher |
| `test_scheduler.py` | FIFO 展開與 pipeline 順序 |
| `test_core.py` | 提交、tick、完成、VRAM 拒絕、reset |
| `test_cpu.py` | Tiny8 子集 CPU 語義 + 組譯器 + KLAUNCH/KWAIT/KSTAT 別名 |
| `test_bridge.py` | CPU↔GPU 互動、KWAIT 卡停、TraceRow 產生 |
| `test_memory_ops.py` | LD / ST / LDS / STS、address wrap、記憶體變動快照、bridge 三層 history、memory_copy 端到端 |
| `test_exceptions.py` | 自定義例外階層 + strict 模式 |
| `test_config.py` | JSON load/save、錯誤處理、trigger mapping 驗證 |
| `test_persistence.py` | SQLite schema、CRUD、自動 end session |
| `test_exporter.py` | CSV / JSON / Markdown 匯出 |
| `test_real_gpu.py` | graceful degrade(無 GPU 不崩潰) |
| `test_event_listener.py` | KernelQueue 執行緒安全 drain |
| `test_i18n.py` | i18n 字典 fallback、kernel / trigger 中文別名 |
| `test_achievements.py` | 10 種徽章 unlock 邏輯、SQLite 持久化、tracker callback |
| `test_quiz.py` | 靜態 / 動態題庫產生、隨機種子可重現 |
| `test_pet_and_sounds.py` | GPU 寵物 5 階表情切換、音效靜默降級不爆炸 |
| `test_new_examples.py` | 8 支 .asm 都組譯成功並 HALT;`counter` / `mixed_burst` / `memory_copy` 結果驗證 |
| `test_full_bridge.py` | 內嵌 Tiny8 完整 ISA(MUL 等)、KLAUNCH/KWAIT 端到端、F(10)=55、bubble sort 排好結果 |
| `test_commentary.py` | 中文指令解說、事件分類(KLAUNCH/KWAIT/HALT/分支/記憶體)、Commentator 旁白 |
| `test_lessons.py` | 5 課內容齊全、每課 .asm 都能跑到 HALT、KLAUNCH 課真的有提交 kernel、第 5 課真的用到 MUL |
| `test_round8_examples.py` | 5 支 Tiny8-延伸範例:GCD=6、popcount(0xB7)=6、5!=120、histogram=[4,4,4,4]、對角線=[1]*8;每支提交的 kernel 數也都對 |
| `test_round9_modules.py` | 第九輪 8 個旗艦模組全部:每 kernel chord、Markdown 報告、daily challenge 穩定性、leaderboard 排序、AI 離線 fallback、Conway's blinker 週期 2、warp 發散因子、coalescing transactions、Web mirror HTTP /snapshot 端點 |

---

## 🏗️ 資料流

```text
┌───────────────────────────┐    OS events
│ EventListener +           │◀──── 鍵 · 滑 · 焦點 · 新 process · 閒置
│ ProcessWatcher + title    │
└─────────────┬─────────────┘
              │ Kernel (trigger_mapping 決定類型)
              ▼
┌───────────────────────────┐
│ KernelQueue (thread-safe) │
└─────────────┬─────────────┘
              │ GUI 主執行緒每 tick drain
              ▼
┌───────────────────────────┐       ┌───────────────────┐
│           GPU             │──────▶│   WarpScheduler   │
│  SM × 8 · Warp × 32       │       └─────────┬─────────┘
│  5-stage pipeline         │                 │ pop_ready()
│  VRAM / Shared / RF       │◀────────────────┘
└─────────────┬─────────────┘
              │ snapshot()  (plain dict,每 tick)
              ▼
┌───────────────────────────┐       ┌──────────────────────┐
│     GPUVizWidget          │       │    SessionStore      │
│  ┌─ Live tab              │──────▶│    (SQLite)          │
│  │  ├ SMGrid / VRAM bar   │       │  sessions / events   │
│  │  ├ Pipeline            │       │  snapshots / subs    │
│  │  └ EventLog            │       └──────────┬───────────┘
│  ├─ Analytics tab         │◀──── iter_snapshots (replay)
│  │  └ matplotlib canvas   │                  │
│  └─ History tab           │                  ▼
│     └ HistoryPanel  ──────┼───▶ SessionExporter ──▶ CSV/JSON/MD/PNG
│                           │
│  + RealGPUPanel (optional)│◀──── RealGPUSampler (pynvml / GPUtil)
└───────────────────────────┘
```

---

## 📝 需求變更流程

所有需求與設計決策集中在 [CHANGELOG_REQUIREMENTS.md](./CHANGELOG_REQUIREMENTS.md)。
目前已鎖定兩次對齊:

1. **2026-04-24 初始對齊** — 改寫自 Tiny8 的桌面 GPU 模擬器。
2. **2026-04-24 第二輪對齊** — 對齊商管程式設計期末專案 PDF 規格、
   把進階技術補到 6/6、擴大行為覆蓋至「打開 app / 輸入網址」、
   加上真實 GPU 追蹤選項。

未來新需求都請追加在該文件下方。

---

## 🎯 期末專案對照

對齊 `PBC114-2_project.pdf`:

| 評分項目 | 狀態 |
| -------- | ---- |
| 計劃書 (5 分) | [proposal.md](./proposal.md) 已撰寫骨架,待補組員名單 |
| 展示影片 (35 分) | UI 已完成,可錄 live + replay + analytics + 真實 GPU 對照 |
| 書面報告 (30 分) | 架構 / schema / 分層 / 例外階層 / 分工表皆已整理完成,可直接摘錄 |
| 組間互評 (5 分) | 專案外執行 |
| 組內互評 (15 分) | 專案外執行 |
| 家庭錄影 (10 分) | 專案外執行(widget 執行畫面清晰適合演示) |

---

## 📄 授權

MIT License。

---

## 📚 各版本累積功能歷程

本專題從 v0.4 累積到目前(v0.10+),每一輪都把不同面向的功能補上來。
為避免主敘事被淹沒,完整歷程收在這一段;點開來看每一輪做了什麼。

<details>
<summary><b>🚀 v0.8 升級:八項旗艦功能</b></summary>

| 旗艦 | 內容 |
| ---- | ---- |
| 🎮 **ASM 遊戲機** | Conway's Game of Life 跑在 Tiny8 + 虛擬 GPU 上;blinker / glider / 隨機 三種 seed,每代真的派 8 顆 GPU kernel |
| 🏗️ **3D GPU 視圖** | QPainter 自繪等距(isometric)立方體,8 顆 SM 排成 4×2 高塔,塔越高利用率越高;KLAUNCH 時頂上有橘色光球 |
| 📜 **自動實驗報告** | 一鍵產出 Markdown + 3 張 PNG 圖(CPU 狀態 timeline、暫存器 heatmap、記憶體 heatmap),內含中文逐行解說、事件統計、kernel 派送統計、自動摘要 |
| 🎵 **多音 chord 音效** | 7 種 kernel 各有自己的 chord 動機(vector_add 上行、idle 低頻長音…),用聽的就分得出 GPU 在做什麼 |
| 🏁 **每日挑戰 + 排行榜** | 每天用日期 hash 出題,3 種類型(`kernel_count` / `kernel_mix` / `memory_writes`),通過後上 SQLite leaderboard |
| 🤖 **AI 解釋器** | 用 Claude API 把你的 ASM + trace 翻譯成中文白話講解;沒裝 anthropic / 沒 API key 時自動降級為純規則式離線解說 |
| 🌐 **Web 鏡像** | `gpu-simulator --serve-web 8765` 一鍵啟動 stdlib http.server,瀏覽器看 GPU 即時狀態(內嵌 JS 每 500ms 拉一次 snapshot) |
| 🧠 **進階 GPU 概念** | warp divergence + memory coalescing 視覺化 + 4 種 builtin 預設情境(完美 SIMD / 奇偶分流 / 4 路發散 / 最壞情況),教學性十足 |

</details>

<details>
<summary><b>🎓 v0.10 升級:UX polish 六連發 + CPU 狀態時間熱圖</b></summary>

| 功能 | 說明 |
| ---- | ---- |
| 🌡️ **CPU 狀態熱圖** | 新分頁 `🌡️ 狀態熱圖`:跑一支 Tiny8 ASM,即時渲染三層 matplotlib 熱圖 — 上層 SREG 8 旗標位、中層 R0–R31、下層記憶體 0x60–0x7f,時間軸 slider 拖到任一 step 看精確的 PC / SP / 指令 / 暫存器值。直接對應大學「微處理器原理」課程裡的 state-trace 作業 |
| 💻 **真實硬體儀表板** | 新分頁 `💻 真實硬體`:用 psutil 顯示自己機器當下 N 顆邏輯 CPU 核心(每顆變色 bar)+ CPU 頻率 + 處理程序數;NVIDIA 用戶看到 GPU 利用率 / 記憶體 / 溫度 / 功耗。`gpu-simulator --monitor` 直接開到這分頁 |
| 🍞 **Toast 通知** | 不再用 QMessageBox 打斷你 — 4 種等級的 toast 從右下角滑入,3 秒後自動淡出 |
| ⌨️ **Command Palette** | `Ctrl+Shift+P` 開命令面板,輸入幾個字就 fuzzy 搜尋:電影模式 / TTS / 心情日記 / 寵物改名 / 煙火 / 快捷鍵 |
| 📊 **底部狀態列** | 永遠顯示版本、目前模式、累計 kernel 數、即時利用率、FPS — 用 monospace 字體像 IDE |
| 📅 **GPU 心情日記** | `Ctrl+M` 打開,GitHub-contributions 風格的月曆熱圖 — 每天的平均負載自動入帳,hover 看 emoji + 評語 |
| 🥚 **彩蛋系統** | Konami 上上下下左右左右BA 觸發超 mega 煙火;輸入 `matrix` 切 Matrix 主題、`dragon` 寵物直接進化到龍、`boom` 放煙火、`rainbow` 彩虹爆發 |
| 🐱 **寵物命名 + 閒置動畫** | `Ctrl+Shift+E` 幫寵物取名;沒人理他時每 6 秒會偷偷眨眼一下,讓桌面看起來有靈魂 |

</details>

<details>
<summary><b>✨ v0.9 升級:眼前一亮的視覺特效</b></summary>

| 特效 | 說明 |
| ---- | ---- |
| ✨ **粒子特效** | 每次 KLAUNCH 從 CPU 噴一道橘色粒子飛到 GPU 區域;kernel 完成時冒綠色煙火;KWAIT 解除時藍色水波紋 |
| 🥚→🐲 **寵物五階進化** | 解鎖的成就數會推動寵物進化:🥚 蛋 → 🐣 雛鳥 → 🐤 小鳥 → 🦅 老鷹 → 🐲 龍。每次進化跳一下 wiggle 動畫 |
| 🟢 **Matrix Code Rain** | GPU 利用率 > 70% 時背景自動下「綠色字元雨」(Tiny8 助記符);< 40% 時自動收起。致敬 The Matrix |
| 🎬 **電影模式** | 工具列點「🎬 電影模式」或啟動加 `--cinema` flag,自動跑 60 秒劇本式 showcase:切 8 個分頁、跑 ASM、放煙火、字幕配中文。**直接錄下來就是展示影片**,後製成本接近 0 |
| 🗣️ **TTS 中文旁白** | 點「🗣️ TTS」開啟後,寵物說的話、成就解鎖、電影字幕都會被念出來(用 pyttsx3 背景 thread,不會卡 GUI) |

</details>

<details>
<summary><b>🎬 v0.7 升級:CPU↔GPU 內部交互運作 + Tiny8 範例延伸</b></summary>

| 功能 | 說明 |
| ---- | ---- |
| 🎬 **Cycle Cinema 同步劇場** | 新分頁:**頂部** Tiny8 CPU 完整狀態(暫存器網格 + 源碼面板,正在執行的那行高亮 Tiny8 風格)、**中間** 中文 flow label(`🚀 KLAUNCH:CPU 把 kernel id=0 (vector_add) 推給 GPU`)、**底部** 8 顆 SM × 4 warps × 5 階 pipeline 動畫;**底列** VCR 控制(⏮ ◀ ▶ ⏭ + 滑桿 + 自動播放),拖前後可以時光旅行 |
| 📦 **VRAM 區塊圖** | Live 分頁取代純 bar,每顆 kernel 的 VRAM 佔用畫成有名字的方塊,按 owner 名雜湊取色,讓不同 kernel 一眼可分 |
| ⚙ **Warp Pipeline 動畫** | Live 分頁,每 warp 5 個 F/D/E/M/W 小方塊,跟著 stage 移動發光 |
| 📜 **5 支 Tiny8 範例的 GPU 進階版** | `full_gcd_gpu` / `full_count_bits_gpu` / `full_factorial_gpu` / `full_histogram_gpu` / `full_matrix_diagonal_gpu`,全用 Tiny8 完整 ISA(MUL / LSL / RJMP / BRCS / ANDI 等)+ GPU bridge,每個都對應一個 Tiny8 經典題目 |

</details>

<details>
<summary><b>🎓 v0.6 升級:Tiny8 教學等級體驗</b></summary>

| 功能 | 說明 |
| ---- | ---- |
| 📖 **中文指令導讀** | Trace 分頁右側多一條側欄,即時把每行指令翻成「這一行做了什麼」(`OUT 0x40, R16` → `把 R16 當 kernel id 提交給 GPU(KLAUNCH 觸發!)`) |
| 🎨 **行色碼 + ← badge** | KLAUNCH 橘 / KSTAT 淺綠 / KWAIT 藍 / stall 灰 / HALT 紅 / 分支黃 / 記憶體青;每行最後一欄寫中文事件標記(像「← 提交『向量加法』」) |
| 🔁 **時序圖分頁** | UML 風 CPU/GPU 兩條 lane,KLAUNCH 橘色實線往下、kernel 完成綠色虛線往上;一眼看清誰先誰後 |
| 🗺️ **記憶體地圖分頁** | 256 byte 整片畫出來,標示 0x40 / 0x41 / 0xFF 是 GPU 控制暫存器,寫入會閃黃高亮 |
| ⏪ **時光旅行** | 點 Trace 表的任一列 → Debug / 記憶體地圖 / 時序圖 同步顯示那個 cycle 的暫存器、記憶體與 GPU 狀態 |
| 🎓 **5 課中文教學** | 工具列 `🎓 教學課程` 鈕打開雙欄式對話:認識 SM → KLAUNCH 入門 → KWAIT 為何存在 → 迴圈批次 → 完整 Tiny8 + MUL。每課可一鍵載入或執行 |

</details>

<details>
<summary><b>🧬 v0.5 升級:整合「真正的 Tiny8 CPU」</b></summary>

把上游 Tiny8 專案完整源碼 vendor 進來,塞在 [src/gpu_simulator/tiny8_full/](src/gpu_simulator/tiny8_full/)
(MIT 授權,LICENSE 一併帶進來)。透過 [`full_bridge.py`](src/gpu_simulator/full_bridge.py)
把 Tiny8 CPU 的 60+ 指令完整 ISA 跟虛擬 GPU 串接:

| 機制 | 說明 |
| ---- | ---- |
| **Vendor 而非 pip 依賴** | Python 3.14 wheel 還沒出時也能用,且日後想 patch Tiny8 隨時改 |
| **不修改 Tiny8 一行原始碼** | `FullTiny8CPU` 是子類別,override `write_ram` / `read_ram` 在 0x40 / 0x41 / 0xFF 三個位址掛鉤;Tiny8 ISA 完全不用動 |
| **三個 GPU port** | `OUT 0x40, Rr` = KLAUNCH;`OUT 0x41, Rr` = HINT;`OUT 0xFF, Rr` = KWAIT;`IN Rd, 0x40` = 讀剩餘 kernel 數 |
| **同框並列視圖** | `Tiny8FullView` 把 CPU 跟 GPU 畫在同一個 widget,中間用箭頭表示 kernel 流動 |

兩支整合範例:

- [examples/full_fibonacci.asm](examples/full_fibonacci.asm) — 算 F(10) = 55 後丟給 GPU 做 hash kernel
- [examples/full_bubble_sort.asm](examples/full_bubble_sort.asm) — 用 RJMP / BRCS 排序 8 byte 後提交兩種 kernel

</details>

<details>
<summary><b>🎯 v0.4 升級:給非技術使用者的友善體驗</b></summary>

| 功能 | 說明 |
| ---- | ---- |
| 🌐 全面繁中化 | 7 個分頁、所有按鈕、tooltip、event log、heatmap 軸標題、kernel 名(向量加法 / 紋理載入 …)全改中文 |
| 📚 範例卡片庫 | Input 分頁變 Steam 風卡片,8 支範例每支有名稱、中文說明、難度星星;一鍵 `▶ 執行` 直接跑 |
| ✨ 首次啟動歡迎對話 | 5 步驟導覽,記在 `~/.gpu_simulator/welcomed`,可勾「下次不顯示」 |
| 🐹 GPU 寵物表情 | widget 頂部住一隻會看利用率變表情的小寵物:`😴 → 🤔 → 💪 → 😅 → 🔥`,搭配中文小語 |
| 🏆 成就系統 | 10 個徽章(第一次提交、KWAIT、滿載、馬拉松…),SQLite 持久化,點 `🏆 獎盃室` 鈕看進度 |
| 🧠 考考你小測驗 | 跑完 ASM 後彈 5 題選擇題,3 題靜態 + 動態(問你「最後 R0 是多少?」),滿分解鎖成就 |
| 🔴 內建 GIF 錄影 | 一鍵把 widget 螢幕錄成動圖,儲存到 `~/.gpu_simulator/recordings/`,直接拿去交家庭錄影 |
| 🔊 音效回饋 | kernel 完成叮咚、HALT 嗶、成就解鎖播放音(Windows 用 winsound,跨平台靜音降級) |
| 👴 給爸媽看模式 | `gpu-simulator --easy` 啟動,只留 Live + 教學秀兩個分頁,自動循環播 5 支範例,適合家庭錄影 |

</details>
