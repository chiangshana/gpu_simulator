"""Web 鏡像 — 在背景 thread 跑一個小型 HTTP server,讓瀏覽器看 GPU 狀態。

零外部相依:全用 stdlib :mod:`http.server` + :mod:`json`,
沒有 Flask / FastAPI / WebSocket 套件相依。

UI 端 widget 透過 :class:`SnapshotPublisher` 把目前 GPU snapshot 推給 server,
server 提供兩個 endpoint:

- ``GET /``           回一個簡單的 HTML(內嵌 JS 每 500ms poll 一次)
- ``GET /snapshot``   回最新的 snapshot JSON

UI 上一個 toggle 鈕呼叫 :meth:`MirrorServer.start` / :meth:`stop`。
**整個 server 在 daemon thread 上跑,widget 關閉就一起死,不會留 zombie。**
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger(__name__)


_HTML_PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<title>GPU Simulator · Live Mirror</title>
<style>
  body { font-family: Consolas, monospace; background: #14171f; color: #dadfe8;
         margin: 0; padding: 20px; }
  h1 { font-size: 18px; color: #ffd884; margin: 0 0 12px; }
  .stats { background: #1d2230; padding: 8px 14px; border-radius: 6px; margin: 8px 0; }
  .sm-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
             margin: 12px 0; }
  .sm-cell { padding: 12px; border-radius: 6px; text-align: center;
             font-weight: bold; }
  .events { background: #1d2230; padding: 10px; border-radius: 6px;
            font-size: 12px; max-height: 240px; overflow-y: auto;
            white-space: pre-wrap; }
  .label { color: #8a92a4; }
</style>
</head>
<body>
  <h1>🛰️ GPU Simulator — Live Mirror</h1>
  <p class="label">每 500 毫秒從 widget 抓一次 snapshot。關掉 widget 此頁也會停。</p>
  <div class="stats" id="stats">尚未連線</div>
  <div class="sm-grid" id="sm-grid"></div>
  <div class="label">事件 log:</div>
  <div class="events" id="events">(等待…)</div>
<script>
async function refresh() {
  try {
    const response = await fetch('/snapshot', { cache: 'no-store' });
    if (!response.ok) {
      document.getElementById('stats').textContent =
        '未取得 snapshot(widget 可能還沒推第一筆)';
      return;
    }
    const data = await response.json();
    const stats = document.getElementById('stats');
    const util = (data.overall_utilization || 0) * 100;
    stats.textContent =
      `clock ${data.clock || 0}  ·  util ${util.toFixed(0)}%  ·  ` +
      `submitted ${data.kernels_submitted || 0}  ·  completed ${data.kernels_completed || 0}`;
    const smGrid = document.getElementById('sm-grid');
    smGrid.innerHTML = '';
    for (const sm of (data.sms || [])) {
      const div = document.createElement('div');
      div.className = 'sm-cell';
      const u = (sm.utilization || 0);
      const r = Math.round(40 + u * 200);
      const g = Math.round(80 + (1-u) * 100);
      const b = Math.round(80 + (1-u) * 80);
      div.style.background = `rgb(${r}, ${g}, ${b})`;
      div.textContent = `SM${sm.sm_id}  ${(u*100).toFixed(0)}%`;
      smGrid.appendChild(div);
    }
    const events = document.getElementById('events');
    events.textContent = (data.event_log || [])
      .slice(-20)
      .map(e => `[${e.clock}] ${e.message}`)
      .join('\\n');
  } catch (err) {
    document.getElementById('stats').textContent = '連線錯誤:' + err.message;
  }
}
setInterval(refresh, 500);
refresh();
</script>
</body></html>
"""


@dataclass
class SnapshotPublisher:
    """Thread-safe holder for the latest GPU snapshot dict."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    snapshot: dict = field(default_factory=dict)

    def publish(self, snapshot: dict) -> None:
        with self.lock:
            self.snapshot = snapshot

    def get(self) -> dict:
        with self.lock:
            return dict(self.snapshot)


class _MirrorRequestHandler(BaseHTTPRequestHandler):
    publisher: SnapshotPublisher | None = None  # set by MirrorServer

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # 把預設的 stderr noise 收進 logger,不要洗螢幕
        logger.info("[web-mirror] " + format, *args)

    def do_GET(self) -> None:  # noqa: N802 - http.server convention
        path = self.path.split("?", 1)[0]
        if path == "/":
            payload = _HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/snapshot":
            publisher = type(self).publisher
            if publisher is None:
                self.send_response(503)
                self.end_headers()
                return
            payload = json.dumps(publisher.get(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()


class MirrorServer:
    """Background HTTP server that surfaces GPU snapshots over HTTP."""

    def __init__(
        self,
        publisher: SnapshotPublisher,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self._publisher = publisher
        self._host = host
        self._port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}/"

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return

        # 把 publisher 綁在 handler class(每次連線都共用同一個)
        class BoundHandler(_MirrorRequestHandler):
            pass

        BoundHandler.publisher = self._publisher
        self._server = ThreadingHTTPServer((self._host, self._port), BoundHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="gpu-simulator-web-mirror",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
