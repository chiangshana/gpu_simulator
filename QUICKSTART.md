# Quickstart · 5 分鐘上手 gpu_simulator

給期末作業審查者與第一次使用的同學:一頁看完安裝、啟動、核心功能與驗證方式。
完整提案請參考 [PROJECT_BRIEF.md](PROJECT_BRIEF.md);完整功能清單見 [README.md](README.md)。

## 專案定位

互動式 CPU↔GPU 視覺化教學模擬器,同時整合本機硬體儀表板。三個面向:

1. 模擬層 — 執行 Tiny8 組合語言,逐 cycle 觀察 32 個通用暫存器(R0–R31)、SREG
   狀態旗標、記憶體 0x60–0x7F 區段的變化;8 個 Streaming Multiprocessor 與每
   個 SM 內 4 條 warp 的平行執行視覺化。
2. 教學體驗 — 5 課中文課堂、互動式測驗、Claude API 自動產生 trace 解釋、
   Markdown 實驗報告自動產出。
3. 真實硬體儀表板 — 同一視窗內顯示本機各顆 CPU 邏輯核心的即時使用率,
   以及 NVIDIA 顯卡的讀值(如有)。

## 安裝

需要 Python 3.10 以上(建議 3.12)。

```bash
git clone https://github.com/chiangshana/gpu_simulator.git
cd gpu_simulator
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
pip install -e ".[realgpu]"   # 可選:啟用 NVIDIA 顯卡讀值
```

不想安裝 Python 的話,從 repo 根目錄下載 `一鍵安裝包.exe`(75 MB)直接執行。

## 啟動模式

| 命令 | 用途 |
| --- | --- |
| `gpu-simulator` | 一般啟動,14 個分頁全開 |
| `gpu-simulator --tutorial` | 開機進入 10 分鐘詳細導覽(零程式基礎觀眾用) |
| `gpu-simulator --cinema` | 60 秒自動展示劇本,適合錄製 demo 影片 |
| `gpu-simulator --monitor` | 開機跳到「💻 硬體」分頁,當作本機硬體儀表板使用 |
| `gpu-simulator --easy` | 給長輩看的精簡介面,自動循環播範例 |
| `gpu-simulator --lite` | 強制輕量模式,關閉特效給低階機器用 |
| `gpu-simulator --serve-web 8765` | 同時啟動 Web 鏡像,瀏覽器存取 `localhost:8765` |

## 四個必看的分頁

### 第 1 分頁 · 🪞 對照

打開應用程式預設停留在此頁,展現專題的核心論述。

- 左側:模擬 GPU 的 8 個運算單元(SM)即時使用率
- 右側:本機各邏輯 CPU 核心即時使用率(由 psutil 取樣)
- 下方:NVIDIA 顯卡讀值(若有)
- 中央按鈕「派工作給模擬 GPU」:按下後左側 SM 使用率瞬間升高,右側真實 CPU
  幾乎不動。此對比清楚顯示「模擬端」與「真實端」是獨立的兩個世界。
- 差距分數(0–100)以數值方式呈現兩側負載落差。

### 第 2 分頁 · 🌡️ 變化(狀態變化圖)

執行一段 Tiny8 ASM,以三層 matplotlib heatmap 視覺化 CPU 內部狀態演化。

操作流程:

1. 左半部為 ASM 編輯器,可使用內建範例或自行編寫(支援 60 餘條 Tiny8 指令)
2. 設定 `最多跑幾拍`(預設 200),按「▶️ 開跑並畫圖」
3. 右半部呈現三層熱圖:
   - 上層:SREG 8 個狀態旗標(I T H S V N Z C)
   - 中層:R0–R31 共 32 個通用暫存器,顏色對應 0–255 的值
   - 下層:記憶體 0x60–0x7F,顏色對應該位址的 byte 值
4. 拖動時間軸拉桿可定位到特定 cycle,下方顯示該 cycle 的 PC、SP、執行指令、
   SREG 與前 8 個暫存器的精確值。

