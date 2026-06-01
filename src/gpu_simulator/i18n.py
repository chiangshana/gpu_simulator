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
    "app.title": "GPU 模擬器 · 桌面虛擬顯卡視覺化工具",
    "app.subtitle": "用白話教你看懂 CPU(電腦大腦)跟 GPU(顯示卡)在做什麼",
    "mode.live": "● 即時模式",
    "mode.replay": "● 重看舊紀錄 #{session_id}",
    "mode.asm": "● 寫程式模式",
    "mode.easy": "● 給爸媽看模式",

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
        "你每動一下滑鼠 / 鍵盤,GPU 就會收到一個要算的工作。"
        "看下面 8 顆運算單元(SM)跟 GPU 記憶體(VRAM)怎麼反應吧!"
    ),
    "section.sm_grid": "GPU 運算單元(SM,共 8 顆)的忙碌程度",
    "section.vram": "GPU 記憶體(VRAM)用了多少",
    "section.pipeline": "流水線(pipeline)五階段 — 每個平行小組跑到哪了",
    "section.event_log": "事件紀錄 — 剛剛發生什麼事",
    "section.analytics.title": "忙碌程度與 GPU 記憶體用量隨時間變化",
    "section.analytics.tip": (
        "橘色線 = GPU 多忙(百分比)、藍色線 = GPU 記憶體用了多少(MiB)"
    ),
    "section.history.title": "過去的執行紀錄(可重看 / 匯出)",
    "section.history.tip": (
        "選一筆過去的紀錄,可以重看,或匯出成表格(CSV)、報告(Markdown)、圖片(PNG)"
    ),
    "section.trace.title": "逐拍追蹤 — CPU 每一拍(cycle)做了什麼",
    "section.trace.tip": "每一橫列是一拍(cycle),有變動的格子會亮起來",
    "section.debug.title": "CPU 內部狀態觀察",
    "section.debug.tip": (
        "黑底是為了像專業除錯器(debugger)一樣;格子變黃色代表這一拍剛改變"
    ),
    "section.heatmap.title": "時間 × CPU 內部 熱力圖",
    "section.heatmap.tip": (
        "從上到下:狀態旗標(SREG 8 個小燈)/ 32 個小格子(暫存器 R0–R31)"
        " / 記憶體 0x60–0x7F,顏色越亮代表值越大"
    ),
    "section.input.title": "程式指令編輯區(組合語言 ASM)",
    "section.input.tip": "可以從上方挑現成範例,或自己寫一段組合語言(ASM)",
    "section.real_gpu": "你電腦真實的 GPU(只有 NVIDIA 顯卡才有資料)",

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
        "把下方的程式指令(組合語言 ASM)讀進來開始跑,"
        "「逐拍」「內部」「演化」三個分頁都會跟著動"
    ),
    "tooltip.step": "只走一拍(cycle),慢慢看每一行指令做了什麼",
    "tooltip.reset": "停下執行、清空紀錄,回到原本的即時模式",
    "tooltip.load_example": "載入內建範例程式到下方編輯器",
    "tooltip.record_start": "把畫面錄成 GIF 動圖,存在 ~/.gpu_simulator/recordings/",
    "tooltip.record_stop": "停止錄影並儲存 GIF",
    "tooltip.trophy_room": "看你已經解鎖的成就徽章",
    "tooltip.start_quiz": "5 題選擇題小測驗,看你剛剛跑的程式記了多少",
    "tooltip.start_tour": "重看一遍新手導覽",
    "tooltip.close": "關閉小工具,並把這次紀錄存進歷史",

    # ----------- 狀態列訊息 -----------
    "status.ready": "已就緒,點「執行」開始。",
    "status.running": "執行中,共 {count} 行指令…按「重置」可中止。",
    "status.halted": "走了 {cycles} 拍(cycle)後停下來。",
    "status.max_cycles": "達到最大拍數({limit}),已自動停下來。",
    "status.cycle_one": "第 {cycle} 拍 · {instruction}",
    "status.reset": "已重置,回到即時模式。",
    "status.example_loaded": "已載入範例:{name}",
    "status.recording": "🔴 錄影中… 已 {seconds} 秒",
    "status.recording_saved": "GIF 已儲存到 {path}",
    "status.kwait_indicator": "等待中 · CPU 在等 GPU 完成(KWAIT)",
    "status.running_indicator": "執行中 · CPU 正在跑",
    "status.halted_indicator": "已停止 · CPU 不跑了",

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

    # ----------- GPU 寵物表情語 -----------
    "pet.bored": "好閒喔…來點工作給我嘛 😴",
    "pet.warming": "嗯?有事要做了 🤔",
    "pet.busy": "正在認真幹活!💪",
    "pet.sweating": "我快忙不過來了 😅",
    "pet.melting": "我要燒起來啦!🔥",

    # ----------- 歡迎對話 -----------
    "welcome.title": "歡迎使用 GPU 模擬器!",
    "welcome.intro": (
        "這是一個會在桌面跑的虛擬顯卡模擬器。\n"
        "它會把你的滑鼠、鍵盤、開啟 App 等動作,即時翻譯成 GPU 要算的工作。\n"
        "下面 30 秒帶你看懂幾個重要分頁:"
    ),
    "welcome.step1": "⚡ 即時 — 動一下滑鼠,看下面 8 顆運算單元(SM)亮起來",
    "welcome.step2": "📈 趨勢 — 看 GPU 多忙、用了多少記憶體,隨時間怎麼變動",
    "welcome.step3": "📚 歷史 — 過去的執行紀錄都在這,可以重看或匯出",
    "welcome.step4": "🐞 內部 / 🌡️ 演化 — 看 CPU 內部的小格子(暫存器)與記憶體",
    "welcome.step5": "⌨️ 寫程式 — 寫一段程式指令(組合語言 ASM),看 CPU 跟 GPU 怎麼合作",
    "welcome.cta": (
        "點下方按鈕開始體驗。不知道從哪開始的話,先到「寫程式」分頁"
        "按「📚 載入範例」!"
    ),
    "welcome.start": "好,開始!",
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
    "preset.hello.name": "你好 GPU",
    "preset.hello.desc": "最簡單的開門菜:CPU 派一個「向量加法」工作給 GPU,然後等它做完",
    "preset.hello.stars": "★☆☆☆☆",
    "preset.burst.name": "連發三顆",
    "preset.burst.desc": "一口氣把「向量加法」「雜湊」「紋理載入」三種工作丟給 GPU",
    "preset.burst.stars": "★★☆☆☆",
    "preset.loop.name": "迴圈發射",
    "preset.loop.desc": "用迴圈連續派 3 次「線性插值」工作給 GPU,順便展示條件跳轉的寫法",
    "preset.loop.stars": "★★☆☆☆",
    "preset.memory_copy.name": "記憶體拷貝",
    "preset.memory_copy.desc": (
        "把記憶體 0x60..0x65 內容複製到 0x70..0x75,最後派一個「向量加法」工作給 GPU。"
        "熱力圖會超漂亮!"
    ),
    "preset.memory_copy.stars": "★★★☆☆",
    "preset.sort_three.name": "三數排序",
    "preset.sort_three.desc": (
        "用比較跟條件跳轉,把三個小格子(R16/R17/R18)裡的數字由小到大排好"
    ),
    "preset.sort_three.stars": "★★★☆☆",
    "preset.find_max.name": "找最大值",
    "preset.find_max.desc": "掃過記憶體 0x60..0x67 共 8 個位置,找出最大值放到 R0 格子",
    "preset.find_max.stars": "★★★☆☆",
    "preset.counter.name": "倒數計時器",
    "preset.counter.desc": "從 9 倒數到 0,每數一個就派一個「雜湊」工作給 GPU",
    "preset.counter.stars": "★★☆☆☆",
    "preset.mixed_burst.name": "混合工作負載",
    "preset.mixed_burst.desc": (
        "依序派出全部 7 種工作給 GPU,熱力圖上會看到運算單元(SM)忙碌程度波動"
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
