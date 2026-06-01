"""繁體中文字串集中管理(internationalization)。

風格 B:**白話 + 第一次出現括號標技術詞**。
受眾是沒學過程式的學生,所以用日常比喻當主詞、把專業詞放在括號裡讓他們順便認識。

把所有對使用者顯示的字串集中在這個模組,有兩個好處:

1. UI 模組的程式碼不會混雜中文字串,Python source 的可讀性較高。
2. 想對英文使用者輸出時,只要替換 ``STRINGS`` 字典即可。

使用方式::

    from gpu_simulator.i18n import t
    label.setText(t("tab.live"))

未在字典中找到的 key 會 fallback 為 key 本身,方便在開發時抓漏。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 主要字串字典 — 用 dot.path key 把同類型字串分組
# ---------------------------------------------------------------------------
STRINGS: dict[str, str] = {
    # ----------- 視窗、總體 -----------
    "app.title": "GPU 模擬器 — CPU↔GPU 視覺化教學工具",
    "app.subtitle": "互動式呈現 CPU 與 GPU 的執行狀態與互動",
    "mode.live": "● 即時模式",
    "mode.replay": "● 重看舊紀錄 #{session_id}",
    "mode.asm": "● ASM 執行模式",
    "mode.easy": "● 精簡介面模式",

    # ----------- 分頁名稱(精簡 emoji + 1-3 字)-----------
    "tab.live": "⚡ 即時",
    "tab.analytics": "📈 趨勢",
    "tab.history": "📚 歷史",
    "tab.trace": "📜 逐拍",
    "tab.debug": "🐞 內部",
    "tab.heatmap": "🌡️ 演化",
    "tab.input": "⌨️ 寫程式",
    "tab.demo": "🎬 教學秀",

    # ----------- 各分頁標題提示 -----------
    "section.live.title": "GPU 即時狀態",
    "section.live.tip": (
        "滑鼠 / 鍵盤事件會觸發對應的 GPU kernel。觀察下方 8 個 Streaming "
        "Multiprocessor(SM)與 VRAM 的反應。"
    ),
    "section.sm_grid": "Streaming Multiprocessor(SM,共 8 個)使用率",
    "section.vram": "VRAM 使用量",
    "section.pipeline": "5 階 pipeline 各 warp 所處階段",
    "section.event_log": "事件紀錄(event log)",
    "section.analytics.title": "GPU 使用率與 VRAM 用量隨時間變化",
    "section.analytics.tip": (
        "橘線:整體 GPU 使用率(百分比);藍線:VRAM 使用量(MiB)"
    ),
    "section.history.title": "歷史執行紀錄(可重播 / 匯出)",
    "section.history.tip": (
        "選擇歷史紀錄可重播,或匯出為 CSV / Markdown / PNG 格式"
    ),
    "section.trace.title": "逐 cycle 執行紀錄",
    "section.trace.tip": "每一橫列代表一個 cycle,有變動的欄位高亮顯示",
    "section.debug.title": "CPU 內部狀態觀察",
    "section.debug.tip": (
        "monospace 字型呈現,變動格高亮為黃色"
    ),
    "section.heatmap.title": "時間 × CPU 內部狀態 熱圖",
    "section.heatmap.tip": (
        "由上至下:SREG 狀態旗標(8 bit)、R0–R31 通用暫存器、"
        "記憶體 0x60–0x7F。顏色強度對應數值大小。"
    ),
    "section.input.title": "Tiny8 組合語言(ASM)編輯區",
    "section.input.tip": "可從上方選擇內建範例,或自行撰寫 Tiny8 子集組合語言",
    "section.real_gpu": "本機真實顯卡讀值(僅 NVIDIA 顯卡)",

    # ----------- 按鈕 -----------
    "btn.run": "▶ 執行",
    "btn.step": "⏭ 走一拍",
    "btn.reset": "⟲ 重置",
    "btn.load_example": "📚 載入範例",
    "btn.refresh": "重新整理",
    "btn.replay": "重看",
    "btn.export_csv": "匯出表格",
    "btn.export_md": "匯出文字報告",
    "btn.export_png": "匯出圖片",
    "btn.record_start": "🔴 開始錄影",
    "btn.record_stop": "⏹ 停止錄影",
    "btn.trophy_room": "🏆 獎盃室",
    "btn.start_quiz": "🧠 考考你",
    "btn.start_tour": "✨ 新手導覽",
    "btn.close": "關閉",

    # ----------- 按鈕 tooltip -----------
    "tooltip.run": (
        "組譯並執行下方 ASM,「逐拍」「內部」「演化」三個分頁會即時同步更新"
    ),
    "tooltip.step": "單步執行一個 cycle,逐一觀察指令效果",
    "tooltip.reset": "停止執行並清空紀錄,回到即時模式",
    "tooltip.load_example": "載入內建範例程式至下方編輯器",
    "tooltip.record_start": "將視窗畫面錄製為 GIF,輸出至 ~/.gpu_simulator/recordings/",
    "tooltip.record_stop": "停止錄影並儲存 GIF",
    "tooltip.trophy_room": "查看已解鎖的成就徽章",
    "tooltip.start_quiz": "5 題選擇題,基於剛執行的 ASM 內容出題",
    "tooltip.start_tour": "重新顯示新手導覽",
    "tooltip.close": "關閉視窗,自動將本次 session 寫入歷史紀錄",

    # ----------- 狀態列訊息 -----------
    "status.ready": "已就緒,按「執行」開始。",
    "status.running": "執行中,共 {count} 行指令(按「重置」可中止)。",
    "status.halted": "已執行 {cycles} 個 cycle 後停止。",
    "status.max_cycles": "達到最大 cycle 數上限({limit}),自動停止。",
    "status.cycle_one": "Cycle {cycle} · {instruction}",
    "status.reset": "已重置,回到即時模式。",
    "status.example_loaded": "已載入範例:{name}",
    "status.recording": "錄影中,已 {seconds} 秒",
    "status.recording_saved": "GIF 已儲存至 {path}",
    "status.kwait_indicator": "等待中 · CPU stall 等待 GPU(KWAIT)",
    "status.running_indicator": "執行中 · CPU 正常推進",
    "status.halted_indicator": "已停止 · CPU 已 HALT",

    # ----------- kernel 中文別名(會在 event log 顯示) -----------
    "kernel.vector_add": "向量加法",
    "kernel.interpolation": "線性插值",
    "kernel.hash": "雜湊運算",
    "kernel.texture_load": "紋理載入",
    "kernel.idle_compression": "閒置壓縮",
    "kernel.app_launch": "App 啟動載入",
    "kernel.page_nav": "頁面跳轉",

    # ----------- 觸發來源中文別名 -----------
    "trigger.mouse_click": "滑鼠點擊",
    "trigger.mouse_move": "滑鼠移動",
    "trigger.keyboard": "鍵盤輸入",
    "trigger.focus_change": "切換 App",
    "trigger.page_nav": "頁面切換",
    "trigger.app_launch": "開啟新 App",
    "trigger.idle": "使用者閒置",
    "trigger.asm": "程式指令",

    # ----------- GPU 寵物表情語(維持較輕鬆的口吻,因為這是寵物 UI) -----------
    "pet.bored": "待機中,GPU 閒置",
    "pet.warming": "開始接到工作",
    "pet.busy": "執行中",
    "pet.sweating": "高負載運轉中",
    "pet.melting": "接近滿載",

    # ----------- 歡迎對話 -----------
    "welcome.title": "歡迎使用 GPU 模擬器",
    "welcome.intro": (
        "本工具是一個桌面 CPU↔GPU 視覺化教學模擬器。\n"
        "滑鼠、鍵盤、開啟 App 等事件會被翻譯成 GPU kernel,即時呈現於各分頁。\n"
        "以下是重點分頁說明:"
    ),
    "welcome.step1": "⚡ 即時 — 滑鼠/鍵盤事件觸發 kernel,觀察 8 個 SM 的反應",
    "welcome.step2": "📈 趨勢 — GPU 使用率與 VRAM 用量隨時間的變化曲線",
    "welcome.step3": "📚 歷史 — 過去 session 的紀錄,可重播或匯出",
    "welcome.step4": "🐞 內部 / 🌡️ 演化 — 觀察 CPU 暫存器與記憶體的內部狀態",
    "welcome.step5": "⌨️ 寫程式 — 撰寫 Tiny8 組合語言(ASM),觀察 CPU 與 GPU 的協同運作",
    "welcome.cta": (
        "按下方按鈕開始。建議先到「寫程式」分頁按「載入範例」執行內建程式。"
    ),
    "welcome.start": "開始",
    "welcome.dont_show": "下次不要再顯示",

    # ----------- 成就 -----------
    "ach.first_run.name": "Hello, GPU!",
    "ach.first_run.desc": "第一次跑了程式",
    "ach.first_kwait.name": "懂得等待",
    "ach.first_kwait.desc": "第一次成功讓 CPU 等 GPU 完成(KWAIT 同步)",
    "ach.first_klaunch.name": "起手第一發",
    "ach.first_klaunch.desc": "第一次派工給 GPU(提交 kernel)",
    "ach.full_load.name": "GPU 滿載",
    "ach.full_load.desc": "達到 100% GPU 利用率(所有平行小組 warp 同時忙碌)",
    "ach.memory_master.name": "記憶體達人",
    "ach.memory_master.desc": "一次執行中寫入記憶體 ≥ 16 個位址",
    "ach.kernel_collector.name": "Kernel 收藏家",
    "ach.kernel_collector.desc": "一次執行中派工給 GPU ≥ 5 個工作(kernel)",
    "ach.long_session.name": "馬拉松選手",
    "ach.long_session.desc": "一次執行跑超過 100 拍(cycle)",
    "ach.idle_master.name": "禪定大師",
    "ach.idle_master.desc": "讓 GPU 進入閒置壓縮模式",
    "ach.quiz_pass.name": "考試達人",
    "ach.quiz_pass.desc": "在「考考你」拿到 100 分",
    "ach.recorder.name": "Youtuber",
    "ach.recorder.desc": "第一次使用內建錄影功能",

    "trophy.title": "🏆 獎盃室",
    "trophy.subtitle": "你已經解鎖 {unlocked} / {total} 個成就",
    "trophy.locked": "(尚未解鎖)",
    "trophy.unlocked_at": "解鎖於 {when}",
    "trophy.popup_title": "🎉 成就解鎖!",
    "trophy.popup_body": "{name}\n{desc}",

    # ----------- 考考你 -----------
    "quiz.title": "考考你 — 看完執行紀錄之後測驗一下",
    "quiz.intro": "下面有 5 道選擇題,看你剛剛跑的程式記了多少。請選出你認為對的答案。",
    "quiz.score": "你答對了 {score} / {total} 題!",
    "quiz.next": "下一題 →",
    "quiz.finish": "看結果",
    "quiz.review_title": "解答解釋",
    "quiz.no_session": "請先到「寫程式」分頁跑一段程式,再來測驗喔!",

    # ----------- 範例庫卡片 -----------
    "preset.hello.name": "Hello GPU",
    "preset.hello.desc": "最基本範例:CPU 派發一個 vector_add kernel 至 GPU,等待完成",
    "preset.hello.stars": "★☆☆☆☆",
    "preset.burst.name": "連發三顆",
    "preset.burst.desc": "連續派發 vector_add、hash、texture_load 三種 kernel 至 GPU",
    "preset.burst.stars": "★★☆☆☆",
    "preset.loop.name": "迴圈派發",
    "preset.loop.desc": "以迴圈連續派發 3 次 interpolation kernel,展示條件跳轉指令",
    "preset.loop.stars": "★★☆☆☆",
    "preset.memory_copy.name": "記憶體拷貝",
    "preset.memory_copy.desc": (
        "將 0x60..0x65 區段複製至 0x70..0x75,最後派發一個 vector_add kernel"
    ),
    "preset.memory_copy.stars": "★★★☆☆",
    "preset.sort_three.name": "三數排序",
    "preset.sort_three.desc": (
        "以比較與條件跳轉指令,將 R16 / R17 / R18 三個暫存器值由小到大排序"
    ),
    "preset.sort_three.stars": "★★★☆☆",
    "preset.find_max.name": "尋找最大值",
    "preset.find_max.desc": "掃描記憶體 0x60..0x67 共 8 個位置,將最大值存入 R0",
    "preset.find_max.stars": "★★★☆☆",
    "preset.counter.name": "倒數計時",
    "preset.counter.desc": "從 9 倒數至 0,每次迭代派發一個 hash kernel",
    "preset.counter.stars": "★★☆☆☆",
    "preset.mixed_burst.name": "混合工作負載",
    "preset.mixed_burst.desc": (
        "依序派發全部 7 種 kernel,熱圖會呈現各 SM 使用率的波動"
    ),
    "preset.mixed_burst.stars": "★★★★☆",

    # ----------- 教學秀 / 給爸媽看 -----------
    "demo.title": "🎬 教學秀(自動播放)",
    "demo.subtitle": "本工具會循環跑下面這幾個範例,每 30 秒換一支。",
    "demo.now_playing": "正在跑:{name}",
    "demo.next_in": "{seconds} 秒後切換到下一支",

    # ----------- 錯誤訊息 -----------
    "err.assemble": "讀程式失敗:{detail}",
    "err.empty_program": "編輯器是空的,請先寫一些指令或載入範例。",
    "err.no_history_session": "目前沒有可重看的紀錄,請先讓小工具跑一陣子。",
    "err.export_failed": "匯出失敗:{detail}",
}


def t(key: str, **kwargs) -> str:
    """Translate a key to its Traditional Chinese string.

    ``kwargs`` are passed to :meth:`str.format` so callers can do::

        t("status.running", count=5)
    """
    template = STRINGS.get(key, key)
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


# Convenience: kernel name → 中文
def kernel_label(internal_name: str) -> str:
    return t(f"kernel.{internal_name}")


def trigger_label(internal_name: str) -> str:
    return t(f"trigger.{internal_name}")
