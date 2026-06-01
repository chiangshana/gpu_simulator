"""The top-level desktop widget.

Packs the sub-visualizers into seven tabs (Live / Analytics / History /
Trace / Debug / Heatmap / Input) plus an optional Real-GPU strip and
GPU pet face on top.  Drives the simulation via a
:class:`~PySide6.QtCore.QTimer`, drains the event-listener queue on
every tick so user actions feed real workloads, persists a
downsampled trace into :class:`~gpu_simulator.persistence.SessionStore`
for later replay and export, awards achievements, runs in-widget
quizzes, and can record itself as a GIF.

When ``WidgetConfig.easy_mode`` is on, the layout collapses to a
single self-explanatory tab that auto-cycles through preset programs
— that's the mode the family video uses.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gpu_simulator.achievements import (
    Achievement,
    AchievementStore,
    AchievementTracker,
)
from gpu_simulator.ai_explainer import (
    Explainer,
    ExplainRequest,
    summarize_registers,
    summarize_trace,
)
from gpu_simulator.ai_explainer import (
    is_available as ai_is_available,
)
from gpu_simulator.bridge import CPUGPUBridge
from gpu_simulator.challenges import (
    LeaderboardStore,
    daily_challenge,
    score_attempt,
)
from gpu_simulator.cinematic import (
    CinemaActionKind,
    CinemaPlayer,
    builtin_60_second_script,
)
from gpu_simulator.code_rain import build_overlay as build_code_rain_overlay
from gpu_simulator.command_palette import Command, open_palette
from gpu_simulator.config import AppConfig, user_config_dir
from gpu_simulator.core import GPU, GPUConfig
from gpu_simulator.cpu import AssemblerError, assemble
from gpu_simulator.dialogs import (
    AchievementToast,
    AIExplainerDialog,
    ChallengeDialog,
    DemoTab,
    GuidedLessonDialog,
    PresetMenu,
    QuizDialog,
    TrophyRoomDialog,
    WelcomeDialog,
)
from gpu_simulator.divergence import (
    analyze_branch,
    analyze_memory_access,
    builtin_coalescing_presets,
    builtin_divergence_presets,
)
from gpu_simulator.divergence import (
    summary as divergence_summary,
)
from gpu_simulator.easter_eggs import (
    EasterEggDetector,
    make_default_handlers,
    qt_key_to_label,
)
from gpu_simulator.easter_eggs import (
    dispatch as eegg_dispatch,
)
from gpu_simulator.event_listener import EventListener, EventListenerConfig, KernelQueue
from gpu_simulator.exceptions import PersistenceError
from gpu_simulator.full_bridge import FullCPUGPUBridge
from gpu_simulator.gpu_pet import GPUPetWidget
from gpu_simulator.i18n import t
from gpu_simulator.lab_report import generate_report
from gpu_simulator.lessons import LESSONS
from gpu_simulator.mood_calendar import DayMood, MoodLog, build_mood_calendar_widget
from gpu_simulator.particle_fx import build_overlay as build_particle_overlay
from gpu_simulator.persistence import SessionStore
from gpu_simulator.plugins import PluginRegistry, load_plugins
from gpu_simulator.profiler import profile_session
from gpu_simulator.quiz import build_dynamic_questions, build_quiz
from gpu_simulator.real_gpu import RealGPUSampler
from gpu_simulator.recorder import GIFRecorder, RecorderError
from gpu_simulator.sounds import SoundEffect, play, play_kernel_chord
from gpu_simulator.status_bar import StatusSnapshot, build_status_bar, update_status_bar
from gpu_simulator.themes import ALL_THEMES, apply_theme
from gpu_simulator.toast import ToastLevel, ToastManager, ToastSpec
from gpu_simulator.tts import is_available as tts_is_available
from gpu_simulator.tts import speak as tts_speak
from gpu_simulator.visualizer import (
    DEFAULT_ASM_PROGRAM,
    AsmInputPanel,
    CycleCinemaView,
    DebugView,
    DivergenceView,
    EventLogWidget,
    GPU3DView,
    HeatmapView,
    LiveCommentaryPanel,
    MemoryMapView,
    PipelineWidget,
    RealGPUPanel,
    SequenceDiagramView,
    SMGridWidget,
    StatsBar,
    Tiny8FullView,
    TraceTable,
    VRAMBarWidget,
    VRAMBlocksWidget,
    WarpPipelineAnimationWidget,
    _section_label,
)
from gpu_simulator.web_mirror import MirrorServer, SnapshotPublisher


@dataclass
class WidgetConfig:
    """UI-side knobs(mirrors the persisted config for easy overrides)."""

    tick_interval_ms: int = 100
    kernels_per_tick: int = 4
    window_width: int = 720
    window_height: int = 640
    background_alpha: int = 210
    snapshot_record_every: int = 5  # persist one snapshot every N ticks
    asm_max_cycles: int = 5000
    easy_mode: bool = False
    easy_mode_demo_seconds: int = 30
    skip_welcome_dialog: bool = False
    # 第 21 輪:低階電腦自動偵測後的輕量模式。
    # 關掉粒子特效 / Matrix 字元雨 / 拉長 timer 頻率,讓 4 核以下機器也能順跑。
    lite_mode: bool = False


class WidgetMode:
    """String constants for the widget's mode-state machine."""

    LIVE = "live"
    REPLAY = "replay"
    ASM = "asm"
    FULL_ASM = "full_asm"  # full Tiny8 CPU ↔ GPU integration tab is driving


# ---------------------------------------------------------------------------
# easy-mode helpers
# ---------------------------------------------------------------------------
EASY_MODE_DEMOS: tuple[str, ...] = (
    "hello_gpu.asm",
    "burst_and_count.asm",
    "memory_copy.asm",
    "counter.asm",
    "mixed_burst.asm",
)


def _examples_dir() -> Path:
    """Return the absolute path to the bundled examples folder."""
    return Path(__file__).resolve().parent.parent.parent / "examples"


def _welcome_marker_path() -> Path:
    return user_config_dir() / "welcomed"


_DEFAULT_FULL_ASM_PROGRAM = """; 用完整版 Tiny8 CPU(60+ 指令)寫一段跟 GPU 互動的程式
; 0x40 = KLAUNCH(寫入 = 用 R 內容當 kernel id 提交)
; 0x41 = HINT(提示值)
; 0xFF = KWAIT(寫入 = CPU 卡到 GPU 都跑完)

    ldi r16, 0          ; vector_add 的 kernel id
    ldi r17, 3          ; 想連發 3 次

burst:
    out 0x40, r16       ; KLAUNCH
    dec r17
    brne burst

    out 0xFF, r17       ; KWAIT(R17 已是 0,值不重要)

    ; 用 Tiny8 完整版才有的 MUL 指令算 6 × 7
    ldi r18, 6
    ldi r19, 7
    mul r18, r19        ; R18 ← 42(完整版才支援)
"""


# ---------------------------------------------------------------------------
# helpers to build subsystems from an AppConfig
# ---------------------------------------------------------------------------
def _gpu_config_from_app_config(app_config: AppConfig) -> GPUConfig:
    gpu_section = app_config.gpu
    # 輕量模式把 SM 從 8 顆降到 4 顆(顯著減少要繪製的方格數量)
    num_sms = gpu_section.num_sms
    if app_config.widget.lite_mode:
        num_sms = min(num_sms, 4)
    return GPUConfig(
        num_sms=num_sms,
        warps_per_sm=gpu_section.warps_per_sm,
        threads_per_warp=gpu_section.threads_per_warp,
        vram_capacity_bytes=gpu_section.vram_capacity_mib * 1024 * 1024,
        shared_memory_per_sm_bytes=gpu_section.shared_memory_per_sm_kib * 1024,
        registers_per_thread=gpu_section.registers_per_thread,
        event_log_size=gpu_section.event_log_size,
    )


def _widget_config_from_app_config(app_config: AppConfig) -> WidgetConfig:
    widget_section = app_config.widget
    return WidgetConfig(
        tick_interval_ms=widget_section.tick_interval_ms,
        kernels_per_tick=widget_section.kernels_per_tick,
        window_width=widget_section.window_width,
        window_height=widget_section.window_height,
        background_alpha=widget_section.background_alpha,
        lite_mode=widget_section.lite_mode,
    )


def _default_db_path(app_config: AppConfig) -> Path:
    from gpu_simulator.config import user_config_dir

    return user_config_dir() / app_config.persistence.database_filename


