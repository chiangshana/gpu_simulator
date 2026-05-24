"""widget 螢幕錄影 → 動圖 GIF。

收幀走 PySide6 的 :meth:`QWidget.grab` (回傳 :class:`QPixmap`),
編碼用 PIL(matplotlib 已經把 Pillow 拉進來,沒有額外相依)。

UI 端用法很單純::

    recorder = GIFRecorder(widget)
    recorder.start()
    ... 一段時間後 ...
    saved_path = recorder.stop()
"""

from __future__ import annotations

import io
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QObject, QTimer
from PySide6.QtWidgets import QWidget


class RecorderError(Exception):
    """錄影過程出錯。"""


class GIFRecorder(QObject):
    """以固定 FPS 取截圖,結束時編碼為 GIF。

    內建幀數上限,避免使用者忘了停止把記憶體吃光。
    """

    DEFAULT_FRAME_INTERVAL_MS: int = 250  # 4 fps,適合 demo
    DEFAULT_MAX_FRAMES: int = 240         # ≈ 60 秒

    def __init__(
        self,
        widget: QWidget,
        output_dir: Path | str,
        frame_interval_ms: int | None = None,
        max_frames: int | None = None,
        on_progress: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(widget)
        self._widget = widget
        self._output_dir = Path(output_dir).expanduser()
        self._frame_interval_ms = frame_interval_ms or self.DEFAULT_FRAME_INTERVAL_MS
        self._max_frames = max_frames or self.DEFAULT_MAX_FRAMES
        self._on_progress = on_progress or (lambda _frame_count: None)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._capture_frame)
        self._frames: list[bytes] = []
        self._started_at: float = 0.0
        self._is_recording: bool = False

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._is_recording:
            return
        self._frames.clear()
        self._is_recording = True
        self._started_at = time.monotonic()
        self._timer.start(self._frame_interval_ms)
        # 馬上抓第一幀,免得使用者按下後先看到一片黑
        self._capture_frame()

    def stop(self) -> Path | None:
        if not self._is_recording:
            return None
        self._timer.stop()
        self._is_recording = False
        if not self._frames:
            return None
        return self._encode_to_gif()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def elapsed_seconds(self) -> float:
        if not self._is_recording:
            return 0.0
        return time.monotonic() - self._started_at

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _capture_frame(self) -> None:
        if not self._is_recording:
            return
        try:
            pixmap = self._widget.grab()
        except Exception:
            self.stop()
            return
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        # PNG 是無損的,後續轉 GIF 時 PIL 會做 palette quantization
        if not pixmap.save(buffer, "PNG"):
            return
        self._frames.append(bytes(buffer.data()))
        self._on_progress(len(self._frames))
        if len(self._frames) >= self._max_frames:
            self.stop()

    def _encode_to_gif(self) -> Path:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RecorderError(
                "Pillow is required for GIF recording — install with `pip install pillow`."
            ) from exc

        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_path = self._output_dir / f"gpu-simulator-{timestamp}.gif"

        images = [Image.open(io.BytesIO(payload)).convert("P", palette=Image.ADAPTIVE)
                  for payload in self._frames]
        if not images:
            raise RecorderError("no frames were captured")
        first, *rest = images
        try:
            first.save(
                output_path,
                save_all=True,
                append_images=rest,
                duration=self._frame_interval_ms,
                loop=0,
                optimize=True,
            )
        except Exception as exc:
            raise RecorderError(f"saving GIF failed: {exc}") from exc
        return output_path
