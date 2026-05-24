"""OS-level user-action listener that drops :class:`Kernel` work items
into a thread-safe queue.

The listener deliberately does **not** depend on Qt — it pushes kernels
into a :class:`queue.Queue`, and the GUI polls that queue from its own
main-thread timer.  This keeps the simulation testable without a
display server.

Handled events:

* mouse move            → ``interpolation`` kernel (heavily throttled)
* mouse click           → ``vector_add`` kernel
* keyboard press        → ``hash`` kernel
* foreground app change → ``texture_load`` kernel
* foreground title tweak (e.g. URL change) → ``page_nav`` kernel
* new process launched  → ``app_launch`` kernel
* sustained idle        → ``idle_compression`` kernel

The exact event → kernel mapping is configurable via
:class:`~gpu_simulator.config.AppConfig` so users can re-wire the
relationship without touching this module.
"""

from __future__ import annotations

import contextlib
import queue
import sys
import threading
import time
from dataclasses import dataclass

from gpu_simulator.config import DEFAULT_TRIGGER_MAPPING, AppConfig
from gpu_simulator.kernel import Kernel, KernelLibrary


@dataclass
class EventListenerConfig:
    """Knobs controlling how chatty the listener is."""

    mouse_move_throttle_seconds: float = 0.4
    idle_threshold_seconds: float = 5.0
    focus_poll_interval_seconds: float = 1.0
    process_poll_interval_seconds: float = 2.0


class KernelQueue:
    """A thin wrapper around :class:`queue.Queue` for clarity at call sites."""

    def __init__(self, max_size: int = 256) -> None:
        self._queue: queue.Queue[Kernel] = queue.Queue(maxsize=max_size)

    def push(self, kernel: Kernel) -> None:
        with contextlib.suppress(queue.Full):
            # Drop on overflow — visualization value only.
            self._queue.put_nowait(kernel)

    def drain(self, limit: int = 16) -> list[Kernel]:
        drained: list[Kernel] = []
        for _ in range(limit):
            try:
                drained.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return drained