# ---------------------------------------------------------------------------
# main widget
# ---------------------------------------------------------------------------
class GPUVizWidget(QWidget):
    """The desktop window that visualizes the virtual GPU."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        widget_config: WidgetConfig | None = None,
        gpu: GPU | None = None,
        listener: EventListener | None = None,
        kernel_queue: KernelQueue | None = None,
        session_store: SessionStore | None = None,
        real_gpu_sampler: RealGPUSampler | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_config = app_config or AppConfig()
        self._widget_config = widget_config or _widget_config_from_app_config(self._app_config)

        self._gpu = gpu or GPU(_gpu_config_from_app_config(self._app_config))
        self._kernel_queue = kernel_queue or KernelQueue()
        self._listener = listener or EventListener(
            self._kernel_queue,
            config=EventListenerConfig(
                mouse_move_throttle_seconds=self._app_config.event_listener.mouse_move_throttle_seconds,
                idle_threshold_seconds=self._app_config.event_listener.idle_threshold_seconds,
                focus_poll_interval_seconds=self._app_config.event_listener.focus_poll_interval_seconds,
                process_poll_interval_seconds=self._app_config.event_listener.process_poll_interval_seconds,
            ),
            trigger_mapping=self._app_config.trigger_mapping,
        )
        self._session_store = session_store
        if self._session_store is None and self._app_config.persistence.enabled:
            self._session_store = self._try_open_session_store()
        self._session_id: int | None = None
        self._real_gpu_sampler = real_gpu_sampler
        if self._real_gpu_sampler is None and self._app_config.real_gpu.enabled:
            self._real_gpu_sampler = RealGPUSampler(
                preferred_backend=self._app_config.real_gpu.preferred_backend
            )

        # mode state machine
        self._mode: str = WidgetMode.LIVE

        # replay state
        self._replay_snapshots: list = []
        self._replay_index: int = 0
        self._replay_session_id: int | None = None

        # asm-mode state (subset CPU)
        self._bridge: CPUGPUBridge | None = None
        self._asm_run_active: bool = False
        self._asm_cycles_run: int = 0
        self._asm_seen_kwait: bool = False
        self._asm_memory_writes: set[int] = set()
        self._last_asm_run_summary: dict | None = None

        # full Tiny8 CPU ↔ GPU bridge state
        self._full_bridge: FullCPUGPUBridge | None = None
        self._full_run_active: bool = False
        self._full_steps_run: int = 0
        self._full_previous_registers: tuple[int, ...] | None = None
        self._full_previous_memory: tuple[int, ...] | None = None

        # 第九輪新增的狀態
        self._mirror_publisher = SnapshotPublisher()
        self._mirror_server: MirrorServer | None = None
        self._leaderboard_store: LeaderboardStore | None = None
        self._latest_challenge_result = None  # 最近一次跑出的 challenge 結果
        self._asm_source_for_report: str = ""  # 給 lab_report 用的最近一支 asm

        # 第十輪新增的狀態
        self._current_theme_index: int = 0
        self._plugin_registry: PluginRegistry = load_plugins()

        # 第十一輪新增的視覺特效狀態
        self._particle_overlay = None    # 建立在 _build_layout 後
        self._code_rain_overlay = None   # 同上
        self._cinema_player: CinemaPlayer | None = None
        self._cinema_timer: QTimer | None = None
        self._cinema_caption_label: QLabel | None = None
        self._tts_enabled: bool = False

        # achievements
        self._achievement_store = self._try_open_achievement_store()
        self._achievement_tracker = (
            AchievementTracker(self._achievement_store, self._on_achievement_unlocked)
            if self._achievement_store is not None
            else None
        )
        self._idle_kernel_seen: bool = False

        # recorder
        self._recorder: GIFRecorder | None = None
        self._recorder_status_timer = QTimer(self)
        self._recorder_status_timer.setInterval(1000)
        self._recorder_status_timer.timeout.connect(self._refresh_recorder_status)

        # easy-mode rotation
        self._easy_demo_index = 0
        self._easy_demo_timer = QTimer(self)
        self._easy_demo_timer.setInterval(self._widget_config.easy_mode_demo_seconds * 1000)
        self._easy_demo_timer.timeout.connect(self._easy_demo_next)
        self._easy_countdown_timer = QTimer(self)
        self._easy_countdown_timer.setInterval(1000)
        self._easy_countdown_timer.timeout.connect(self._easy_demo_tick_countdown)
        self._easy_seconds_remaining = self._widget_config.easy_mode_demo_seconds

        self._drag_offset: QPoint | None = None

        self._setup_window_flags()
        self._build_layout()
        self._wire_signals()
        self._start_loops()
        self._setup_visual_overlays()
        self._maybe_show_welcome_dialog()
        if self._widget_config.easy_mode:
            self._easy_demo_start()

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _setup_window_flags(self) -> None:
        # 從第 20 輪開始改成「標準視窗」 —— 有標題列、X 鈕、在 taskbar 看得到、
        # 不透明。原本的 frameless + transparent + Tool 三招組合在很多使用者環境
        # 會出現「視窗存在但點不到」的詭異 bug,捨棄炫炮、保住可用性。
        self.setWindowTitle("GPU 模擬器 — CPU↔GPU 視覺化教學工具")
        # 用「最小尺寸」而不是「固定尺寸」,讓使用者可以拉大、自由縮放
        self.setMinimumSize(
            self._widget_config.window_width,
            self._widget_config.window_height,
        )
        # 啟動後置中到當前螢幕,避免在多螢幕環境跑到看不到的地方
        self._center_on_screen()

    def _center_on_screen(self) -> None:
        """把視窗移到當前螢幕的中央。"""
        try:
            from PySide6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
            if screen is None:
                return
            geom = screen.availableGeometry()
            x = geom.x() + (geom.width() - self.width()) // 2
            y = geom.y() + (geom.height() - self.height()) // 2
            # 確保不會跑到負座標
            self.move(max(geom.x(), x), max(geom.y(), y))
        except Exception:
            pass

    def _build_layout(self) -> None:
        # shared live-mode widgets
        self._stats_bar = StatsBar(self)
        self._sm_grid = SMGridWidget(self)
        self._vram_bar = VRAMBarWidget(self)
        self._vram_blocks = VRAMBlocksWidget(self)
        self._pipeline = PipelineWidget(self)
        self._warp_animation = WarpPipelineAnimationWidget(self)
        self._event_log = EventLogWidget(self)

        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        live_layout.setContentsMargins(4, 4, 4, 4)
        live_layout.setSpacing(4)
        live_layout.addWidget(self._stats_bar)
        live_layout.addWidget(_section_label(t("section.live.tip")))
        live_layout.addWidget(_section_label(t("section.sm_grid")))
        live_layout.addWidget(self._sm_grid, 3)
        live_layout.addWidget(_section_label(t("section.vram")))
        live_layout.addWidget(self._vram_bar)
        live_layout.addWidget(self._vram_blocks, 1)
        live_layout.addWidget(_section_label(t("section.pipeline")))
        live_layout.addWidget(self._pipeline)
        live_layout.addWidget(_section_label("⚙ Warp 5 階 Pipeline 動畫"))
        live_layout.addWidget(self._warp_animation, 2)
        live_layout.addWidget(_section_label(t("section.event_log")))
        live_layout.addWidget(self._event_log, 3)

        # (第 23 輪砍掉:Analytics chart + History panel)

        self._trace_table = TraceTable(parent=self)
        self._commentary_panel = LiveCommentaryPanel(parent=self)
        trace_tab = QWidget()
        trace_layout = QVBoxLayout(trace_tab)
        trace_layout.setContentsMargins(4, 4, 4, 4)
        trace_layout.addWidget(_section_label(t("section.trace.title")))
        trace_layout.addWidget(_section_label(t("section.trace.tip")))
        trace_split = QHBoxLayout()
        trace_split.setContentsMargins(0, 0, 0, 0)
        trace_split.addWidget(self._trace_table, 5)
        trace_split.addWidget(self._commentary_panel, 3)
        trace_layout.addLayout(trace_split, 1)

        self._debug_view = DebugView(parent=self)
        debug_tab = QWidget()
        debug_layout = QVBoxLayout(debug_tab)
        debug_layout.setContentsMargins(4, 4, 4, 4)
        debug_layout.addWidget(_section_label(t("section.debug.title")))
        debug_layout.addWidget(_section_label(t("section.debug.tip")))
        debug_layout.addWidget(self._debug_view, 1)

        self._heatmap_view = HeatmapView(parent=self)
        heatmap_tab = QWidget()
        heatmap_layout = QVBoxLayout(heatmap_tab)
        heatmap_layout.setContentsMargins(4, 4, 4, 4)
        heatmap_layout.addWidget(_section_label(t("section.heatmap.title")))
        heatmap_layout.addWidget(_section_label(t("section.heatmap.tip")))
        heatmap_layout.addWidget(self._heatmap_view, 1)

        # Sequence diagram tab — UML-style CPU/GPU lanes
        self._sequence_view = SequenceDiagramView(parent=self)
        sequence_tab = QWidget()
        sequence_layout = QVBoxLayout(sequence_tab)
        sequence_layout.setContentsMargins(4, 4, 4, 4)
        sequence_layout.addWidget(
            _section_label(
                "🔁 CPU 跟 GPU 對話的時序圖 — 橘色實線箭頭往下 = CPU 派工(KLAUNCH);"
                "綠色虛線往上 = GPU 回報「我做完了」"
            )
        )
        sequence_layout.addWidget(self._sequence_view, 1)

        # Memory map tab — visual diagram of the 256-byte address space
        self._memory_map_view = MemoryMapView(parent=self)
        memory_map_tab = QWidget()
        memory_map_layout = QVBoxLayout(memory_map_tab)
        memory_map_layout.setContentsMargins(4, 4, 4, 4)
        memory_map_layout.addWidget(
            _section_label(
                "🗺️ 記憶體地圖 — 寫到「橘色 / 綠色 / 藍色」格子等於對 GPU 下指令"
            )
        )
        memory_map_layout.addWidget(self._memory_map_view, 1)

        # 🏗️ 3D GPU view (isometric, QPainter-based)
        self._gpu_3d_view = GPU3DView(parent=self)
        gpu_3d_tab = QWidget()
        gpu_3d_layout = QVBoxLayout(gpu_3d_tab)
        gpu_3d_layout.setContentsMargins(4, 4, 4, 4)
        gpu_3d_layout.addWidget(
            _section_label(
                "🏗️ 3D 視圖 — 8 顆 SM 等距投影,塔越高利用率越高;KLAUNCH 時頂上會有橘色光球"
            )
        )
        gpu_3d_layout.addWidget(self._gpu_3d_view, 1)

        # (第 23 輪砍掉:🎮 ASM 遊戲機 — Conway's Game of Life)

        # 🧠 Divergence + coalescing 視圖
        self._divergence_view = DivergenceView(parent=self)
        self._divergence_presets = builtin_divergence_presets()
        self._coalescing_presets = builtin_coalescing_presets()
        self._divergence_index = 0
        self._coalescing_index = 0

        def _cycle_divergence() -> None:
            self._divergence_index = (
                self._divergence_index + 1
            ) % len(self._divergence_presets)
            self._refresh_divergence_view()

        def _cycle_coalescing() -> None:
            self._coalescing_index = (
                self._coalescing_index + 1
            ) % len(self._coalescing_presets)
            self._refresh_divergence_view()

        self._divergence_swap_btn = self._create_action_button(
            "🔀 換分支模式", "切換到下一個「平行小組(warp)分歧」的預設情境", _cycle_divergence
        )
        self._coalescing_swap_btn = self._create_action_button(
            "📚 換讀取模式",
            "切換到下一個「記憶體合併讀取(memory coalescing)」的預設情境",
            _cycle_coalescing,
        )
        divergence_tab = QWidget()
        divergence_layout = QVBoxLayout(divergence_tab)
        divergence_layout.setContentsMargins(4, 4, 4, 4)
        divergence_layout.addWidget(
            _section_label("🧠 Warp 發散 + 記憶體 coalescing(GPU 性能教學)")
        )
        divergence_layout.addWidget(self._divergence_view, 1)
        div_buttons = QHBoxLayout()
        div_buttons.addWidget(self._divergence_swap_btn)
        div_buttons.addWidget(self._coalescing_swap_btn)
        div_buttons.addStretch(1)
        divergence_layout.addLayout(div_buttons)

        self._refresh_divergence_view()

        # 🎬 Cycle Cinema — synchronized CPU + GPU view with VCR controls
        self._cinema_view = CycleCinemaView(parent=self)
        cinema_tab = QWidget()
        cinema_layout = QVBoxLayout(cinema_tab)
        cinema_layout.setContentsMargins(4, 4, 4, 4)
        cinema_layout.addWidget(
            _section_label(
                "🎬 慢動作劇場 — 同框看 CPU 跟 GPU 每一拍(cycle)的合作,可拖下方拉桿前後播"
            )
        )
        cinema_layout.addWidget(self._cinema_view, 1)

        # Input tab — preset cards (top, scrollable) + asm editor (bottom)
        self._preset_menu = PresetMenu(_examples_dir(), parent=self)
        self._asm_panel = AsmInputPanel(parent=self)
        input_tab = QWidget()
        input_layout = QVBoxLayout(input_tab)
        input_layout.setContentsMargins(4, 4, 4, 4)
        input_layout.setSpacing(4)
        input_layout.addWidget(_section_label("📚 範例庫(點下方卡片任一個就能直接跑)"))
        input_layout.addWidget(self._preset_menu, 4)
        input_layout.addWidget(_section_label(t("section.input.title")))
        input_layout.addWidget(self._asm_panel, 5)

        # Tiny8 完整版 ↔ GPU 整合分頁
        self._tiny8_full_view = Tiny8FullView(parent=self)
        self._full_asm_panel = AsmInputPanel(parent=self)
        self._full_asm_panel.set_program_text(_DEFAULT_FULL_ASM_PROGRAM)
        full_tab = QWidget()
        full_layout = QVBoxLayout(full_tab)
        full_layout.setContentsMargins(4, 4, 4, 4)
        full_layout.setSpacing(4)
        full_layout.addWidget(
            _section_label(
                "🧬 Tiny8 完整版 CPU ↔ 虛擬 GPU(全 60+ 指令、寫到 0x40 / 0xFF 即觸發 GPU 工作)"
            )
        )
        full_layout.addWidget(self._tiny8_full_view, 4)
        full_layout.addWidget(
            _section_label("💻 完整 Tiny8 程式編輯器(組合語言 ASM,支援 60+ 條指令)")
        )
        full_layout.addWidget(self._full_asm_panel, 4)

        # demo tab (only shown in easy mode)
        self._demo_tab = DemoTab(parent=self)

        # 第十二輪:CPU 狀態時間熱圖分頁
        from gpu_simulator.cpu_heatmap import build_heatmap_tab as build_cpu_state_heatmap_tab
        cpu_state_heatmap_tab = build_cpu_state_heatmap_tab(parent=self)

        # 第十二輪加碼:真實硬體(多核 CPU + 真實 GPU)分頁
        from gpu_simulator.real_hardware import RealHardwareSampler, build_real_hardware_panel
        real_hw_tab = build_real_hardware_panel(parent=self)

        # 第十三輪:🪞 對照鏡 — 模擬 GPU 8 SM vs 真實 CPU N 核並排
        from gpu_simulator.mirror_dashboard import (
            build_mirror_dashboard,
            compose_snapshot,
        )

        self._mirror_sampler = RealHardwareSampler()

        def _mirror_snapshot_provider():
            return compose_snapshot(
                sim_snapshot=self._gpu.snapshot(),
                real_sample=self._mirror_sampler.sample(),
            )

        def _mirror_trigger_workload():
            # 觸發一連串模擬 kernel,讓左邊飆高、右邊基本不動
            from gpu_simulator.kernel import KernelLibrary

            with contextlib.suppress(Exception):
                for factory in (
                    KernelLibrary.vector_add,
                    KernelLibrary.texture_load,
                    KernelLibrary.hash_kernel,
                ):
                    try:
                        kernel = factory(trigger="mirror_demo")
                    except TypeError:
                        # hash_kernel requires key_repr
                        kernel = KernelLibrary.hash_kernel("M", trigger="mirror_demo")
                    self._kernel_queue.push(kernel)
            self._trigger_particles_on_kernel_launch()

        mirror_tab = build_mirror_dashboard(
            self,
            snapshot_provider=_mirror_snapshot_provider,
            on_trigger_workload=_mirror_trigger_workload,
        )

        self._tabs = QTabWidget(self)
        self._tabs.setStyleSheet(
            """
            QTabWidget::pane { border: 0; }
            QTabBar::tab {
                background: rgba(40, 46, 64, 200);
                color: rgb(200, 210, 230);
                padding: 3px 10px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { background: rgba(90, 130, 200, 230); color: white; }
            """
        )
        if self._widget_config.easy_mode:
            self._tabs.addTab(live_tab, t("tab.live"))
            self._tabs.addTab(self._demo_tab, t("tab.demo"))
        else:
            # 分頁標題改用「emoji + 2-3 字」壓縮版,讓 16 顆分頁在 720px 寬下能全顯示;
            # 完整中文敘述放 tooltip。
            def add_tab(widget, short_label: str, tooltip: str) -> None:
                idx = self._tabs.addTab(widget, short_label)
                self._tabs.setTabToolTip(idx, tooltip)

            # 14 個分頁 tooltip 採用「白話 + 括號標技術詞」風格
            add_tab(
                mirror_tab,
                "🪞 對照",
                "對照鏡 — 模擬 GPU 8 個運算單元(SM)與本機 CPU 各邏輯核心並排顯示,"
                "用於即時對比兩端負載",
            )
            add_tab(
                cpu_state_heatmap_tab,
                "🌡️ 變化",
                "狀態變化圖 — 執行一段 Tiny8 ASM,以三層 matplotlib heatmap 呈現 "
                "SREG 狀態旗標、R0–R31 通用暫存器、記憶體 0x60–0x7F 隨 cycle 的演化",
            )
            add_tab(
                real_hw_tab,
                "💻 硬體",
                "本機硬體儀表板 — 各顆 CPU 邏輯核心即時使用率,以及 NVIDIA 顯卡的"
                "使用率、記憶體、溫度、功耗(若有)",
            )
            # 模擬層其他分頁
            add_tab(
                live_tab,
                "⚡ 即時",
                "即時模擬 — 滑鼠/鍵盤事件觸發對應 kernel,顯示 8 個 SM、VRAM、"
                "5 階 pipeline 的即時反應",
            )
            add_tab(
                cinema_tab,
                "🎬 Cinema",
                "慢動作劇場 — CPU 與 GPU 並排播放,可拖時間軸前後檢視任一 cycle 的協同狀態",
            )
            add_tab(
                full_tab,
                "🧬 完整 CPU",
                "Tiny8 完整 ISA — 內嵌完整 Tiny8 處理器,支援 60 餘條指令"
                "(ADD、MUL、CALL、RJMP 等)",
            )
            add_tab(
                input_tab,
                "⌨️ 寫程式",
                "程式編輯器 — 撰寫 Tiny8 子集組合語言(ASM),內建多支範例可一鍵載入",
            )
            # 除錯與視覺化
            add_tab(
                trace_tab,
                "📜 逐拍",
                "逐拍紀錄表 — 每個 cycle 一列,變動欄位高亮;"
                "點任一列可回溯該 cycle 的完整狀態",
            )
            add_tab(
                debug_tab,
                "🐞 內部",
                "CPU 內部觀察 — 32 個通用暫存器(R0–R31)與記憶體區段即時顯示,"
                "變動格高亮",
            )
            add_tab(
                heatmap_tab,
                "📊 演化",
                "暫存器/記憶體值隨 cycle 演化的色塊圖",
            )
            add_tab(
                sequence_tab,
                "🔁 對話",
                "CPU↔GPU 互動時序圖 — UML 風格雙泳道,呈現 KLAUNCH 派發與"
                "kernel 完成事件",
            )
            add_tab(
                memory_map_tab,
                "🗺️ 記憶",
                "256 byte 完整記憶體地圖,標示 0x40 / 0x41 / 0xFF 三個 I/O 控制位址",
            )
            add_tab(
                gpu_3d_tab,
                "🏗️ 3D",
                "3D 等距投影視圖 — 8 個 SM 呈現為立體高塔,塔高反映各 SM 的使用率",
            )
            # 進階主題(最後一個,後面三個 [遊戲 / 趨勢 / 歷史]
            # 在第 22 輪砍掉以精簡介面 — 程式碼還在,以後想恢復把它們加回 add_tab 即可)
            add_tab(
                divergence_tab,
                "🧠 進階",
                "進階 GPU 概念 — warp 執行分歧(branch divergence)與記憶體合併存取"
                "(memory coalescing)的視覺化",
            )
            # 已砍:🎮 遊戲(Conway's Life)/ 📈 趨勢(Analytics)/ 📚 歷史(Session history)
            # 對應的 widget instance 仍在記憶體中以避免影響其他模組,
            # 但不會出現在分頁列上。

        # real GPU panel (shown only when a backend was initialised)
        self._real_gpu_panel = RealGPUPanel(self)
        if self._real_gpu_sampler is None or not self._real_gpu_sampler.available():
            self._real_gpu_panel.set_unavailable(
                "real GPU disabled (enable via --real or config)"
                if self._real_gpu_sampler is None
                else "no GPU backend available"
            )

        # title row
        self._close_button = QPushButton("×", self)
        self._close_button.setFixedSize(22, 22)
        self._close_button.clicked.connect(self.close)
        self._close_button.setToolTip(t("tooltip.close"))
        self._close_button.setStyleSheet(
            """
            QPushButton {
                background: rgba(200, 70, 70, 200);
                color: white;
                border: none;
                border-radius: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(230, 90, 90, 240); }
            """
        )
        self._title_label = QLabel(t("app.title"))
        self._title_label.setStyleSheet(
            "color: rgba(200, 210, 230, 230); font-weight: bold; font-size: 11px;"
        )
        self._mode_label = QLabel(t("mode.live"))
        self._mode_label.setStyleSheet(
            "color: rgba(120, 220, 140, 230); font-weight: bold; font-size: 10px;"
        )

        title_row = QHBoxLayout()
        title_row.setContentsMargins(4, 0, 2, 0)
        title_row.addWidget(self._title_label)
        title_row.addStretch(1)
        title_row.addWidget(self._mode_label)
        title_row.addSpacing(6)
        title_row.addWidget(self._close_button)

        # GPU pet on top of the tabs
        self._pet_widget = GPUPetWidget(self)

        # Action button row (trophy / quiz / tour / recorder)
        self._trophy_button = self._create_action_button(
            t("btn.trophy_room"), t("tooltip.trophy_room"), self._show_trophy_room
        )
        self._quiz_button = self._create_action_button(
            t("btn.start_quiz"), t("tooltip.start_quiz"), self._show_quiz
        )
        self._tour_button = self._create_action_button(
            t("btn.start_tour"), t("tooltip.start_tour"),
            lambda: self._show_welcome_dialog(force=True),
        )
        self._record_button = self._create_action_button(
            t("btn.record_start"), t("tooltip.record_start"), self._toggle_recorder
        )
        self._lesson_button = self._create_action_button(
            "🎓 教學課程",
            "打開 5 課中文教學導覽,從認識 SM 到完整 Tiny8 範例",
            self._show_lesson_dialog,
        )
        self._ai_button = self._create_action_button(
            "🤖 AI 解釋",
            "用 AI(Claude)把剛剛的程式跟執行紀錄翻成白話中文解釋",
            self._show_ai_explainer,
        )
        self._challenge_button = self._create_action_button(
            "🏁 每日挑戰",
            "看今天的程式設計小挑戰,完成後分數會上排行榜",
            self._show_daily_challenge,
        )
        self._lab_report_button = self._create_action_button(
            "📜 產出報告",
            "把剛跑完的程式自動寫成一份附圖的文字報告(Markdown 格式)",
            self._generate_lab_report,
        )
        self._mirror_button = self._create_action_button(
            "🌐 開啟 Web 鏡像",
            "啟動 stdlib HTTP server,瀏覽器可看 GPU 即時狀態",
            self._toggle_web_mirror,
        )
        self._theme_button = self._create_action_button(
            "🎨 主題", "切換到下一個主題(Cyberpunk / Matrix / Retro DOS / Classic)",
            self._cycle_theme,
        )
        self._profiler_button = self._create_action_button(
            "📈 效能分析",
            "看剛跑的程式裡,每個 GPU 工作(kernel)花了多少時間 + Roofline 效能圖",
            self._show_profiler,
        )
        # ---- 第十一輪 spectacle 按鈕 ----
        self._cinema_button = self._create_action_button(
            "🎬 電影模式", "自動跑 60 秒 showcase,適合錄展示影片",
            self._start_cinema_mode,
        )
        self._tutorial_button = self._create_action_button(
            "📖 10 分鐘導覽",
            "10 分鐘詳細教學版 — 零程式基礎也能跟著看,逐個概念講解",
            self._start_tutorial_mode,
        )
        self._tts_button = self._create_action_button(
            "🗣️ TTS", "切換中文 TTS 旁白(需 pyttsx3)",
            self._toggle_tts,
        )

        action_row = QHBoxLayout()
        action_row.setContentsMargins(4, 0, 4, 0)
        action_row.setSpacing(4)
        action_row.addWidget(self._lesson_button)
        action_row.addWidget(self._trophy_button)
        action_row.addWidget(self._quiz_button)
        action_row.addWidget(self._challenge_button)
        action_row.addWidget(self._ai_button)
        action_row.addWidget(self._lab_report_button)
        action_row.addWidget(self._mirror_button)
        action_row.addWidget(self._theme_button)
        action_row.addWidget(self._profiler_button)
        action_row.addWidget(self._cinema_button)
        action_row.addWidget(self._tutorial_button)
        action_row.addWidget(self._tts_button)
        action_row.addWidget(self._tour_button)
        action_row.addWidget(self._record_button)
        action_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)
        layout.addLayout(title_row)
        layout.addWidget(self._pet_widget)
        if not self._widget_config.easy_mode:
            layout.addLayout(action_row)
        layout.addWidget(self._tabs, 1)
        layout.addWidget(_section_label(t("section.real_gpu")))
        layout.addWidget(self._real_gpu_panel)
        # 第十二輪:底部狀態列
        try:
            from gpu_simulator import __version__ as _version
        except Exception:
            _version = "0.10.0"
        self._status_bar_frame = build_status_bar(
            self,
            StatusSnapshot(version=_version, mode="即時", kernels=0,
                           utilization_percent=0.0, fps=0.0),
        )
        layout.addWidget(self._status_bar_frame)

    @staticmethod
    def _create_action_button(label: str, tooltip: str, on_click) -> QPushButton:
        """工具列按鈕 — 為了讓 13 顆按鈕在 720px 視窗排得下,只顯示 emoji,
        中文標籤跟說明都塞進 tooltip。

        ``label`` 的慣例是 ``"🎓 教學課程"``:第一個空白前是 emoji,後面是中文。
        """
        parts = label.split(" ", 1)
        if len(parts) == 2 and parts[0]:
            icon, text_part = parts[0], parts[1]
            full_tooltip = f"{text_part}\n\n{tooltip}" if tooltip else text_part
        else:
            icon, full_tooltip = label, tooltip
        button = QPushButton(icon)
        button.setToolTip(full_tooltip)
        button.setFixedSize(32, 24)
        button.setStyleSheet(
            """
            QPushButton {
                background: rgba(60, 70, 90, 220);
                color: rgb(220, 224, 236);
                border: 1px solid rgba(120, 180, 255, 100);
                border-radius: 4px;
                padding: 0px;
                font-size: 13px;
            }
            QPushButton:hover { background: rgba(90, 120, 170, 240); }
            QPushButton:pressed { background: rgba(120, 160, 220, 240); }
            """
        )
        button.clicked.connect(on_click)
        return button

    def _wire_signals(self) -> None:
        # (第 23 輪砍掉:_history_panel 的 refresh/replay/export 三條 signal)
        self._asm_panel.run_requested.connect(self._asm_run)
        self._asm_panel.step_requested.connect(self._asm_step_one)
        self._asm_panel.reset_requested.connect(self._asm_reset)
        self._asm_panel.load_example_requested.connect(self._asm_load_example)
        self._preset_menu.run_requested.connect(self._asm_run_with_source)
        self._preset_menu.load_requested.connect(self._asm_load_into_editor)
        self._full_asm_panel.run_requested.connect(self._full_run)
        self._full_asm_panel.step_requested.connect(self._full_step_one)
        self._full_asm_panel.reset_requested.connect(self._full_reset)
        self._full_asm_panel.load_example_requested.connect(self._full_load_example)
        self._trace_table.row_selected.connect(self._on_trace_row_selected)

    # ------------------------------------------------------------------
    # painting — 不再自繪背景(改用標準視窗後,Qt 自己會畫背景);
    # 保留方法以維持簽名,避免外部 hook 失效。
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

    # ------------------------------------------------------------------
    # drag-to-move — 標準視窗時 Qt 自己會處理拖曳標題列,但保留 child-aware
    # 邏輯以防使用者拉大視窗後想抓「邊框內空白」拖移
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # 只有「點到沒有 child widget 的純背景區」才當作要拖曳整個視窗。
        # 否則直接讓 child(tab bar、按鈕、輸入框…)收事件,避免 frameless widget
        # 的 drag handler 把使用者的點擊吞掉造成「分頁切不過去」。
        if event.button() == Qt.LeftButton:
            click_pos = (
                event.position().toPoint() if hasattr(event, "position") else event.pos()
            )
            if self.childAt(click_pos) is None:
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # simulation & listener loops
    # ------------------------------------------------------------------
    def _start_loops(self) -> None:
        self._listener.start()
        if self._session_store is not None:
            try:
                self._session_id = self._session_store.start_session(name="live")
            except PersistenceError as exc:
                print(f"[gpu_simulator] could not start session recording: {exc}")
                self._session_store = None
        self._tick_counter = 0
        self._kernels_this_session = 0
        self._timer = QTimer(self)
        # 輕量模式把模擬 tick 從 100ms 拉長到 250ms,大幅降低 CPU 用量
        # (代價:動畫看起來會慢一點,但低階機器才跑得動)
        tick_ms = self._widget_config.tick_interval_ms
        if getattr(self._widget_config, "lite_mode", False):
            tick_ms = max(250, tick_ms)
        self._timer.setInterval(tick_ms)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()
        self._real_gpu_timer = QTimer(self)
        self._real_gpu_timer.setInterval(
            int(self._app_config.real_gpu.sample_interval_seconds * 1000)
        )
        self._real_gpu_timer.timeout.connect(self._on_real_gpu_tick)
        if self._real_gpu_sampler is not None and self._real_gpu_sampler.available():
            self._real_gpu_timer.start()

    def _on_tick(self) -> None:
        if self._mode == WidgetMode.REPLAY:
            self._advance_replay()
            return
        if self._mode == WidgetMode.ASM:
            self._advance_asm_run()
            return
        if self._mode == WidgetMode.FULL_ASM:
            self._advance_full_run()
            return

        previous_submitted = self._gpu.kernels_submitted
        for kernel in self._kernel_queue.drain(limit=self._widget_config.kernels_per_tick):
            self._gpu.submit_kernel(kernel)
            if self._session_store is not None and self._session_id is not None:
                with contextlib.suppress(PersistenceError):
                    self._session_store.record_kernel_submission(
                        clock=self._gpu.clock,
                        kernel_name=kernel.name,
                        profile=kernel.profile.value,
                        trigger=kernel.trigger,
                        grid_size=kernel.grid_size,
                        block_size=kernel.block_size,
                        vram_bytes=kernel.vram_bytes,
                    )
        self._kernels_this_session += self._gpu.kernels_submitted - previous_submitted

        self._gpu.tick()
        snapshot = self._gpu.snapshot()
        self._render_snapshot(snapshot)
        self._persist_snapshot(snapshot)
        self._tick_counter += 1
        self._notify_achievement_tracker_from_snapshot(snapshot)

    def _render_snapshot(self, snapshot: dict) -> None:
        self._stats_bar.update_snapshot(snapshot)
        self._sm_grid.update_snapshot(snapshot)
        self._vram_bar.update_snapshot(snapshot)
        self._vram_blocks.update_snapshot(snapshot)
        self._pipeline.update_snapshot(snapshot)
        self._warp_animation.update_snapshot(snapshot)
        self._gpu_3d_view.update_snapshot(snapshot)
        self._event_log.update_snapshot(snapshot)
        # (第 23 輪砍掉:self._analytics_chart.update_snapshot)
        self._pet_widget.update_from_snapshot(snapshot)
        self._maybe_detect_idle_kernel(snapshot)
        self._mirror_publisher.publish(snapshot)
        # 第十一輪:把利用率餵給 code rain,讓它在高負載時下雨
        if self._code_rain_overlay is not None:
            self._code_rain_overlay.set_utilization(
                float(snapshot.get("overall_utilization", 0.0))
            )

    def _maybe_detect_idle_kernel(self, snapshot: dict) -> None:
        if self._idle_kernel_seen or self._achievement_tracker is None:
            return
        for entry in snapshot.get("event_log", []):
            message = str(entry.get("message", ""))
            if "idle_compression" in message or "閒置壓縮" in message:
                self._achievement_tracker.report_idle_kernel()
                self._idle_kernel_seen = True
                return

    def _notify_achievement_tracker_from_snapshot(
        self, snapshot: dict, *, cycles_observed: int | None = None
    ) -> None:
        if self._achievement_tracker is None:
            return
        cycles = cycles_observed if cycles_observed is not None else self._tick_counter
        self._achievement_tracker.report_snapshot(snapshot, cycles_observed=cycles)

    def _persist_snapshot(self, snapshot: dict) -> None:
        if self._session_store is None or self._session_id is None:
            return
        if self._tick_counter % self._widget_config.snapshot_record_every != 0:
            return
        try:
            self._session_store.record_snapshot(
                clock=snapshot.get("clock", 0),
                overall_utilization=snapshot.get("overall_utilization", 0.0),
                vram_used_bytes=snapshot.get("vram", {}).get("used_bytes", 0),
                snapshot=snapshot,
            )
            for entry in snapshot.get("event_log", [])[-4:]:
                self._session_store.record_event(
                    clock=entry["clock"], message=entry["message"]
                )
        except PersistenceError:
            pass

    def _on_real_gpu_tick(self) -> None:
        if self._real_gpu_sampler is None or not self._real_gpu_sampler.available():
            return
        sample = self._real_gpu_sampler.sample()
        self._real_gpu_panel.update_sample(sample)

    # ------------------------------------------------------------------
    # (第 23 輪砍掉:_refresh_history / _start_replay — 對應 📚 歷史分頁)
    # _export_session 也一併移除
    # session 寫入 SQLite 仍會持續,只是沒有 UI 入口去看舊紀錄了
    # ------------------------------------------------------------------

    def _advance_replay(self) -> None:
        if self._replay_index >= len(self._replay_snapshots):
            self._exit_replay()
            return
        row = self._replay_snapshots[self._replay_index]
        self._replay_index += 1
        self._render_snapshot(row.snapshot)

    def _exit_replay(self) -> None:
        self._replay_snapshots = []
        self._replay_index = 0
        self._replay_session_id = None
        self._mode = WidgetMode.LIVE
        self._set_mode_label(t("mode.live"), QColor(120, 220, 140))

    # ------------------------------------------------------------------
    # ASM mode (Tiny8-style CPU + GPU input)
    # ------------------------------------------------------------------
    def _asm_load_example(self) -> None:
        self._asm_panel.set_program_text(DEFAULT_ASM_PROGRAM)
        self._asm_panel.set_status("loaded example program.")

    def _enter_asm_mode_if_needed(self) -> None:
        if self._mode == WidgetMode.ASM:
            return
        with contextlib.suppress(Exception):
            self._listener.stop()
        if self._bridge is None:
            self._bridge = CPUGPUBridge(gpu=self._gpu)
        self._mode = WidgetMode.ASM
        self._set_mode_label(t("mode.asm"), QColor(180, 220, 255))

    def _exit_asm_mode(self) -> None:
        if self._mode != WidgetMode.ASM:
            return
        self._asm_run_active = False
        self._mode = WidgetMode.LIVE
        self._set_mode_label(t("mode.live"), QColor(120, 220, 140))
        with contextlib.suppress(Exception):
            self._listener.start()

    def _assemble_or_warn(self, source: str):
        try:
            return assemble(source)
        except AssemblerError as exc:
            self._asm_panel.set_status(t("err.assemble", detail=str(exc)), error=True)
            self._tabs.setCurrentWidget(self._asm_panel.parent())
            return None

    def _asm_run(self, source: str) -> None:
        if not source.strip():
            self._asm_panel.set_status(t("err.empty_program"), error=True)
            return
        instructions = self._assemble_or_warn(source)
        if instructions is None:
            return
        self._enter_asm_mode_if_needed()
        if self._bridge is None:
            return
        self._bridge.load_program(instructions)
        self._reset_all_trace_views()
        self._cinema_view.set_program(source)
        self._asm_source_for_report = source
        self._asm_run_active = True
        self._asm_cycles_run = 0
        self._asm_seen_kwait = False
        self._asm_memory_writes = set()
        self._asm_panel.set_status(t("status.running", count=len(instructions)))
        self._tabs.setCurrentWidget(self._trace_table.parent())
        if self._achievement_tracker is not None:
            self._achievement_tracker.report_first_run()

    def _asm_run_with_source(self, source: str) -> None:
        """Triggered from a preset card — load into editor first then run."""
        self._asm_panel.set_program_text(source)
        self._asm_run(source)

    def _asm_load_into_editor(self, source: str) -> None:
        """Load a preset program into the editor without running it."""
        self._asm_panel.set_program_text(source)
        self._asm_panel.set_status(t("status.example_loaded", name="範例已載入"))
        self._tabs.setCurrentWidget(self._asm_panel.parent())

    def _asm_step_one(self, source: str) -> None:
        if self._mode != WidgetMode.ASM or self._bridge is None:
            instructions = self._assemble_or_warn(source)
            if instructions is None:
                return
            self._enter_asm_mode_if_needed()
            if self._bridge is None:
                return
            self._bridge.load_program(instructions)
            self._reset_all_trace_views()
        if self._bridge is None:
            return
        self._asm_run_active = False
        row = self._bridge.step()
        self._track_asm_row(row)
        self._append_to_all_trace_views(row)
        self._refresh_cpu_views(row)
        self._render_snapshot(self._gpu.snapshot())
        self._asm_panel.set_status(
            t("status.cycle_one", cycle=row.cycle, instruction=row.instruction_text),
            error=row.cpu_halted and not row.cpu_stalled,
        )

    def _asm_reset(self) -> None:
        if self._bridge is not None:
            self._bridge.reset()
        self._reset_all_trace_views()
        self._asm_run_active = False
        self._asm_cycles_run = 0
        self._asm_seen_kwait = False
        self._asm_memory_writes.clear()
        self._exit_asm_mode()
        self._asm_panel.set_status(t("status.reset"))

    def _advance_asm_run(self) -> None:
        if not self._asm_run_active or self._bridge is None:
            return
        cycles_this_tick = max(1, self._widget_config.kernels_per_tick)
        last_row = None
        for _ in range(cycles_this_tick):
            row = self._bridge.step()
            last_row = row
            self._track_asm_row(row)
            self._append_to_all_trace_views(row)
            self._asm_cycles_run += 1
            if row.cpu_halted and not row.cpu_stalled:
                self._asm_run_active = False
                self._asm_panel.set_status(
                    t("status.halted", cycles=self._asm_cycles_run)
                )
                play(SoundEffect.HALT)
                self._on_asm_run_completed()
                break
            if self._asm_cycles_run >= self._widget_config.asm_max_cycles:
                self._asm_run_active = False
                self._asm_panel.set_status(
                    t("status.max_cycles", limit=self._widget_config.asm_max_cycles),
                    error=True,
                )
                self._on_asm_run_completed()
                break
        if last_row is not None:
            self._refresh_cpu_views(last_row)
        snapshot = self._gpu.snapshot()
        self._render_snapshot(snapshot)
        self._notify_achievement_tracker_from_snapshot(
            snapshot, cycles_observed=self._asm_cycles_run
        )

    def _track_asm_row(self, row) -> None:
        """Inspect one TraceRow and update achievement-tracking state."""
        if self._achievement_tracker is None:
            return
        # KLAUNCH:OUT 0x40 出現
        for port, value in row.port_writes:
            if port == 0x40:
                self._achievement_tracker.report_klaunch()
                play(SoundEffect.KERNEL_DONE)
                # 第十一輪:粒子特效 + kernel 專屬 chord
                self._trigger_particles_on_kernel_launch()
                kernel_names = (
                    "vector_add", "interpolation", "hash", "texture_load",
                    "idle_compression", "app_launch", "page_nav",
                )
                play_kernel_chord(kernel_names[(value & 0xFF) % len(kernel_names)])
        # 任何進入 stalled 的 cycle 表示 KWAIT 啟動成功
        if row.cpu_stalled:
            self._asm_seen_kwait = True
        # 記憶體寫入(用 register_changes 之外的訊號:從 trace 拿不到,要從 bridge 重新取)
        if self._bridge is not None and self._bridge.memory_history:
            latest_memory = self._bridge.memory_history[-1]
            previous_memory = (
                self._bridge.memory_history[-2]
                if len(self._bridge.memory_history) >= 2
                else None
            )
            if previous_memory is not None:
                for address, (current, before) in enumerate(
                    zip(latest_memory, previous_memory, strict=False)
                ):
                    if current != before:
                        self._asm_memory_writes.add(address)

    def _on_asm_run_completed(self) -> None:
        """Called once when an asm run halts or hits the cycle cap."""
        if self._achievement_tracker is None or self._bridge is None:
            return
        if self._asm_seen_kwait:
            self._achievement_tracker.report_kwait_completed()
        self._achievement_tracker.report_memory_writes(len(self._asm_memory_writes))
        # 把最後狀態快照給 quiz 用
        self._last_asm_run_summary = {
            "final_register_value_r0": self._bridge.cpu.registers[0],
            "kernels_submitted": self._gpu.kernels_submitted,
            "kernels_completed": self._gpu.kernels_completed,
            "cycles_executed": self._asm_cycles_run,
        }

    def _refresh_cpu_views(self, last_row) -> None:
        """Push the latest bridge state into Debug and Heatmap views."""
        if self._bridge is None:
            return
        registers_history = self._bridge.register_history
        memory_history = self._bridge.memory_history
        sreg_history = self._bridge.sreg_history
        if not registers_history:
            return
        latest_registers = registers_history[-1]
        latest_memory = memory_history[-1]
        previous_registers = (
            registers_history[-2] if len(registers_history) >= 2 else None
        )
        previous_memory = memory_history[-2] if len(memory_history) >= 2 else None
        previous_sreg = sreg_history[-2] if len(sreg_history) >= 2 else None
        self._debug_view.update_state(
            cycle=last_row.cycle,
            pc=last_row.pc,
            instruction_text=last_row.instruction_text,
            sreg_text=last_row.sreg_text,
            registers=latest_registers,
            memory=latest_memory,
            previous_registers=previous_registers,
            previous_memory=previous_memory,
            previous_sreg_text=previous_sreg,
            cpu_halted=last_row.cpu_halted,
            cpu_stalled=last_row.cpu_stalled,
        )
        self._heatmap_view.update_history(
            register_history=registers_history,
            memory_history=memory_history,
            sreg_history=sreg_history,
            latest_pc=last_row.pc,
            latest_instruction=last_row.instruction_text,
        )

    def _set_mode_label(self, text: str, color: QColor) -> None:
        self._mode_label.setText(text)
        self._mode_label.setStyleSheet(
            f"color: rgba({color.red()},{color.green()},{color.blue()},230);"
            "font-weight: bold; font-size: 10px;"
        )

    # ------------------------------------------------------------------
    # 七輪新增:廣播 trace row 到所有相關的視圖 + 時光旅行 + 教學對話
    # ------------------------------------------------------------------
    def _reset_all_trace_views(self) -> None:
        """asm 載入新 program 時把所有相關面板一次性清空。"""
        self._trace_table.reset()
        self._debug_view.reset()
        self._heatmap_view.reset()
        self._commentary_panel.reset()
        self._sequence_view.reset()
        self._memory_map_view.reset()
        self._cinema_view.reset()

    def _append_to_all_trace_views(self, row) -> None:
        """asm 每跑一個 cycle 同步推進 trace 表 / 中文導讀 / 時序圖 / cinema。"""
        snapshot = self._gpu.snapshot()
        self._trace_table.append_row(row)
        self._commentary_panel.append_row(row)
        self._sequence_view.append_row(row, gpu_snapshot=snapshot)
        if self._bridge is not None and self._bridge.memory_history:
            latest = self._bridge.memory_history[-1]
            previous = (
                self._bridge.memory_history[-2]
                if len(self._bridge.memory_history) >= 2
                else None
            )
            self._memory_map_view.update_memory(latest, previous)
            sreg = (
                self._bridge.sreg_history[-1] if self._bridge.sreg_history else "----"
            )
            registers = self._bridge.register_history[-1]
            memory = self._bridge.memory_history[-1]
            self._cinema_view.append_one(
                trace_row=row,
                registers=registers,
                memory=memory,
                sreg=sreg,
                gpu_snapshot=snapshot,
                source_line_index=self._cinema_line_for_pc(row.pc),
            )

    def _cinema_line_for_pc(self, pc: int) -> int:
        """Best-effort PC → source-line 映射;失敗時回 -1。

        子集 CPU 的 program 是一連串 :class:`Instruction`,每個有
        ``line_number``;Tiny8 完整版的 program 是 ``(mnemonic, operands)``
        tuple,沒有 line number 直接拿,需另查 ``cpu.pc_to_line``。
        """
        if self._bridge is None:
            return -1
        cpu_obj = getattr(self._bridge, "cpu", None) or getattr(self._bridge, "_cpu", None)
        if cpu_obj is None:
            return -1
        program = getattr(cpu_obj, "program", None)
        if not program or not (0 <= pc < len(program)):
            return -1
        instr = program[pc]
        line_no = getattr(instr, "line_number", None)
        if line_no is not None:
            return max(0, int(line_no) - 1)
        pc_to_line = getattr(cpu_obj, "pc_to_line", None)
        if isinstance(pc_to_line, dict):
            mapped = pc_to_line.get(pc)
            if mapped is not None:
                return max(0, int(mapped) - 1)
        return -1

    def _on_trace_row_selected(self, cycle: int) -> None:
        """使用者點 Trace 表某一列 → Debug / Heatmap / Sequence 同步顯示那 cycle。"""
        if self._bridge is None:
            return
        history_index = max(0, cycle - 1)
        registers_history = self._bridge.register_history
        memory_history = self._bridge.memory_history
        if history_index >= len(registers_history):
            return
        registers = registers_history[history_index]
        memory = memory_history[history_index] if history_index < len(memory_history) else (
            tuple(0 for _ in range(256))
        )
        previous_registers = (
            registers_history[history_index - 1] if history_index >= 1 else None
        )
        previous_memory = (
            memory_history[history_index - 1]
            if history_index >= 1 and history_index - 1 < len(memory_history)
            else None
        )
        # find matching trace row to know instruction / sreg
        matching_row = None
        for row in self._bridge.trace:
            if row.cycle == cycle:
                matching_row = row
                break
        if matching_row is None:
            return
        self._debug_view.update_state(
            cycle=cycle,
            pc=matching_row.pc,
            instruction_text=matching_row.instruction_text,
            sreg_text=matching_row.sreg_text,
            registers=registers,
            memory=memory,
            previous_registers=previous_registers,
            previous_memory=previous_memory,
            previous_sreg_text=None,
            cpu_halted=matching_row.cpu_halted,
            cpu_stalled=matching_row.cpu_stalled,
        )
        self._memory_map_view.update_memory(memory, previous_memory)
        self._sequence_view.highlight_cycle(cycle)

    def _show_lesson_dialog(self) -> None:
        """打開 5 課中文教學導覽對話框。"""
        dialog = GuidedLessonDialog(LESSONS, self)
        dialog.lesson_selected.connect(self._on_lesson_selected)
        dialog.exec()

    def _on_lesson_selected(self, annotated_source: str, use_full_tiny8: bool) -> None:
        """從教學對話框收到的選擇:annotated_source 第一行是 'RUN' / 'LOAD'。"""
        marker, _, source = annotated_source.partition("\n")
        marker = marker.strip().upper()
        if use_full_tiny8:
            self._full_asm_panel.set_program_text(source)
            if marker == "RUN":
                self._full_run(source)
            else:
                self._tabs.setCurrentWidget(self._full_asm_panel.parent())
        else:
            self._asm_panel.set_program_text(source)
            if marker == "RUN":
                self._asm_run(source)
            else:
                self._tabs.setCurrentWidget(self._asm_panel.parent())

    # ------------------------------------------------------------------
    # Full Tiny8 ↔ GPU integration mode
    # ------------------------------------------------------------------
    def _full_load_example(self) -> None:
        self._full_asm_panel.set_program_text(_DEFAULT_FULL_ASM_PROGRAM)
        self._full_asm_panel.set_status("已載入完整版 Tiny8 整合範例。")

    def _enter_full_mode_if_needed(self) -> None:
        if self._mode == WidgetMode.FULL_ASM:
            return
        with contextlib.suppress(Exception):
            self._listener.stop()
        if self._full_bridge is None:
            self._full_bridge = FullCPUGPUBridge(gpu=self._gpu)
        self._mode = WidgetMode.FULL_ASM
        self._set_mode_label("● Tiny8 完整版", QColor(255, 200, 100))

    def _exit_full_mode(self) -> None:
        if self._mode != WidgetMode.FULL_ASM:
            return
        self._full_run_active = False
        self._mode = WidgetMode.LIVE
        self._set_mode_label(t("mode.live"), QColor(120, 220, 140))
        with contextlib.suppress(Exception):
            self._listener.start()

    def _full_load_source(self, source: str) -> bool:
        if not source.strip():
            self._full_asm_panel.set_status(t("err.empty_program"), error=True)
            return False
        self._enter_full_mode_if_needed()
        if self._full_bridge is None:
            return False
        try:
            self._full_bridge.load_source(source)
        except Exception as exc:
            # Tiny8 的 assembler 會丟自己的 ValueError;統一包成中文訊息
            self._full_asm_panel.set_status(
                t("err.assemble", detail=str(exc)), error=True
            )
            return False
        self._full_previous_registers = tuple(self._full_bridge.cpu.regs)
        self._full_previous_memory = tuple(
            self._full_bridge.cpu.read_ram(addr) for addr in range(256)
        )
        self._tiny8_full_view.reset()
        return True

    def _full_run(self, source: str) -> None:
        if not self._full_load_source(source):
            return
        self._full_run_active = True
        self._full_steps_run = 0
        self._full_asm_panel.set_status(
            "完整 Tiny8 執行中…按重置可以中止。"
        )

    def _full_step_one(self, source: str) -> None:
        needs_load = (
            self._mode != WidgetMode.FULL_ASM or self._full_bridge is None
        )
        if needs_load and not self._full_load_source(source):
            return
        if self._full_bridge is None:
            return
        self._full_run_active = False
        row = self._full_bridge.step()
        self._refresh_full_view(row)
        self._render_snapshot(self._gpu.snapshot())
        self._full_asm_panel.set_status(
            f"step {row.step}  ·  {row.instruction_text}",
            error=row.cpu_halted and not row.cpu_stalled,
        )

    def _full_reset(self) -> None:
        if self._full_bridge is not None:
            self._full_bridge.reset()
        self._tiny8_full_view.reset()
        self._full_run_active = False
        self._full_steps_run = 0
        self._full_previous_registers = None
        self._full_previous_memory = None
        self._exit_full_mode()
        self._full_asm_panel.set_status("已重置,回到即時模式。")

    def _advance_full_run(self) -> None:
        if not self._full_run_active or self._full_bridge is None:
            return
        steps_this_tick = max(1, self._widget_config.kernels_per_tick)
        last_row = None
        for _ in range(steps_this_tick):
            row = self._full_bridge.step()
            last_row = row
            self._full_steps_run += 1
            if row.cpu_halted and not row.cpu_stalled:
                self._full_run_active = False
                self._full_asm_panel.set_status(
                    f"完整 Tiny8 已停止,共執行 {self._full_steps_run} 個 step。"
                )
                play(SoundEffect.HALT)
                break
            if self._full_steps_run >= self._widget_config.asm_max_cycles:
                self._full_run_active = False
                self._full_asm_panel.set_status(
                    t("status.max_cycles", limit=self._widget_config.asm_max_cycles),
                    error=True,
                )
                break
        if last_row is not None:
            self._refresh_full_view(last_row)
            for port, _value in last_row.port_writes:
                if port == 0x40:
                    play(SoundEffect.KERNEL_DONE)
                    if self._achievement_tracker is not None:
                        self._achievement_tracker.report_klaunch()
                if port == 0xFF and self._achievement_tracker is not None:
                    self._achievement_tracker.report_kwait_completed()
        self._render_snapshot(self._gpu.snapshot())

    def _refresh_full_view(self, last_row) -> None:
        if self._full_bridge is None:
            return
        registers = tuple(self._full_bridge.cpu.regs)
        memory = tuple(self._full_bridge.cpu.read_ram(addr) for addr in range(256))
        kernel_dispatched = any(port == 0x40 for port, _ in last_row.port_writes)
        self._tiny8_full_view.update_state(
            step=last_row.step,
            pc=last_row.pc,
            instruction_text=last_row.instruction_text,
            sreg_text=last_row.sreg_text,
            registers=registers,
            memory=memory,
            previous_registers=self._full_previous_registers,
            previous_memory=self._full_previous_memory,
            cpu_halted=last_row.cpu_halted,
            cpu_stalled=last_row.cpu_stalled,
            kernel_dispatched=kernel_dispatched,
            gpu_snapshot=self._gpu.snapshot(),
        )
        self._full_previous_registers = registers
        self._full_previous_memory = memory

    # (第 23 輪砍掉:_export_session — 對應 📚 歷史分頁的匯出功能)

    # ------------------------------------------------------------------
    # infrastructure helpers
    # ------------------------------------------------------------------
    def _try_open_session_store(self) -> SessionStore | None:
        try:
            return SessionStore(_default_db_path(self._app_config))
        except PersistenceError as exc:
            print(f"[gpu_simulator] persistence disabled: {exc}")
            return None

    def _try_open_achievement_store(self) -> AchievementStore | None:
        try:
            return AchievementStore(_default_db_path(self._app_config))
        except PersistenceError as exc:
            print(f"[gpu_simulator] achievements disabled: {exc}")
            return None

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _show_info(self, title: str, message: str) -> None:
        manager = getattr(self, "_toast_manager", None)
        if manager is None:
            QMessageBox.information(self, title, message)
            return
        try:
            manager.show(ToastSpec(title=title, body=message, level=ToastLevel.INFO))
        except Exception:
            QMessageBox.information(self, title, message)

    def _show_toast(
        self,
        title: str,
        message: str = "",
        level: ToastLevel = ToastLevel.INFO,
    ) -> None:
        manager = getattr(self, "_toast_manager", None)
        if manager is None:
            return
        with contextlib.suppress(Exception):
            manager.show(ToastSpec(title=title, body=message, level=level))

    # ------------------------------------------------------------------
    # welcome dialog
    # ------------------------------------------------------------------
    def _maybe_show_welcome_dialog(self) -> None:
        if self._widget_config.skip_welcome_dialog:
            return
        try:
            already_welcomed = _welcome_marker_path().exists()
        except Exception:
            already_welcomed = False
        if already_welcomed:
            return
        self._show_welcome_dialog(force=False)

    def _show_welcome_dialog(self, *, force: bool) -> None:
        dialog = WelcomeDialog(self)
        dialog.exec()
        if dialog.should_skip_next_time or not force:
            try:
                marker = _welcome_marker_path()
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(
                    datetime.now(tz=timezone.utc).isoformat(), encoding="utf-8"
                )
            except OSError:
                pass

    # ------------------------------------------------------------------
    # trophy room + achievement notifications
    # ------------------------------------------------------------------
    def _show_trophy_room(self) -> None:
        if self._achievement_store is None:
            self._show_info(t("btn.trophy_room"), "成就系統暫時無法使用。")
            return
        try:
            unlocked = self._achievement_store.all_unlocked()
        except PersistenceError as exc:
            self._show_error(t("btn.trophy_room"), str(exc))
            return
        TrophyRoomDialog(unlocked, self).exec()

    def _on_achievement_unlocked(self, achievement: Achievement) -> None:
        play(SoundEffect.ACHIEVEMENT)
        try:
            toast = AchievementToast(achievement, self)
            toast.move(self.x() + 12, self.y() + 12)
            toast.show()
        except Exception:
            pass
        # 第十一輪:更新寵物進化階段 + 粒子煙火 + TTS 報告
        if self._achievement_store is not None:
            unlocked_count = len(self._achievement_store.all_unlocked())
            with contextlib.suppress(Exception):
                self._pet_widget.set_achievement_count(unlocked_count)
        self._trigger_particles_on_kernel_done()
        self._speak_if_enabled(f"成就解鎖 — {achievement.name}")

    # ------------------------------------------------------------------
    # quiz
    # ------------------------------------------------------------------
    def _show_quiz(self) -> None:
        dynamic_questions: list = []
        if self._last_asm_run_summary is not None:
            dynamic_questions = build_dynamic_questions(**self._last_asm_run_summary)
        else:
            self._show_info(t("btn.start_quiz"), t("quiz.no_session"))
            return
        questions = build_quiz(dynamic_questions=dynamic_questions)
        dialog = QuizDialog(questions, self)
        dialog.exec()
        if (
            dialog.score == dialog.total
            and dialog.total > 0
            and self._achievement_tracker is not None
        ):
            self._achievement_tracker.report_quiz_perfect()
            play(SoundEffect.QUIZ_CORRECT)

    # ------------------------------------------------------------------
    # GIF recorder
    # ------------------------------------------------------------------
    def _toggle_recorder(self) -> None:
        if self._recorder is not None and self._recorder.is_recording:
            self._stop_recorder()
        else:
            self._start_recorder()

    def _start_recorder(self) -> None:
        output_dir = user_config_dir() / "recordings"
        try:
            self._recorder = GIFRecorder(self, output_dir)
            self._recorder.start()
        except Exception as exc:
            self._show_error("錄影", str(exc))
            return
        self._record_button.setText(t("btn.record_stop"))
        self._record_button.setToolTip(t("tooltip.record_stop"))
        self._recorder_status_timer.start()
        if self._achievement_tracker is not None:
            self._achievement_tracker.report_recorder_used()

    def _stop_recorder(self) -> None:
        self._recorder_status_timer.stop()
        if self._recorder is None:
            return
        try:
            output_path = self._recorder.stop()
        except RecorderError as exc:
            self._show_error("錄影", str(exc))
            self._recorder = None
            self._record_button.setText(t("btn.record_start"))
            return
        self._record_button.setText(t("btn.record_start"))
        self._record_button.setToolTip(t("tooltip.record_start"))
        self._recorder = None
        if output_path is not None:
            self._show_info("錄影", t("status.recording_saved", path=output_path))

    def _refresh_recorder_status(self) -> None:
        if self._recorder is None or not self._recorder.is_recording:
            return
        seconds = int(self._recorder.elapsed_seconds)
        self._record_button.setText(t("status.recording", seconds=seconds))

    # ------------------------------------------------------------------
    # easy-mode automatic demo rotation
    # ------------------------------------------------------------------
    def _easy_demo_start(self) -> None:
        self._easy_demo_load_current()
        self._easy_demo_timer.start()
        self._easy_countdown_timer.start()

    def _easy_demo_load_current(self) -> None:
        if not EASY_MODE_DEMOS:
            return
        filename = EASY_MODE_DEMOS[self._easy_demo_index % len(EASY_MODE_DEMOS)]
        path = _examples_dir() / filename
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            return
        nice_name = filename.replace(".asm", "")
        self._easy_seconds_remaining = self._widget_config.easy_mode_demo_seconds
        self._demo_tab.update_state(
            current_name=nice_name,
            seconds_remaining=self._easy_seconds_remaining,
        )
        self._asm_run(source)

    def _easy_demo_next(self) -> None:
        self._easy_demo_index += 1
        self._easy_demo_load_current()

    def _easy_demo_tick_countdown(self) -> None:
        self._easy_seconds_remaining = max(0, self._easy_seconds_remaining - 1)
        filename = EASY_MODE_DEMOS[self._easy_demo_index % len(EASY_MODE_DEMOS)]
        self._demo_tab.update_state(
            current_name=filename.replace(".asm", ""),
            seconds_remaining=self._easy_seconds_remaining,
        )

    # ==================================================================
    # 第九輪新功能的 handlers(全部放在 cleanup 之前)
    # ==================================================================

    # (第 23 輪砍掉:Conway's Life 遊戲機 — 6 個 _life_* methods)

    # ---- Divergence 視圖 --------------------------------------------
    def _refresh_divergence_view(self) -> None:
        divergence_preset = self._divergence_presets[self._divergence_index]
        coalescing_preset = self._coalescing_presets[self._coalescing_index]
        divergence_analysis = analyze_branch(divergence_preset.branch_decisions)
        coalescing_analysis = analyze_memory_access(coalescing_preset.addresses)
        self._divergence_view.set_divergence_pattern(divergence_preset.branch_decisions)
        self._divergence_view.set_coalescing_pattern(coalescing_preset.addresses)
        summary_text = (
            f"分支:{divergence_preset.chinese_description} | "
            f"存取:{coalescing_preset.chinese_description} | "
            f"{divergence_summary(divergence_analysis, coalescing_analysis)}"
        )
        self._divergence_view.set_summary(summary_text)

    # ---- AI 解釋 -----------------------------------------------------
    def _show_ai_explainer(self) -> None:
        if self._bridge is None:
            self._show_info("AI 解釋", "請先在 ASM 編輯器跑一支程式。")
            return
        trace_text = summarize_trace(self._bridge.trace)
        registers_text = summarize_registers(list(self._bridge.cpu.registers))
        request = ExplainRequest(
            asm_source=self._asm_source_for_report or self._asm_panel.program_text(),
            trace_summary=trace_text,
            final_register_summary=registers_text,
            kernels_submitted=self._gpu.kernels_submitted,
            kernels_completed=self._gpu.kernels_completed,
        )
        available, reason = ai_is_available()
        if not available:
            self._show_info(
                "AI 未啟用",
                f"{reason}\n\n仍會顯示「離線模式」中文導讀。",
            )
        explainer = Explainer()
        response = explainer.explain(request)
        AIExplainerDialog(response.text, response.used_ai, self).exec()

    # ---- 每日挑戰 ---------------------------------------------------
    def _show_daily_challenge(self) -> None:
        challenge = daily_challenge()
        store = self._ensure_leaderboard_store()
        leaderboard = store.top_for(challenge.code) if store else []
        result = None
        if self._bridge is not None and self._bridge.trace:
            memory_writes_addrs = self._asm_memory_writes
            result = score_attempt(
                challenge,
                trace_rows=list(self._bridge.trace),
                kernels_submitted=self._gpu.kernels_submitted,
                memory_writes=memory_writes_addrs,
            )
            self._latest_challenge_result = result
        dialog = ChallengeDialog(challenge, result, leaderboard, parent=self)
        dialog.submit_score_requested.connect(
            lambda nickname: self._submit_challenge_score(challenge, result, nickname)
        )
        dialog.exec()

    def _submit_challenge_score(self, challenge, result, nickname: str) -> None:
        if result is None or not result.passed:
            return
        store = self._ensure_leaderboard_store()
        if store is None:
            return
        try:
            store.record(
                challenge_code=challenge.code,
                nickname=nickname,
                cycles_used=result.cycles_used,
                score=result.score,
            )
            self._show_info("提交成功", f"{nickname} 的分數 {result.score} 已上榜!")
        except PersistenceError as exc:
            self._show_error("提交失敗", str(exc))

    def _ensure_leaderboard_store(self) -> LeaderboardStore | None:
        if self._leaderboard_store is None:
            try:
                self._leaderboard_store = LeaderboardStore(
                    _default_db_path(self._app_config)
                )
            except PersistenceError as exc:
                print(f"[gpu_simulator] leaderboard disabled: {exc}")
                return None
        return self._leaderboard_store

    # ---- 實驗報告 ---------------------------------------------------
    def _generate_lab_report(self) -> None:
        if self._bridge is None or not self._bridge.trace:
            self._show_info("實驗報告", "請先在 ASM 編輯器跑一支程式。")
            return
        output_dir = user_config_dir() / "lab_reports"
        try:
            result = generate_report(
                title=self._asm_panel._editor.objectName() or "ASM run",
                asm_source=self._asm_source_for_report or self._asm_panel.program_text(),
                trace_rows=list(self._bridge.trace),
                register_history=list(self._bridge.register_history),
                memory_history=list(self._bridge.memory_history),
                sreg_history=list(self._bridge.sreg_history),
                final_registers=list(self._bridge.cpu.registers),
                final_memory=list(self._bridge.cpu.memory),
                kernels_submitted=self._gpu.kernels_submitted,
                kernels_completed=self._gpu.kernels_completed,
                output_dir=output_dir,
            )
        except Exception as exc:
            self._show_error("實驗報告", f"產出失敗:{exc}")
            return
        self._show_info(
            "實驗報告產生完成",
            f"已寫入:\n{result.markdown_path}\n附帶 {len(result.image_paths)} 張圖。",
        )

    # ---- 主題 ------------------------------------------------------
    # ==================================================================
    # 第十一輪:粒子 / 雨 / 電影 / TTS handlers
    # ==================================================================
    def _setup_visual_overlays(self) -> None:
        """主視窗 widget 已就緒後,建立粒子 + 雨 overlay,並把雨壓在最底。

        **輕量模式(lite_mode)會完全跳過粒子+字元雨**,讓 4 核以下機器也能跑。
        這兩個 overlay 各自有 30 FPS 的 QTimer 在跑 paintEvent,是最大的效能殺手。
        """
        lite = getattr(self._widget_config, "lite_mode", False)
        if not lite:
            try:
                self._code_rain_overlay = build_code_rain_overlay(self)
                self._code_rain_overlay.lower()
                self._code_rain_overlay.show()
            except Exception:
                self._code_rain_overlay = None
            try:
                self._particle_overlay = build_particle_overlay(self)
                self._particle_overlay.raise_()
                self._particle_overlay.show()
            except Exception:
                self._particle_overlay = None
        else:
            # 輕量模式直接設成 None,後面所有用 overlay 的地方都會檢查並 noop
            self._code_rain_overlay = None
            self._particle_overlay = None
        # cinema 字幕(浮在最上層)
        self._cinema_caption_label = QLabel("", self)
        self._cinema_caption_label.setStyleSheet(
            "background: rgba(0, 0, 0, 200); color: rgb(255, 220, 130);"
            "font-size: 14px; font-weight: bold; padding: 8px 14px;"
            "border: 2px solid rgba(255, 220, 130, 200); border-radius: 6px;"
        )
        self._cinema_caption_label.setAlignment(Qt.AlignCenter)
        self._cinema_caption_label.hide()

        # 第十二輪:toast 管理員 + easter egg detector + status bar refresh timer
        self._toast_manager = ToastManager(self)
        self._easter_eggs = EasterEggDetector()
        self._easter_egg_handlers = make_default_handlers(
            on_konami=lambda: self._on_easter_egg_konami(),
            on_matrix=lambda: self._on_easter_egg_matrix(),
            on_dragon=lambda: self._on_easter_egg_dragon(),
            on_rainbow=lambda: self._on_easter_egg_rainbow(),
            on_firework=lambda: self._trigger_particles_on_kernel_done(),
        )
        self._kernel_launch_count = 0
        self._status_refresh_timer = QTimer(self)
        # 輕量模式把狀態列從 1s 延長到 3s,降低重繪頻率
        self._status_refresh_timer.setInterval(3000 if lite else 1000)
        self._status_refresh_timer.timeout.connect(self._refresh_status_bar)
        self._status_refresh_timer.start()
        self._setup_global_shortcuts()

    def resizeEvent(self, event) -> None:  # noqa: N802
        """重設兩個 overlay 的大小 + 重新對齊 cinema 字幕。"""
        super().resizeEvent(event)
        if self._code_rain_overlay is not None:
            self._code_rain_overlay.resize(self.size())
        if self._particle_overlay is not None:
            self._particle_overlay.resize(self.size())
        if self._cinema_caption_label is not None:
            caption_width = min(self.width() - 40, 540)
            self._cinema_caption_label.setFixedWidth(caption_width)
            self._cinema_caption_label.adjustSize()
            self._cinema_caption_label.move(
                (self.width() - self._cinema_caption_label.width()) // 2,
                self.height() // 4,
            )

    # ---- 粒子 ------------------------------------------------------
    def _trigger_particles_on_kernel_launch(self) -> None:
        """每次 KLAUNCH 發生時呼叫;從畫面中央往右上方噴粒子。"""
        self._kernel_launch_count = getattr(self, "_kernel_launch_count", 0) + 1
        # 把今天的負載寫進 mood log(每次 launch 都更新一次)
        self._record_today_mood_from_snapshot()
        if self._particle_overlay is None:
            return
        with contextlib.suppress(Exception):
            self._particle_overlay.emit_launch(
                origin_x=self.width() * 0.30,
                origin_y=self.height() * 0.45,
                target_x=self.width() * 0.75,
                target_y=self.height() * 0.30,
                count=18,
            )

    def _trigger_particles_on_kernel_done(self) -> None:
        """Kernel 完成時呼叫煙火。"""
        if self._particle_overlay is None:
            return
        with contextlib.suppress(Exception):
            self._particle_overlay.emit_firework(
                center_x=self.width() * 0.75,
                center_y=self.height() * 0.30,
                count=24,
            )

    # ---- TTS -------------------------------------------------------
    def _toggle_tts(self) -> None:
        available, reason = tts_is_available()
        if not available:
            self._show_info("TTS 不可用", reason)
            return
        self._tts_enabled = not self._tts_enabled
        if self._tts_enabled:
            self._tts_button.setText("🗣️ TTS 開")
            tts_speak("TTS 已開啟,現在會把寵物說的話念出來。")
        else:
            self._tts_button.setText("🗣️ TTS")

    def _speak_if_enabled(self, text: str) -> None:
        if self._tts_enabled:
            tts_speak(text)

    # ---- Cinema mode ------------------------------------------------
    def _start_cinema_mode(self) -> None:
        """跑 60 秒快速 showcase 劇本(適合錄展示影片)。"""
        self._start_scripted_mode(builtin_60_second_script(), name="電影模式")

    def _start_tutorial_mode(self) -> None:
        """跑 10 分鐘詳細導覽 — 給零程式基礎觀眾用,每個概念都會停留讀字幕。"""
        from gpu_simulator.cinematic import builtin_10_minute_tutorial_script

        self._start_scripted_mode(
            builtin_10_minute_tutorial_script(), name="10 分鐘導覽"
        )

    def _start_scripted_mode(self, script, name: str = "電影模式") -> None:
        if self._cinema_timer is not None and self._cinema_timer.isActive():
            self._show_info(name, f"已經在播了({name}),等播完或關掉再試。")
            return
        self._cinema_player = CinemaPlayer(script, on_action=self._handle_cinema_action)
        self._cinema_timer = QTimer(self)
        self._cinema_timer.timeout.connect(self._cinema_advance)
        # 立即跑第一個 action
        self._cinema_advance()

    def _cinema_advance(self) -> None:
        if self._cinema_player is None or self._cinema_timer is None:
            return
        if self._cinema_player.is_finished:
            self._cinema_timer.stop()
            if self._cinema_caption_label is not None:
                self._cinema_caption_label.hide()
            self._cinema_player = None
            self._cinema_timer = None
            return
        action = self._cinema_player.advance()
        if action is None:
            return
        # 排下個 action 的時間
        self._cinema_timer.start(max(200, action.duration_ms))

    def _handle_cinema_action(self, action) -> None:
        kind = action.kind
        payload = action.payload
        if kind is CinemaActionKind.SHOW_CAPTION:
            text = payload.get("text", "")
            if self._cinema_caption_label is not None:
                self._cinema_caption_label.setText(text)
                caption_width = min(self.width() - 40, 540)
                self._cinema_caption_label.setFixedWidth(caption_width)
                self._cinema_caption_label.adjustSize()
                self._cinema_caption_label.move(
                    (self.width() - self._cinema_caption_label.width()) // 2,
                    self.height() // 4,
                )
                self._cinema_caption_label.show()
                self._cinema_caption_label.raise_()
            self._speak_if_enabled(text)
        elif kind is CinemaActionKind.SWITCH_TAB:
            tab_name = payload.get("tab", "")
            for index in range(self._tabs.count()):
                if tab_name in self._tabs.tabText(index):
                    self._tabs.setCurrentIndex(index)
                    break
        elif kind is CinemaActionKind.LOAD_AND_RUN_ASM:
            asm = payload.get("asm", "")
            if asm:
                self._asm_panel.set_program_text(asm)
                self._asm_run(asm)
        elif kind is CinemaActionKind.PARTICLE_BURST:
            burst_kind = payload.get("kind", "firework")
            if burst_kind == "firework":
                self._trigger_particles_on_kernel_done()
            else:
                self._trigger_particles_on_kernel_launch()
        elif kind is CinemaActionKind.DONE:
            if self._cinema_caption_label is not None:
                self._cinema_caption_label.hide()

    def _cycle_theme(self) -> None:
        self._current_theme_index = (self._current_theme_index + 1) % len(ALL_THEMES)
        theme = ALL_THEMES[self._current_theme_index]
        apply_theme(self, theme.code)
        self._theme_button.setText(f"🎨 {theme.name}")

    # ---- 效能分析 -----------------------------------------------------
    def _show_profiler(self) -> None:
        if self._bridge is None or not self._bridge.trace:
            self._show_info("效能分析", "請先在 ASM 編輯器跑一支程式。")
            return
        profile = profile_session(
            list(self._bridge.trace),
            sm_count=self._app_config.gpu.num_sms,
            warps_per_sm=self._app_config.gpu.warps_per_sm,
        )
        lines: list[str] = []
        lines.append("📈 效能分析報告")
        lines.append(f"總 cycle:{profile.total_cycles}")
        lines.append(f"提交 kernel:{profile.total_kernels}")
        lines.append(f"被 KWAIT 卡住:{profile.stalled_cycles} cycle")
        lines.append(f"平均佔用率:{profile.avg_occupancy * 100:.1f}%")
        lines.append(f"IPC(busy/total):{profile.instructions_per_cycle:.2f}")
        lines.append("")
        lines.append("Per-kernel 細節:")
        for stat in profile.kernel_stats:
            lines.append(
                f"  {stat.kernel_name:18s}  "
                f"次數={stat.submissions:>3}  "
                f"預估 cycles={stat.estimated_cycles:>5}  "
                f"OI={stat.operational_intensity:.4f}"
            )
        self._show_info("效能分析", "\n".join(lines))

    # ---- Web 鏡像 ---------------------------------------------------
    def _toggle_web_mirror(self) -> None:
        if self._mirror_server is not None and self._mirror_server.is_running:
            self._mirror_server.stop()
            self._mirror_server = None
            self._mirror_button.setText("🌐 開啟 Web 鏡像")
            return
        try:
            self._mirror_server = MirrorServer(self._mirror_publisher)
            self._mirror_server.start()
        except Exception as exc:
            self._show_error("Web 鏡像", f"啟動失敗:{exc}")
            self._mirror_server = None
            return
        self._mirror_button.setText("🛑 停止 Web 鏡像")
        self._show_info(
            "Web 鏡像已啟動",
            f"瀏覽器打開 {self._mirror_server.url} 即可看 GPU 即時狀態。",
        )

    # ------------------------------------------------------------------
    # 第十二輪:狀態列 / 彩蛋 / 快捷鍵 / 命令面板 / 心情日記
    # ------------------------------------------------------------------
    def _refresh_status_bar(self) -> None:
        """每秒更新底部狀態列 — 顯示版本、模式、kernel 數、利用率、FPS 估計。"""
        try:
            from gpu_simulator import __version__ as version
        except Exception:
            version = "0.10.0"
        util_pct = 0.0
        with contextlib.suppress(Exception):
            snap = self._gpu.snapshot()
            util_pct = float(snap.get("overall_utilization", 0.0)) * 100.0
        mode = "電影模式" if getattr(self, "_cinema_player", None) is not None else "即時"
        if getattr(self._widget_config, "lite_mode", False):
            mode = f"輕量 · {mode}"
        fps = float(1000.0 / max(1, self._widget_config.tick_interval_ms))
        snapshot = StatusSnapshot(
            version=version,
            mode=mode,
            kernels=self._kernel_launch_count,
            utilization_percent=util_pct,
            fps=fps,
        )
        frame = getattr(self, "_status_bar_frame", None)
        if frame is not None:
            update_status_bar(frame, snapshot)

    def _setup_global_shortcuts(self) -> None:
        """Ctrl+Shift+P 命令面板、Ctrl+/ 快捷鍵清單、F1 說明等。"""
        shortcuts = [
            ("Ctrl+Shift+P", self._open_command_palette),
            ("Ctrl+/", self._show_shortcuts_help),
            ("F1", self._show_shortcuts_help),
            ("Ctrl+R", lambda: self._show_toast("Ctrl+R", "切到 ASM 分頁手動跑", ToastLevel.INFO)),
            ("Ctrl+M", self._open_mood_calendar_dialog),
            ("Ctrl+Shift+E", self._prompt_pet_rename),
            ("Ctrl+Shift+T", self._toggle_tts),
        ]
        self._shortcuts: list = []
        for keyseq, callback in shortcuts:
            sc = QShortcut(QKeySequence(keyseq), self)
            sc.activated.connect(callback)
            self._shortcuts.append(sc)

    def _show_shortcuts_help(self) -> None:
        lines = [
            "Ctrl+Shift+P   命令面板",
            "Ctrl+/  / F1   開這份說明",
            "Ctrl+M         開心情日記",
            "Ctrl+Shift+E   幫寵物改名",
            "Ctrl+Shift+T   切 TTS 旁白",
        ]
        self._show_toast("⌨️ 鍵盤快捷鍵", "\n".join(lines), ToastLevel.INFO)

    def _build_palette_commands(self) -> list[Command]:
        cmds: list[Command] = [
            Command(
                id="cinema",
                title="🎬 電影模式(60 秒快速版)",
                description="60 秒劇本式自動展示,適合錄影",
                run=self._start_cinema_mode,
                keywords=("cinema", "demo", "showcase", "電影"),
            ),
            Command(
                id="tutorial",
                title="📖 10 分鐘詳細導覽(教學版)",
                description="零程式基礎也能跟著看,逐個概念講解",
                run=self._start_tutorial_mode,
                keywords=("tutorial", "guide", "教學", "導覽"),
            ),
            Command(
                id="tts",
                title="🗣️ 切換 TTS 旁白",
                description="開關中文語音說明",
                run=self._toggle_tts,
                keywords=("tts", "voice", "speech"),
                shortcut="Ctrl+Shift+T",
            ),
            Command(
                id="mood",
                title="📅 心情日記",
                description="看最近 12 週 GPU 心情熱圖",
                run=self._open_mood_calendar_dialog,
                keywords=("mood", "diary", "calendar"),
                shortcut="Ctrl+M",
            ),
            Command(
                id="rename_pet",
                title="🐱 幫寵物改名",
                description="輸入新名字",
                run=self._prompt_pet_rename,
                keywords=("pet", "name", "rename"),
                shortcut="Ctrl+Shift+E",
            ),
            Command(
                id="firework",
                title="🎆 來個煙火",
                description="放一發粒子煙火慶祝",
                run=self._trigger_particles_on_kernel_done,
                keywords=("firework", "particle", "burst"),
            ),
            Command(
                id="shortcuts",
                title="⌨️ 看快捷鍵清單",
                description="所有 Ctrl 組合鍵",
                run=self._show_shortcuts_help,
                keywords=("shortcut", "help", "keys"),
                shortcut="F1",
            ),
        ]
        return cmds

    def _open_command_palette(self) -> None:
        with contextlib.suppress(Exception):
            open_palette(self, self._build_palette_commands())

    def _open_mood_calendar_dialog(self) -> None:
        """彈一個簡單的 dialog 顯示 mood calendar。"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        try:
            log = self._get_mood_log()
        except Exception as exc:
            self._show_toast("心情日記", f"開不起來:{exc}", ToastLevel.ERROR)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("📅 GPU 心情日記")
        dialog.resize(700, 360)
        layout = QVBoxLayout(dialog)
        widget = build_mood_calendar_widget(dialog, log, weeks=12)
        layout.addWidget(widget)
        dialog.exec()

    def _get_mood_log(self) -> MoodLog:
        log = getattr(self, "_mood_log", None)
        if log is not None:
            return log
        db_path = user_config_dir() / "mood_log.db"
        self._mood_log = MoodLog(db_path)
        return self._mood_log

    def _record_today_mood_from_snapshot(self) -> None:
        """ widget tick 結束時呼一下,把今天的負載寫進 mood log。"""
        with contextlib.suppress(Exception):
            from datetime import date as _date
            snap = self._gpu.snapshot()
            avg = float(snap.get("overall_utilization", 0.0)) * 100.0
            log = self._get_mood_log()
            today_record = log.get(_date.today())
            peak = avg
            if today_record is not None:
                peak = max(today_record.peak_utilization, avg)
                # 平均 = 移動平均(粗略)
                avg = (today_record.average_utilization * 0.9) + (avg * 0.1)
                kernel_count = today_record.kernel_count
            else:
                kernel_count = 0
            kernel_count = max(kernel_count, self._kernel_launch_count)
            log.record(
                DayMood(
                    day=_date.today(),
                    average_utilization=avg,
                    peak_utilization=peak,
                    kernel_count=kernel_count,
                )
            )

    def _prompt_pet_rename(self) -> None:
        current = ""
        with contextlib.suppress(Exception):
            current = self._pet_widget.pet_name
        new_name, ok = QInputDialog.getText(
            self, "🐱 幫寵物取個名字", "新名字(1–12 字):", text=current
        )
        if not ok:
            return
        with contextlib.suppress(Exception):
            self._pet_widget.set_name(new_name)
            self._show_toast(
                "改名成功",
                f"從現在起叫他 {self._pet_widget.pet_name}!",
                ToastLevel.SUCCESS,
            )

    # ------------------------------------------------------------------
    # 彩蛋 callbacks
    # ------------------------------------------------------------------
    def _on_easter_egg_konami(self) -> None:
        self._show_toast(
            "🎮 KONAMI!", "你發現了開發者彩蛋!", ToastLevel.SUCCESS
        )
        for _ in range(3):
            self._trigger_particles_on_kernel_done()

    def _on_easter_egg_matrix(self) -> None:
        self._show_toast("🟢 Matrix mode", "進入駭客客模式…", ToastLevel.INFO)
        with contextlib.suppress(Exception):
            apply_theme(QApplication.instance(), "Matrix")

    def _on_easter_egg_dragon(self) -> None:
        self._show_toast("🐲 龍!", "寵物直接進化到龍階段", ToastLevel.SUCCESS)
        with contextlib.suppress(Exception):
            self._pet_widget.set_achievement_count(99)

    def _on_easter_egg_rainbow(self) -> None:
        self._show_toast("🌈 RAINBOW", "彩虹爆發!", ToastLevel.SUCCESS)
        for _ in range(5):
            self._trigger_particles_on_kernel_done()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """順手把鍵盤事件也餵進 easter egg detector。"""
        try:
            text = event.text()
            key = event.key()
            label = qt_key_to_label(key, text)
            if label is not None:
                trigger = self._easter_eggs.feed_key(label)
                eegg_dispatch(trigger, self._easter_egg_handlers)
            if text:
                for ch in text:
                    trigger = self._easter_eggs.feed_char(ch)
                    eegg_dispatch(trigger, self._easter_egg_handlers)
        except Exception:
            pass
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        for timer in (
            getattr(self, "_timer", None),
            getattr(self, "_real_gpu_timer", None),
            getattr(self, "_easy_demo_timer", None),
            getattr(self, "_easy_countdown_timer", None),
            getattr(self, "_recorder_status_timer", None),
        ):
            if timer is not None:
                with contextlib.suppress(Exception):
                    timer.stop()
        with contextlib.suppress(Exception):
            self._listener.stop()
        if self._recorder is not None and self._recorder.is_recording:
            with contextlib.suppress(Exception):
                self._recorder.stop()
        if self._session_store is not None and self._session_id is not None:
            with contextlib.suppress(PersistenceError):
                self._session_store.end_session(
                    self._session_id,
                    kernels_seen=self._kernels_this_session,
                    ticks_observed=self._tick_counter,
                )
            self._session_store.close()
        if self._achievement_store is not None:
            self._achievement_store.close()
        if self._real_gpu_sampler is not None:
            self._real_gpu_sampler.close()
        if self._mirror_server is not None and self._mirror_server.is_running:
            with contextlib.suppress(Exception):
                self._mirror_server.stop()
        if self._leaderboard_store is not None:
            self._leaderboard_store.close()
        super().closeEvent(event)


def run_widget(app_config: AppConfig | None = None) -> int:
    """Entry helper used by the CLI and from Python scripts."""
    app = QApplication.instance() or QApplication([])
    widget = GPUVizWidget(app_config=app_config)
    widget.show()
    return app.exec()