### 第 3 分頁 · 💻 硬體

每秒自動更新本機硬體狀態。

- 上方一行摘要:邏輯核心數(實體 N 顆)、頻率、整體使用率、處理程序總數
- 每顆邏輯核心一條 bar,使用率顏色從綠經黃、橘至紅
- NVIDIA 用戶會看到顯卡名稱、後端(pynvml 或 GPUtil)、使用率、記憶體
  used/total、溫度、功耗

### 第 5 分頁 · 🎬 Cinema(慢動作劇場)

CPU 與 GPU 並列的逐 cycle 慢動作播放。左半部顯示 Tiny8 CPU 的暫存器狀態與
當前執行的源碼行,右半部呈現 8 個 SM × 4 warps × 5 階 pipeline 的動畫。底部
VCR 風格控制(⏮ ◀ ▶ ⏭ + 時間軸拉桿 + 自動播放)允許前後檢視任一 cycle。

## 鍵盤快捷鍵

| 組合鍵 | 功能 |
| --- | --- |
| `Ctrl+Shift+P` | 命令面板(模糊搜尋所有功能) |
| `Ctrl+/` 或 `F1` | 顯示快捷鍵清單 |
| `Ctrl+M` | 開啟心情日記月曆熱圖 |
| `Ctrl+Shift+E` | 重新命名桌面寵物 |
| `Ctrl+Shift+T` | 切換 TTS 中文旁白 |

## 課程作業需求對照

| 課程要求 | 達成方式 | 證據檔案 |
| --- | --- | --- |
| 100% Python | 50 個自有 `.py`、17,355 行(不含 vendored Tiny8) | `src/gpu_simulator/` |
| 善用 class | 168 個 class、80 個 `@dataclass`、11 個自訂例外 | `core.py`、`exceptions.py` |
| 進階資料結構 | dataclass、`collections.deque`、`Enum`、二維 list 矩陣 | `cpu_heatmap.py`、`bridge.py` |
| 檔案 I/O | JSON、CSV、Markdown、PNG、ASM、GIF | `config.py`、`exporter.py`、`lab_report.py`、`recorder.py` |
| 例外處理 | `GPUVizError` 階層 + `try`/`except` 涵蓋 23 個檔案 | `exceptions.py` |
| 圖形介面 | PySide6,主視窗 2,400 餘行,30 餘個自訂 QWidget | `widget.py`、`visualizer.py` |
| 資料庫 | 5 張 SQLite 表 | `persistence.py`、`achievements.py`、`challenges.py`、`mood_calendar.py`、`config.py` |
| PEP 8 | ruff lint 設定 + 0 警告(src/ 與 tests/ 均全綠) | `pyproject.toml`、`python -m ruff check src tests` |

## 驗證流程(30 秒)

```powershell
# 1. lint(全 repo 應為 0 警告)
python -m ruff check src tests

# 2. tests(315 cases 全綠)
python -m pytest -q

# 3. 啟動 GUI
gpu-simulator

# 4. 直接進入硬體儀表板
gpu-simulator --monitor

# 5. 錄製 60 秒展示影片
gpu-simulator --cinema
```

## 程式規模摘要

| 指標 | 數值 |
| --- | --- |
| 自有 Python 檔 | 50 |
| 自有程式碼行數 | 17,355 |
| Class 總數 | 168 |
| `@dataclass` 使用次數 | 80 |
| 自訂例外類別 | 11 |
| QWidget 子類 | 30+ |
| 自動化測試案例 | 315(全綠) |
| Ruff lint 警告 | 0 |

## 延伸閱讀

- 完整提案書(動機、使用情境、架構、需求對照):[PROJECT_BRIEF.md](PROJECT_BRIEF.md)
- 完整功能清單與各版本歷程:[README.md](README.md)
- 各輪需求變更紀錄:[CHANGELOG_REQUIREMENTS.md](CHANGELOG_REQUIREMENTS.md)
