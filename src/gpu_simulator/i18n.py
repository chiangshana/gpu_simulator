"""繁體中文字串集中管理(internationalization)。

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
    "app.title": "GPU Simulator · 桌面虛擬 GPU 視覺化小工具",
    "app.subtitle": "用 Tiny8 風格教你看懂 CPU 跟 GPU 在做什麼",
    "mode.live": "● 即時模式",
    "mode.replay": "● 重播 #{session_id}",
    "mode.asm": "● ASM 教學模式",
    "mode.easy": "● 給爸媽看模式",

    # ----------- 7 個分頁名稱 -----------
    "tab.live": "即時",
    "tab.analytics": "趨勢圖",
    "tab.history": "歷史",
    "tab.trace": "Cycle 追蹤",
    "tab.debug": "Tiny8 除錯",
    "tab.heatmap": "Tiny8 熱圖",
    "tab.input": "ASM 輸入",
    "tab.demo": "教學秀",

    # ----------- 各分頁標題提示 -----------
    "section.live.title": "即時 GPU 狀態",
    "section.live.tip": "你每動一下滑鼠 / 鍵盤,GPU 就會接到對應的工作。看下面 8 顆 SM 跟 VRAM 的反應吧!",
    "section.sm_grid": "Streaming Multiprocessor 利用率(8 顆 SM)",
    "section.vram": "VRAM 使用量(GPU 記憶體)",
    "section.pipeline": "Pipeline 五階段(每顆 warp 跑到哪一段)",
    "section.event_log": "事件 Log(剛剛發生了什麼)",
    "section.analytics.title": "利用率與 VRAM 隨時間變化",
    "section.analytics.tip": "橘色線=GPU 利用率(%),藍色線=VRAM 使用量(MiB)",
    "section.history.title": "歷史 Session(可重播 / 匯出)",
    "section.history.tip": "選一筆過去的紀錄,可以重播或匯出 CSV / Markdown / PNG",
    "section.trace.title": "逐 Cycle 追蹤(Tiny8 風格表格)",
    "section.trace.tip": "每一橫列都是一個 cycle,變動的格子會被高亮",
    "section.debug.title": "Tiny8 風格除錯器",
    "section.debug.tip": "黑底是為了像 Tiny8 CLI debugger 一樣;格子變黃色就是這 cycle 有變動",
    "section.heatmap.title": "Tiny8 風格時序熱圖",
    "section.heatmap.tip": "從上到下:SREG 旗標 / R0–R31 暫存器 / 記憶體 0x60–0x7F,顏色越亮值越大",
    "section.input.title": "ASM 程式編輯區(輸入即執行)",
    "section.input.tip": "可以從上方挑現成範例,或自己寫 Tiny8 風格的組合語言",
    "section.real_gpu": "實機 GPU(若有 NVIDIA 才會亮)",

    # ----------- 按鈕 -----------
    "btn.run": "▶ 執行",
    "btn.step": "⏭ 單步",
    "btn.reset": "⟲ 重置",
    "btn.load_example": "📚 載入範例",
    "btn.refresh": "重新整理",
    "btn.replay": "重播",
    "btn.export_csv": "匯出 CSV",
    "btn.export_md": "匯出 Markdown",
    "btn.export_png": "匯出 PNG",
    "btn.record_start": "🔴 開始錄影",
    "btn.record_stop": "⏹ 停止錄影",
    "btn.trophy_room": "🏆 獎盃室",
    "btn.start_quiz": "🧠 考考你",
    "btn.start_tour": "✨ 新手導覽",
    "btn.close": "關閉",

    # ----------- 按鈕 tooltip -----------
    "tooltip.run": "組譯下方的 ASM 程式並開始連續執行,Trace / Debug / Heatmap 三個分頁都會即時更新",
    "tooltip.step": "只前進一個 cycle,可以慢慢看每一行指令做了什麼",
    "tooltip.reset": "停下執行、清空 trace,並回到原本的即時模式",
    "tooltip.load_example": "載入內建範例程式到下方編輯器",
    "tooltip.record_start": "把 widget 螢幕錄製成 GIF,輸出到 ~/.gpu_simulator/recordings/",
    "tooltip.record_stop": "停止錄影並儲存 GIF",
    "tooltip.trophy_room": "看你已經解鎖的成就徽章",
    "tooltip.start_quiz": "彈出 5 題選擇題小測驗,測驗你看完 trace 後懂了多少",
    "tooltip.start_tour": "重看一遍新手導覽",
    "tooltip.close": "關閉小工具,並把這次 session 存進歷史",

    # ----------- 狀態列訊息 -----------
    "status.ready": "已就緒,點「執行」開始。",
    "status.running": "執行中,共 {count} 行指令…按「重置」可中止。",
    "status.halted": "已執行 {cycles} 個 cycle 後停止。",
    "status.max_cycles": "達到最大 cycle 數({limit}),已強制停止。",
    "status.cycle_one": "第 {cycle} cycle · {instruction}",
    "status.reset": "已重置,回到即時模式。",
    "status.example_loaded": "已載入範例:{name}",
    "status.recording": "🔴 錄影中… 已 {seconds} 秒",
    "status.recording_saved": "GIF 已儲存到 {path}",
    "status.kwait_indicator": "STALLED · CPU 卡住等 GPU(KWAIT)",
    "status.running_indicator": "RUNNING · CPU 正在跑",
    "status.halted_indicator": "HALTED · CPU 已停止",

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
    "trigger.asm": "ASM 程式",

    # ----------- GPU 寵物表情語 -----------
    "pet.bored": "好閒喔…來點工作給我嘛 😴",
    "pet.warming": "嗯?有事要做了 🤔",
    "pet.busy": "正在認真幹活!💪",
    "pet.sweating": "我快忙不過來了 😅",
    "pet.melting": "我要燒起來啦!🔥",

    # ----------- 歡迎對話 -----------
    "welcome.title": "歡迎使用 GPU Simulator!",
    "welcome.intro": (
        "這是一個會在桌面上跑的虛擬 GPU 模擬器。\n"
        "它會把你的滑鼠、鍵盤、開啟 App 等動作,即時翻譯成 GPU 工作。\n"
        "下面幫你 30 秒看懂 7 個分頁:"
    ),
    "welcome.step1": "🟢 即時 — 動一下滑鼠,看下面 8 顆 SM(GPU 核心)亮起來",
    "welcome.step2": "📈 趨勢圖 — 看利用率隨時間怎麼變動",
    "welcome.step3": "📜 歷史 — 過去的 session 在這裡,可以重播或匯出",
    "welcome.step4": "🐛 Tiny8 除錯 / 熱圖 — 像 Tiny8 一樣看 CPU 暫存器與記憶體",
    "welcome.step5": "🧮 ASM 輸入 — 寫一段組合語言,觀察 CPU↔GPU 怎麼合作",
    "welcome.cta": "點下方按鈕開始體驗。如果不知道從哪開始,先去「ASM 輸入」按下「📚 載入範例」!",
    "welcome.start": "好,開始!",
    "welcome.dont_show": "下次不要再顯示",

    # ----------- 成就 -----------
    "ach.first_run.name": "Hello, GPU!",
    "ach.first_run.desc": "第一次執行 ASM 程式",
    "ach.first_kwait.name": "懂得等待",
    "ach.first_kwait.desc": "第一次成功使用 KWAIT 同步 CPU 跟 GPU",
    "ach.first_klaunch.name": "起手第一發",
    "ach.first_klaunch.desc": "第一次提交 GPU kernel",
    "ach.full_load.name": "GPU 滿載",
    "ach.full_load.desc": "達到 100% GPU 利用率(所有 warp 同時忙碌)",
    "ach.memory_master.name": "記憶體達人",
    "ach.memory_master.desc": "在一個 session 內寫入記憶體 ≥ 16 個位址",
    "ach.kernel_collector.name": "Kernel 收藏家",
    "ach.kernel_collector.desc": "在一個 session 內提交 ≥ 5 顆 kernel",
    "ach.long_session.name": "馬拉松選手",
    "ach.long_session.desc": "單一 session 跑超過 100 個 cycle",
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
    "quiz.title": "考考你 — 看完 trace 之後測驗一下",
    "quiz.intro": "下面有 5 道選擇題,基於你剛剛跑的 ASM 程式。請選出你認為對的答案。",
    "quiz.score": "你答對了 {score} / {total} 題!",
    "quiz.next": "下一題 →",
    "quiz.finish": "看結果",
    "quiz.review_title": "解答解釋",
    "quiz.no_session": "請先到「ASM 輸入」分頁跑一段程式,再來測驗喔!",

    # ----------- 範例庫卡片 -----------
    "preset.hello.name": "你好 GPU",
    "preset.hello.desc": "最簡單的開門菜:CPU 提交一顆 vector_add,然後等它跑完",
    "preset.hello.stars": "★☆☆☆☆",
    "preset.burst.name": "連發三顆",
    "preset.burst.desc": "一口氣把 vector_add / hash / texture_load 三種 kernel 全丟給 GPU",
    "preset.burst.stars": "★★☆☆☆",
    "preset.loop.name": "迴圈發射",
    "preset.loop.desc": "用 DEC + BRNE 迴圈三次發 interpolation 給 GPU,展示控制流",
    "preset.loop.stars": "★★☆☆☆",
    "preset.memory_copy.name": "記憶體拷貝",
    "preset.memory_copy.desc": "把 RAM[0x60..0x65] 複製到 RAM[0x70..0x75],最後丟一顆 vector_add 給 GPU。Heatmap 會超漂亮!",
    "preset.memory_copy.stars": "★★★☆☆",
    "preset.sort_three.name": "三數排序",
    "preset.sort_three.desc": "用比較和條件分支把 R16/R17/R18 三個數字由小到大排好",
    "preset.sort_three.stars": "★★★☆☆",
    "preset.find_max.name": "找最大值",
    "preset.find_max.desc": "掃過記憶體 0x60..0x67 八個 byte,找出最大值放到 R0",
    "preset.find_max.stars": "★★★☆☆",
    "preset.counter.name": "倒數計時器",
    "preset.counter.desc": "從 9 倒數到 0,每數一個就提交一顆 hash kernel",
    "preset.counter.stars": "★★☆☆☆",
    "preset.mixed_burst.name": "混合工作負載",
    "preset.mixed_burst.desc": "依序提交所有 7 種 kernel,Heatmap 上會看到 SM 利用率波動",
    "preset.mixed_burst.stars": "★★★★☆",

    # ----------- 教學秀 / 給爸媽看 -----------
    "demo.title": "🎬 教學秀(自動播放)",
    "demo.subtitle": "本工具會循環跑下面這幾個範例,每 30 秒換一支。",
    "demo.now_playing": "正在跑:{name}",
    "demo.next_in": "{seconds} 秒後切換到下一支",

    # ----------- 錯誤訊息 -----------
    "err.assemble": "組譯失敗:{detail}",
    "err.empty_program": "ASM 編輯器是空的,請先寫一些指令或載入範例。",
    "err.no_history_session": "目前沒有可重播的 session,請先讓小工具跑一陣子。",
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
