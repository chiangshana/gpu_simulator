# Quickstart · 5 分鐘上手 gpu_simulator

> 給期末作業審查者 / 第一次用的同學:一頁看完怎麼跑、怎麼用、亮點在哪。
> 完整提案見 [PROJECT_BRIEF.md](PROJECT_BRIEF.md);完整功能清單見 [README.md](README.md)。

## 30 秒看懂這個專題在幹嘛

**互動式 CPU↔GPU 視覺化教學模擬器 + 個人電腦硬體儀表板。** 三大支柱:

1. **模擬層** — 寫 Tiny8 ASM,看 cycle-by-cycle 暫存器/記憶體/SREG 熱圖、8 顆 SM × 4 warps 平行跑
2. **教學體驗** — 中文 5 課、AI 解釋、自動 Markdown 報告、寵物進化鼓勵長期使用
3. **真實硬體** — 同一個視窗看自己機器當下 N 顆 CPU 核心 + NVIDIA GPU 即時負載

## 安裝(60 秒)

```bash
git clone <repo>
cd gpu_simulator
python -m venv .venv
.\.venv\Scripts\activate                      # PowerShell
pip install -e .                              # 主套件
pip install -e .[realgpu]                     # 想看真實 NVIDIA GPU 加這個
```

> 要求:Python 3.10+,Windows / macOS / Linux 皆可。

## 啟動(5 種模式)

| 指令 | 用途 |
| ---- | ---- |
| `gpu-simulator` | 一般啟動,16 個分頁全開 |
| `gpu-simulator --monitor` | 直接跳到 **💻 真實硬體** 分頁,當純硬體儀表板用 |
| `gpu-simulator --cinema` | 啟動後跑 60 秒劇本式 showcase(適合錄展示影片) |
| `gpu-simulator --easy` | 給爸媽看模式:簡化 UI、自動循環播範例 |
| `gpu-simulator --serve-web 8765` | 同時啟動 Web 鏡像,瀏覽器 `localhost:8765` 看 |

## 四個必看的分頁

### ⓪ 🪞 對照鏡 — 第一分頁,30 秒看完專題論述

1. 打開 widget 預設就是這頁
2. 左邊 8 條 bar = 模擬 GPU 的 8 顆 SM 即時利用率
3. 右邊 N 條 bar = 你電腦真實的 N 顆邏輯 CPU 核心即時利用率
4. 下方一行 = NVIDIA GPU(有的話)
5. **按 ▶️ 觸發模擬工作負載** — 左邊瞬間飆高,右邊完全不動
6. 「差距分數」用 0..100 顯示兩邊負載差多少,讓論述變成可量化的數字

### ① 🌡️ 狀態熱圖 — 教學核心(第 2 個分頁)

1. 左半邊是 ASM 編輯器,改成你想跑的程式(支援 60+ Tiny8 ISA)
2. 設 `max steps`(預設 200),按 **▶️ Run & 渲染**
3. 右半邊三層 matplotlib 熱圖出現:
   - 上層:SREG 8 個旗標位 I T H S V N Z C
   - 中層:R0–R31 全 32 個暫存器(顏色 = 0..255 的值)
   - 下層:記憶體 0x60–0x7F(顏色 = 該位址的 byte)
4. 拖時間軸 slider 看任一 cycle 的精確 PC / SP / 指令 / SREG / R0–R7

### ② 💻 真實硬體 — 第三支柱(第 3 個分頁)

1. 切過去,每秒自動更新
2. 上方一行:`你的邏輯核心數(實體 N 顆) · 頻率 · 整體利用率 · 處理程序總數`
3. 下方 N 條 bar — 每顆邏輯核心一條,從綠 → 黃 → 橘 → 紅變色
4. 右下 GPU 區塊(NVIDIA 用戶):名稱 / backend / 利用率 / 記憶體 used/total / 溫度 / 功耗

### ③ 🎬 Cycle Cinema — CPU 跟 GPU 同框

左邊 Tiny8 CPU 完整狀態 + 當前 ASM 高亮;右邊 8 顆 SM × 4 warps × 5 階 pipeline 動畫;
中間中文 flow label 即時導讀。底部 VCR 控制(⏮ ◀ ▶ ⏭ + 滑桿 + 自動播放),
**拖動就能時光旅行**。

## 鍵盤快捷鍵速查

| 組合 | 動作 |
| ---- | ---- |
| `Ctrl+Shift+P` | 開命令面板(fuzzy 搜尋功能) |
| `Ctrl+/` 或 `F1` | 顯示快捷鍵清單 |
| `Ctrl+M` | 開心情日記 |
| `Ctrl+Shift+E` | 幫寵物改名 |
| `Ctrl+Shift+T` | 切 TTS 旁白 |

## 課程作業需求 — 對照表(精簡版)

| 要求 | 達成方式 | 證據 |
| ---- | ---- | ---- |
| 100% Python | 48 個自有 `.py`,16,985 行(不含 vendored Tiny8) | `Get-ChildItem src -Recurse -Include *.py \| Measure-Object` |
| 善用 class | **172 個 class**、**80 個 @dataclass**、**11 層自訂例外** | `src/gpu_simulator/exceptions.py`、`src/gpu_simulator/core.py` |
| 進階資料結構 | dataclass / `collections.deque` / `Enum` / 2D matrix | `cpu_heatmap.py:50` `CPUStateHistory`、`bridge.py` `deque` ring buffer |
| 檔案 I/O | JSON / CSV / Markdown / PNG / ASM / GIF | `config.py`、`exporter.py`、`lab_report.py`、`recorder.py` |
| 例外處理 | `GPUVizError` 階層 + `try`/`except` 23 個檔案 | `src/gpu_simulator/exceptions.py` |
| GUI | PySide6,主視窗 2,400 行,30+ 自訂 QWidget | `widget.py`、`visualizer.py` |
| 資料庫 | **5 張 SQLite 表** | `persistence.py`(sessions)、`achievements.py`(unlocks)、`challenges.py`(leaderboard)、`mood_calendar.py`(mood)、`config.py`(kv) |
| PEP 8 | ruff 設定 + **0 issues**(src/ 跟 tests/ 全綠) | `pyproject.toml` `[tool.ruff]`、`python -m ruff check src tests` |

## 驗證(30 秒給審查者跑)

```powershell
# 1. lint(全 repo 0 警告)
python -m ruff check src tests

# 2. tests(299 cases 全綠)
python -m pytest -q

# 3. 啟動 GUI 看實物
gpu-simulator

# 4. 想直接看硬體儀表板
gpu-simulator --monitor

# 5. 想錄展示影片
gpu-simulator --cinema
```

## 程式規模

| 指標 | 數值 |
| ---- | ---- |
| 自有 Python 檔 | 48 |
| 自有程式碼行數 | **16,985** |
| Class 定義 | **172** |
| `@dataclass` | 80 |
| 自訂例外類別 | 11 |
| QWidget 子類 | 30+ |
| 測試案例(全綠) | **299** |
| Ruff lint issues | **0** |

## 還想再看?

- 完整提案書(動機、用例、架構、需求對照):[PROJECT_BRIEF.md](PROJECT_BRIEF.md)
- 完整功能清單與各版本歷程:[README.md](README.md)
- 各輪需求變更紀錄:[CHANGELOG_REQUIREMENTS.md](CHANGELOG_REQUIREMENTS.md)
