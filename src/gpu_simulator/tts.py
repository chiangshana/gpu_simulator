"""(Optional)中文 TTS(text-to-speech)旁白。

依 :mod:`pyttsx3` (可選相依)讀出 widget 的事件(寵物說話、成就解鎖、AI 解釋)。
沒裝 pyttsx3 / 系統沒語音引擎 → :func:`is_available` 回 False,
UI 端的 TTS toggle 仍可顯示,但點下去只會印「請安裝 pyttsx3」。

設計重點:**永遠不阻塞 GUI thread**(`speak()` 把工作丟到背景 thread)。
"""

from __future__ import annotations

import contextlib
import threading
from queue import Empty, Queue

_global_engine_lock = threading.Lock()
_global_speaker: TTSEngine | None = None


def is_available() -> tuple[bool, str]:
    """Return (available, reason)。"""
    try:
        import pyttsx3  # noqa: F401
    except ImportError:
        return False, "pyttsx3 套件未安裝。可選的:pip install pyttsx3"
    try:
        engine = pyttsx3.init()
        engine.stop()
    except Exception as exc:
        return False, f"pyttsx3 初始化失敗:{exc}"
    return True, ""


class TTSEngine:
    """背景 thread + Queue,讓 ``speak(text)`` 非阻塞。"""

    def __init__(self, rate_wpm: int = 180) -> None:
        self._queue: Queue[str] = Queue(maxsize=64)
        self._stop_event = threading.Event()
        self._rate_wpm = rate_wpm
        self._thread: threading.Thread | None = None
        self._enabled: bool = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        self._enabled = value

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop, name="gpu-simulator-tts", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def speak(self, text: str) -> None:
        """非阻塞地排程一段文字朗讀。enabled = False 時直接無視。"""
        if not self._enabled or not text.strip():
            return
        with contextlib.suppress(Exception):
            self._queue.put_nowait(text)

    # ------------------------------------------------------------------
    # 背景 worker
    # ------------------------------------------------------------------
    def _worker_loop(self) -> None:
        try:
            import pyttsx3
        except ImportError:
            return
        engine = None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate_wpm)
        except Exception:
            return
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.3)
            except Empty:
                continue
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                continue


def get_or_create_speaker() -> TTSEngine:
    """全 process 共用一個 TTSEngine(因為大多 OS 一次只能跑一個 TTS engine)。"""
    global _global_speaker
    with _global_engine_lock:
        if _global_speaker is None:
            _global_speaker = TTSEngine()
            _global_speaker.start()
        return _global_speaker


def speak(text: str) -> None:
    """便利函式:取共用 engine 並排程朗讀。"""
    get_or_create_speaker().speak(text)
