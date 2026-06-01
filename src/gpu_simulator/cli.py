"""Command-line entry point.

Examples::

    gpu-simulator                               # defaults
    gpu-simulator --config ~/.gpu_simulator/my.json   # custom config
    gpu-simulator --real                        # enable real GPU sampling
    gpu-simulator --no-db                       # disable session recording
    gpu-simulator --sms 16 --vram 512           # one-off overrides
"""

from __future__ import annotations

import argparse
import contextlib
import sys

from gpu_simulator.config import AppConfig, load_config


def _force_utf8_stdio() -> None:
    """Make stdout/stderr UTF-8 so Chinese help strings render on Windows.

    Python 3.15 makes UTF-8 mode the default (PEP 686);
    until then, Windows consoles fall back to cp1252 which cannot encode
    Chinese characters in ``--help`` output.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(Exception):
                reconfigure(encoding="utf-8", errors="replace")


_force_utf8_stdio()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gpu-simulator",
        description=(
            "Desktop widget that visualizes a virtual GPU reacting to user actions, "
            "with optional real GPU monitoring and SQLite session recording."
        ),
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a JSON config file (default: ~/.gpu_simulator/config.json or bundled default).",
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Enable real GPU sampling (requires pynvml or GPUtil).",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Disable SQLite session recording for this run.",
    )
    parser.add_argument(
        "--easy",
        action="store_true",
        help="給爸媽看模式:簡化 UI、自動循環播放預設範例。",
    )
    parser.add_argument(
        "--no-welcome",
        action="store_true",
        help="不要顯示首次啟動的歡迎對話。",
    )
    parser.add_argument(
        "--serve-web",
        type=int,
        metavar="PORT",
        default=None,
        help="啟動時自動啟用 Web 鏡像 server,綁到指定 port(預設關閉)。",
    )
    parser.add_argument(
        "--cinema",
        action="store_true",
        help="啟動後立即進入電影模式,自動跑 60 秒 showcase(適合錄展示影片)。",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="開機直接跳到「💻 真實硬體」分頁 — 當作多核 CPU / GPU 即時儀表板用。",
    )
    parser.add_argument(
        "--lite",
        action="store_true",
        help="輕量模式:關掉粒子特效跟字元雨、SM 減半、tick 降頻,給低階電腦用。"
             "預設會自動偵測(4 核以下機器自動開啟),用此 flag 強制開啟。",
    )
    parser.add_argument(
        "--no-lite",
        action="store_true",
        help="強制關閉輕量模式(就算偵測到低階機器也保持完整特效)。",
    )
    parser.add_argument("--sms", type=int, help="Override number of streaming multiprocessors.")
    parser.add_argument("--warps-per-sm", type=int, help="Override warps per SM.")
    parser.add_argument("--vram", type=int, help="Override simulated VRAM capacity in MiB.")
    parser.add_argument("--tick", type=int, help="Override simulation tick interval (ms).")
    parser.add_argument("--width", type=int, help="Override window width (px).")
    parser.add_argument("--height", type=int, help="Override window height (px).")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print package version and exit.",
    )
    return parser.parse_args(argv)


def _apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    if args.sms is not None:
        config.gpu.num_sms = args.sms
    if args.warps_per_sm is not None:
        config.gpu.warps_per_sm = args.warps_per_sm
    if args.vram is not None:
        config.gpu.vram_capacity_mib = args.vram
    if args.tick is not None:
        config.widget.tick_interval_ms = args.tick
    if args.width is not None:
        config.widget.window_width = args.width
    if args.height is not None:
        config.widget.window_height = args.height
    if args.real:
        config.real_gpu.enabled = True
    if args.no_db:
        config.persistence.enabled = False
    # 第 21 輪:lite mode 決策
    # 優先順序:--no-lite 強制關 > --lite 強制開 > 自動偵測
    if args.no_lite:
        config.widget.lite_mode = False
    elif args.lite:
        config.widget.lite_mode = True
    else:
        # 自動偵測:邏輯核心 ≤ 2 OR 實體核心 ≤ 2 OR 記憶體 ≤ 4 GB → 自動開
        config.widget.lite_mode = _auto_detect_low_spec()
    return config


def _auto_detect_low_spec() -> bool:
    """回 True 代表這台機器算「低階電腦」,應該預設開啟輕量模式。

    判斷規則:
    * 邏輯核心 ≤ 2 顆,或
    * 實體核心 ≤ 2 顆,或
    * 系統總記憶體 ≤ 4 GB

    任何條件成立就回 True。psutil 取樣失敗時保守回 False(不影響其他功能)。
    """
    try:
        import psutil
    except ImportError:
        return False
    try:
        logical = psutil.cpu_count(logical=True) or 0
        physical = psutil.cpu_count(logical=False) or 0
        mem = psutil.virtual_memory().total
    except Exception:
        return False
    mem_gb = mem / (1024**3)
    return logical <= 2 or physical <= 2 or mem_gb <= 4.0


def _build_widget_overrides(args: argparse.Namespace) -> dict:
    overrides: dict = {}
    if args.easy:
        overrides["easy_mode"] = True
    if args.no_welcome:
        overrides["skip_welcome_dialog"] = True
    return overrides


def _run_headless(argv: list[str]) -> int:
    """`gpu-simulator run path/to/program.asm [--full-cpu] [--report] [--max-cycles N]`

    不開 GUI、不要任何 Qt;單純執行 asm,把結果用文字 + 可選的 markdown 報告
    輸出到 stdout / 指定資料夾。給 CI、批次測試、課堂示範用。
    """
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        prog="gpu-simulator run",
        description="Headless mode — 跑一支 .asm,文字輸出結果。",
    )
    parser.add_argument("source", help="要執行的 .asm 路徑")
    parser.add_argument(
        "--full-cpu",
        action="store_true",
        help="使用內嵌的真正 Tiny8 CPU(60+ 指令)。預設用我們的子集 CPU。",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=2000,
        help="最大執行 cycle 數(預設 2000)。",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        metavar="DIR",
        help="額外把 Markdown 實驗報告寫到這個目錄。",
    )
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"gpu-simulator run: 找不到檔案 {source_path}", file=sys.stderr)
        return 2
    source_text = source_path.read_text(encoding="utf-8")

    if args.full_cpu:
        from gpu_simulator.full_bridge import FullCPUGPUBridge

        bridge = FullCPUGPUBridge()
        bridge.load_source(source_text)
        cycles = bridge.run_until_halt(max_steps=args.max_cycles)
        cpu_registers = list(bridge.cpu.regs)
        cpu_memory = [bridge.cpu.read_ram(addr) for addr in range(256)]
    else:
        from gpu_simulator.bridge import CPUGPUBridge
        from gpu_simulator.cpu import assemble

        bridge = CPUGPUBridge()
        bridge.load_program(assemble(source_text))
        cycles = bridge.run_until_halt(max_cycles=args.max_cycles)
        cpu_registers = list(bridge.cpu.registers)
        cpu_memory = list(bridge.cpu.memory)

    print(f"=== gpu-simulator headless run · {source_path.name} ===")
    print(f"cycles executed: {cycles}")
    print(
        f"GPU kernels submitted={bridge.gpu.kernels_submitted} "
        f"completed={bridge.gpu.kernels_completed}"
    )
    print("registers (non-zero only):")
    for index, value in enumerate(cpu_registers):
        if value != 0:
            print(f"  R{index:02} = {value} (0x{value:02X})")

    if args.report:
        from gpu_simulator.lab_report import generate_report

        result = generate_report(
            title=source_path.stem,
            asm_source=source_text,
            trace_rows=list(bridge.trace),
            register_history=bridge.register_history,
            memory_history=bridge.memory_history,
            sreg_history=bridge.sreg_history,
            final_registers=cpu_registers,
            final_memory=cpu_memory,
            kernels_submitted=bridge.gpu.kernels_submitted,
            kernels_completed=bridge.gpu.kernels_completed,
            output_dir=args.report,
        )
        print(f"report → {result.markdown_path}")
        for image in result.image_paths:
            print(f"  + {image}")
    return 0


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    # ``run`` 子指令走 headless 路徑(不用 import Qt)
    if raw_argv and raw_argv[0] == "run":
        return _run_headless(raw_argv[1:])

    args = _parse_args(argv)
    if args.version:
        from gpu_simulator import __version__

        print(__version__)
        return 0

    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"gpu-simulator: failed to load config — {exc}", file=sys.stderr)
        return 2
    config = _apply_cli_overrides(config, args)

    # Imported lazily so ``--version`` / ``--help`` do not require a display.
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from gpu_simulator.single_instance import try_acquire_lock
    from gpu_simulator.widget import GPUVizWidget, WidgetConfig, _widget_config_from_app_config

    # 在 QApplication 建立之前,把高 DPI 屬性打開 —— 否則在 4K / 高 DPI 螢幕
    # 上,Qt 預設會把視窗畫得太小(看起來像縮圖)或座標錯位導致點不到。
    # PySide6 ≥ 6 預設啟用 AA_EnableHighDpiScaling,但顯式打開比較安全。
    for attr_name in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        attr = getattr(Qt, attr_name, None)
        if attr is not None:
            with contextlib.suppress(Exception):
                QApplication.setAttribute(attr, True)

    app = QApplication.instance() or QApplication(sys.argv)

    # 單實例保護:確保整台機器最多只有一份 widget 跑著,
    # 不然多份半透明 frameless widget 會疊在桌面上,使用者點不到任何一個。
    instance_lock = try_acquire_lock()
    if instance_lock is None:
        QMessageBox.information(
            None,
            "GPU Simulator 已經在執行",
            "GPU Simulator 已經有一份在跑了。\n\n"
            "請從桌面找出已開啟的 widget(它在某個角落,半透明、永遠置頂),\n"
            "或從工作管理員 (Ctrl+Shift+Esc) 結束舊的 instance 後再重啟。",
        )
        return 0
    # 把 lock socket 掛在 app 物件上避免被 GC,
    # process 結束時 OS 會自動釋放 port。
    app._gpu_simulator_instance_lock = instance_lock  # type: ignore[attr-defined]

    widget_config: WidgetConfig = _widget_config_from_app_config(config)
    for key, value in _build_widget_overrides(args).items():
        setattr(widget_config, key, value)
    widget = GPUVizWidget(app_config=config, widget_config=widget_config)
    if args.serve_web is not None:
        from gpu_simulator.web_mirror import MirrorServer

        widget._mirror_server = MirrorServer(
            widget._mirror_publisher, port=args.serve_web
        )
        widget._mirror_server.start()
        widget._mirror_button.setText("🛑 停止 Web 鏡像")
        print(f"web mirror started: {widget._mirror_server.url}")
    widget.show()
    if args.monitor:
        # 跳到 💻 真實硬體分頁 — pillar ③ 純儀表板用例
        with contextlib.suppress(Exception):
            tabs = widget._tabs
            for i in range(tabs.count()):
                if "真實硬體" in tabs.tabText(i):
                    tabs.setCurrentIndex(i)
                    break
    if args.cinema:
        # 等 widget 完成首次繪製再啟動 cinema(讓 layout 已穩定)
        from PySide6.QtCore import QTimer

        QTimer.singleShot(500, widget._start_cinema_mode)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