class EventListener:
    """Listens for OS events on background threads and feeds the queue.

    The listener is started with :meth:`start` and stopped with
    :meth:`stop`.  Every backend (pynput, ctypes, psutil) is imported
    lazily and wrapped in ``try`` so a missing dependency or a denied
    OS permission only silences that one signal rather than crashing.
    """

    def __init__(
        self,
        kernel_queue: KernelQueue,
        config: EventListenerConfig | None = None,
        trigger_mapping: dict[str, str] | None = None,
    ) -> None:
        self._queue = kernel_queue
        self._config = config or EventListenerConfig()
        self._trigger_mapping: dict[str, str] = dict(
            trigger_mapping if trigger_mapping is not None else DEFAULT_TRIGGER_MAPPING
        )
        self._last_mouse_move_time: float = 0.0
        self._last_event_time: float = time.monotonic()
        self._last_focus_app: str = ""
        self._last_focus_title: str = ""
        self._seen_process_ids: set[int] = set()
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._pynput_listeners: list[object] = []

    # ------------------------------------------------------------------
    # factory helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_app_config(
        cls, kernel_queue: KernelQueue, app_config: AppConfig
    ) -> EventListener:
        listener_config = EventListenerConfig(
            mouse_move_throttle_seconds=app_config.event_listener.mouse_move_throttle_seconds,
            idle_threshold_seconds=app_config.event_listener.idle_threshold_seconds,
            focus_poll_interval_seconds=app_config.event_listener.focus_poll_interval_seconds,
            process_poll_interval_seconds=app_config.event_listener.process_poll_interval_seconds,
        )
        return cls(
            kernel_queue=kernel_queue,
            config=listener_config,
            trigger_mapping=app_config.trigger_mapping,
        )

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        self._stop_event.clear()
        self._start_pynput_listeners()
        self._seen_process_ids = _current_process_ids()
        self._spawn_thread(self._idle_loop, name="gpu-simulator-idle")
        self._spawn_thread(self._focus_loop, name="gpu-simulator-focus")
        self._spawn_thread(self._process_loop, name="gpu-simulator-proc")

    def stop(self) -> None:
        self._stop_event.set()
        for listener in self._pynput_listeners:
            stop = getattr(listener, "stop", None)
            if callable(stop):
                with contextlib.suppress(Exception):
                    stop()
        self._pynput_listeners.clear()
        for thread in self._threads:
            thread.join(timeout=1.0)
        self._threads.clear()

    # ------------------------------------------------------------------
    # kernel emission helper
    # ------------------------------------------------------------------
    def _emit(self, event_name: str, *, hint: str = "", trigger: str = "") -> None:
        """Look up the configured kernel for ``event_name`` and push it."""
        kernel_name = self._trigger_mapping.get(event_name)
        if not kernel_name:
            return
        try:
            kernel = KernelLibrary.build(
                kernel_name,
                trigger=trigger or event_name,
                hint=hint,
            )
        except ValueError:
            return
        self._queue.push(kernel)

    # ------------------------------------------------------------------
    # handlers
    # ------------------------------------------------------------------
    def _on_mouse_move(self, x: int, y: int) -> None:
        now = time.monotonic()
        self._last_event_time = now
        if now - self._last_mouse_move_time < self._config.mouse_move_throttle_seconds:
            return
        self._last_mouse_move_time = now
        self._emit("mouse_move", trigger=f"mouse_move({x},{y})")

    def _on_mouse_click(self, x: int, y: int, button, pressed: bool) -> None:  # noqa: ARG002
        if not pressed:
            return
        self._last_event_time = time.monotonic()
        self._emit("mouse_click", trigger=f"mouse_click:{button}")

    def _on_key_press(self, key) -> None:
        self._last_event_time = time.monotonic()
        try:
            key_repr = key.char if hasattr(key, "char") and key.char else str(key)
        except Exception:
            key_repr = "?"
        self._emit("key_press", hint=key_repr, trigger="keyboard")

    # ------------------------------------------------------------------
    # background loops
    # ------------------------------------------------------------------
    def _idle_loop(self) -> None:
        """Emit an idle-compression kernel whenever the user is inactive."""
        sent_for_this_idle_window = False
        while not self._stop_event.wait(timeout=1.0):
            idle_seconds = time.monotonic() - self._last_event_time
            if idle_seconds >= self._config.idle_threshold_seconds:
                if not sent_for_this_idle_window:
                    self._emit("idle", trigger="idle")
                    sent_for_this_idle_window = True
            else:
                sent_for_this_idle_window = False

    def _focus_loop(self) -> None:
        while not self._stop_event.wait(
            timeout=self._config.focus_poll_interval_seconds
        ):
            app_name, title = _active_window_info()
            if not app_name and not title:
                continue
            if app_name != self._last_focus_app:
                self._last_focus_app = app_name
                self._last_focus_title = title
                self._last_event_time = time.monotonic()
                self._emit(
                    "focus_change",
                    hint=app_name or title,
                    trigger=f"focus:{app_name}",
                )
            elif title != self._last_focus_title:
                self._last_focus_title = title
                self._last_event_time = time.monotonic()
                self._emit("page_nav", hint=title, trigger=f"title:{title[:60]}")

    def _process_loop(self) -> None:
        while not self._stop_event.wait(
            timeout=self._config.process_poll_interval_seconds
        ):
            try:
                current = _current_process_ids()
            except Exception:
                continue
            new_pids = current - self._seen_process_ids
            self._seen_process_ids = current
            for pid in new_pids:
                name = _process_name(pid) or f"pid#{pid}"
                if _is_ignorable_process(name):
                    continue
                self._last_event_time = time.monotonic()
                self._emit("app_launch", hint=name, trigger=f"launch:{name}")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _spawn_thread(self, target, name: str) -> None:
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
        self._threads.append(thread)

    def _start_pynput_listeners(self) -> None:
        try:
            from pynput import keyboard, mouse
        except Exception as exc:  # pragma: no cover - optional dep
            print(f"[gpu_simulator] pynput unavailable, OS events disabled: {exc}")
            return
        mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
        )
        keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        mouse_listener.start()
        keyboard_listener.start()
        self._pynput_listeners.extend([mouse_listener, keyboard_listener])


# ---------------------------------------------------------------------------
# platform helpers (kept module-level so they are easy to mock in tests)
# ---------------------------------------------------------------------------
def _active_window_info() -> tuple[str, str]:
    """Return ``(app_name, window_title)``; either may be empty on failure."""
    if sys.platform.startswith("win"):
        return _active_window_info_windows()
    if sys.platform == "darwin":
        return "", _active_window_title_macos()
    return "", _active_window_title_linux()


def _active_window_info_windows() -> tuple[str, str]:
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", ""
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            import psutil

            app_name = psutil.Process(pid.value).name()
        except Exception:
            app_name = ""
        return app_name, title
    except Exception:
        return "", ""


def _active_window_title_macos() -> str:  # pragma: no cover - platform dependent
    try:
        from AppKit import NSWorkspace

        info = NSWorkspace.sharedWorkspace().activeApplication()
        return info.get("NSApplicationName", "") if info else ""
    except Exception:
        return ""


def _active_window_title_linux() -> str:  # pragma: no cover - platform dependent
    try:
        import subprocess

        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=0.3,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _current_process_ids() -> set[int]:
    try:
        import psutil

        return set(psutil.pids())
    except Exception:
        return set()


def _process_name(pid: int) -> str:
    try:
        import psutil

        return psutil.Process(pid).name()
    except Exception:
        return ""


_IGNORED_PROCESS_NAMES: frozenset[str] = frozenset(
    {
        "conhost.exe",
        "svchost.exe",
        "RuntimeBroker.exe",
        "backgroundTaskHost.exe",
        "WmiPrvSE.exe",
        "dllhost.exe",
        "ApplicationFrameHost.exe",
    }
)


def _is_ignorable_process(name: str) -> bool:
    return name in _IGNORED_PROCESS_NAMES or name.lower().startswith("python")
