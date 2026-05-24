# 截圖 / 錄影指南 · 期末 demo 影片 + 報告

> 給自己用的 checklist:demo 影片(6/1)跟期末報告(6/4)分別需要哪些畫面、
> 在哪個分頁怎麼截。Claude 無法替你按截圖鍵,但這份清單會告訴你**該按時什麼**。

---

## 🎬 Demo 影片(6/1 截止 · 60 秒 · 用 `gpu-simulator --cinema` 自動跑)

最簡單的錄法是**直接用內建電影模式錄**,完全不用手動切分頁:

```powershell
# 視窗稍微拉大一點(360x720 → 720x900 看起來比較舒服)
gpu-simulator --width 720 --height 900 --cinema
```

第十四輪改寫過的 60 秒劇本會自動帶你跑完下面 7 個關鍵 shot,
你只要開錄影軟體(OBS / Snipping Tool / Win+G)按下「Run」就好:

| 時間軸 | 畫面 | 為什麼這 shot 重要 |
| ---- | ---- | ---- |
| 0–3s | 🎬 開場字幕「30 秒看完專題核心論述」 | 設定觀眾預期 |
| 3–6s | 🪞 對照鏡靜止狀態(左 8 SM,右 24 核) | 第一眼看到專題論述 |
| 6–9s | 字幕「左邊模擬 / 右邊真實」 | 解釋兩邊代表什麼 |
| 9–13s | **🪞 對照鏡:左邊跳起來、右邊不動** ⭐ 關鍵畫面 | 視覺證明專題論述 |
| 13–18s | 字幕「模擬世界學原理,真實世界看效果」 | 把畫面變成可以引用的句子 |
| 18–28s | 🌡️ 狀態熱圖 — SREG / R0–R31 / mem 三層熱圖 | 支柱 ① 教學核心 |
| 28–38s | 💻 真實硬體 — N 條 CPU bar 變色 | 支柱 ③ 真實硬體 |
| 38–55s | 🎬 / 🧬 / 🧠 三個分頁速覽 | 帶過其他亮點 |
| 55–60s | 回到 🪞 對照鏡 + 煙火 + 收尾字幕 | 收尾 |

### 錄製建議

- **解析度**:1280×800 或更大,讓字幕看得清楚
- **格式**:MP4(H.264),60s 約 5–10 MB
- **音軌**:不需要 — 字幕已經把訊息傳完了。要的話可以後製加旁白
- **錄影軟體**:Windows 內建 Xbox Game Bar(Win+G)最快,或裝 OBS

### 開錄前 checklist

```text
□ 視窗大小設好(--width 720 --height 900)
□ 關掉其他會閃通知的 app(Slack / Teams / 信箱)
□ 桌布暫時換純色,避免後面亂
□ 開錄影軟體,設熱鍵
□ 跑 `gpu-simulator --cinema`,看 widget 出現後按錄影
□ 60 秒後等劇本自動 DONE,停止錄影
```

---

## 📷 期末報告(6/4 截止 · 靜態截圖)

報告需要的**單張**截圖,每張對應 PROJECT_BRIEF.md 裡的一段論述。
全部約 8 張就夠。命名建議 `01_mirror_idle.png`、`02_mirror_after_trigger.png` …。

### 必拍 8 張

| # | 檔名 | 分頁 / 狀態 | 用在報告哪段 |
| ---- | ---- | ---- | ---- |
| 1 | `01_mirror_idle.png` | 🪞 對照鏡 — 靜止 | 「核心論述」開頭,展示左右並排架構 |
| 2 | `02_mirror_after_trigger.png` | 🪞 對照鏡 — 按完「觸發模擬工作負載」3 秒後 | 證明「左跳右不動」,差距分數飆高 |
| 3 | `03_state_heatmap.png` | 🌡️ 狀態熱圖 — 跑完預設 ASM 後 | 支柱 ① 教學核心的具象化 |
| 4 | `04_state_heatmap_slider.png` | 🌡️ 狀態熱圖 — slider 拖到中間 | 展示「時光旅行」功能 |
| 5 | `05_real_hardware.png` | 💻 真實硬體 — N 條 CPU bar 顯著差異 | 支柱 ③ 真實硬體 |
| 6 | `06_cycle_cinema.png` | 🎬 Cycle Cinema — CPU + GPU 同框 | 教學體驗豐富度 |
| 7 | `07_tiny8_full.png` | 🧬 Tiny8 完整版 — 寫 MUL/RJMP/CALL 範例 | 60+ 指令 ISA 證明 |
| 8 | `08_command_palette.png` | Ctrl+Shift+P 命令面板開啟中 | UX 細節 |

### 加分 4 張(有空再拍)

| # | 檔名 | 場景 |
| ---- | ---- | ---- |
| 9 | `09_pet_evolution.png` | 寵物進化到 🐲 龍(解滿 9 個成就) |
| 10 | `10_mood_calendar.png` | Ctrl+M 開心情日記,看連續幾天累積負載 |
| 11 | `11_easter_egg_konami.png` | 打完 Konami code 後的煙火爆發 |
| 12 | `12_lab_report.png` | 自動產的 Markdown 實驗報告 |

### 截圖工具

- **單一視窗**:Win+Shift+S(框選),貼到 PowerPoint / Word
- **整個視窗**:Alt+PrtScn,直接拍當前活動視窗
- **整個螢幕**:Win+PrtScn,自動存到 `Pictures\Screenshots`

---

## 🎙️ 家庭錄影(6/18 截止 · 「給爸媽看」模式)

這個 deadline 最寬,劇本也最特別。用:

```powershell
gpu-simulator --easy
```

`--easy` 模式只開 2 個分頁(Live + Demo),自動循環播 5 支範例。
配旁白「這個叫 GPU,它在做這些事…」會比 60 秒 cinema 模式更適合家人。

### 給爸媽看的開場 30 秒 talking points

1. 「這是我這學期寫的程式,模擬電腦顯卡裡面發生的事」
2. 「左上角這個方格,每個小方塊是顯卡的一個運算單元」
3. 「我點滑鼠的時候,你看,綠色的方塊就會亮起來,代表顯卡開始工作」
4. 「右下角那隻寵物會隨著我用得越多,進化變強」
5. 「整個程式有 17,000 行 Python,300 個測試,全部我自己寫的」

---

## 📁 檔案組織建議

```text
gpu_simulator/
└── docs/
    └── screenshots/                  # 新建這個資料夾(.gitignore 可選)
        ├── 01_mirror_idle.png
        ├── 02_mirror_after_trigger.png
        ├── 03_state_heatmap.png
        ├── ...
        ├── demo_60s.mp4              # 6/1 demo 影片
        └── family_video.mp4          # 6/18 家庭錄影
```

把 demo 影片放上 YouTube 列為「不公開」,把連結貼進 `期末報告計畫書.md`,
就完成所有交付。
