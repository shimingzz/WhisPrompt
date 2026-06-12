"""HTTP/HTTPS servers and the audio → transcript → prompt pipeline.

Two servers run in daemon threads:
- HTTPS (default :8443): the PWA + upload API. Mic access needs a secure context.
- HTTP  (default :8000): one-time helper page to download/trust the local CA.
"""
import datetime
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .certs import CA_CERT, ensure_certs, get_lan_ips
from .config import MODES, RECORDINGS_DIR, THINK_LEVELS, Settings, ensure_dirs
from .llm import OllamaClient
from .storage import HistoryStore
from .transcriber import Transcriber

log = logging.getLogger(__name__)
WEB_DIR = Path(__file__).resolve().parent / "web"


@dataclass
class Result:
    timestamp: str
    filename: str
    duration: float
    language: str
    transcript: str
    prompt: str
    mode: str
    elapsed: float
    id: str = ""
    archived: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Pipeline:
    settings: Settings
    transcriber: Transcriber
    llm: OllamaClient
    store: HistoryStore = field(default_factory=HistoryStore)
    # GUI subscribes here; called from worker threads.
    on_result: Callable[[Result], None] | None = None
    on_status: Callable[[str], None] | None = None
    # GUI refresh hook for history mutations made via the HTTP API (PWA).
    on_history_changed: Callable[[], None] | None = None

    def _status(self, msg: str) -> None:
        log.info(msg)
        if self.on_status:
            self.on_status(msg)

    def process(self, audio_path: Path, mode: str | None = None,
                think: str | None = None) -> Result:
        start = time.monotonic()
        self._status(f"轉錄中: {audio_path.name}")
        tr = self.transcriber.transcribe(audio_path, self.settings.whisper_language or None)
        return self._finish(
            start, tr["text"], mode, think,
            filename=audio_path.name,
            duration=round(tr["duration"], 1),
            language=tr["language"],
        )

    def process_text(self, text: str, mode: str | None = None,
                     think: str | None = None) -> Result:
        """Direct text input (no audio): optimize and record like a recording."""
        start = time.monotonic()
        return self._finish(start, text.strip(), mode, think,
                            filename="文字輸入", duration=0.0, language="text")

    def _finish(self, start: float, transcript: str, mode: str | None,
                think: str | None, *, filename: str, duration: float,
                language: str) -> Result:
        mode = mode if mode in MODES else self.settings.mode
        think = think if think in THINK_LEVELS else self.settings.think_level
        self._status("優化 prompt 中...")
        prompt = self.llm.optimize(transcript, mode, think)
        result = Result(
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            filename=filename,
            duration=duration,
            language=language,
            transcript=transcript,
            prompt=prompt,
            mode=mode,
            elapsed=round(time.monotonic() - start, 1),
        )
        payload = {k: v for k, v in result.to_dict().items() if k not in ("id", "archived")}
        result.id = self.store.add(payload)["id"]
        self._status("完成")
        if self.on_result:
            self.on_result(result)
        return result


def build_app(pipeline: Pipeline) -> FastAPI:
    app = FastAPI(title="WhisPrompt", version=__version__)

    @app.post("/api/audio")
    def upload_audio(file: UploadFile = File(...), mode: str = Form(""),
                     think: str = Form("")):
        ensure_dirs()
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = Path(file.filename or "audio.m4a").suffix or ".m4a"
        dest = RECORDINGS_DIR / f"rec_{stamp}{suffix}"
        dest.write_bytes(file.file.read())
        try:
            result = pipeline.process(dest, mode or None, think or None)
        except Exception as e:
            log.exception("pipeline failed")
            return JSONResponse({"error": str(e)}, status_code=500)
        return result.to_dict()

    @app.post("/api/text")
    def submit_text(body: dict):
        text = (body.get("text") or "").strip()
        if not text:
            return JSONResponse({"error": "text is empty"}, status_code=400)
        try:
            result = pipeline.process_text(
                text, body.get("mode") or None, body.get("think") or None)
        except Exception as e:
            log.exception("text pipeline failed")
            return JSONResponse({"error": str(e)}, status_code=500)
        return result.to_dict()

    @app.get("/api/status")
    def status():
        return {
            "version": __version__,
            "whisper_model": pipeline.transcriber.model_name,
            "whisper_device": pipeline.transcriber.device,
            "ollama_model": pipeline.llm.resolve_model(),
            "mode": pipeline.settings.mode,
            "modes": MODES,
            "think_level": pipeline.settings.think_level,
            "think_levels": THINK_LEVELS,
        }

    @app.get("/api/history")
    def history(limit: int = 50, archived: str = "0"):
        flag = None if archived == "all" else archived == "1"
        items = pipeline.store.list(archived=flag)
        return items[-limit:][::-1]  # newest first

    @app.delete("/api/history/{item_id}")
    def delete_history(item_id: str):
        if not pipeline.store.delete(item_id):
            return JSONResponse({"error": "not found"}, status_code=404)
        if pipeline.on_history_changed:
            pipeline.on_history_changed()
        return {"ok": True}

    @app.post("/api/history/{item_id}/archive")
    def archive_history(item_id: str, body: dict):
        item = pipeline.store.set_archived(item_id, bool(body.get("archived", True)))
        if item is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        if pipeline.on_history_changed:
            pipeline.on_history_changed()
        return item

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def build_cert_helper_app(https_port: int) -> FastAPI:
    """Plain-HTTP app: lets the iPhone download and trust the local CA."""
    app = FastAPI()

    @app.get("/ca.crt")
    def ca():
        return FileResponse(CA_CERT, media_type="application/x-x509-ca-cert",
                            filename="WhisPrompt-CA.crt")

    @app.get("/", response_class=HTMLResponse)
    def index():
        ip = get_lan_ips()[0]
        return f"""<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WhisPrompt 憑證安裝</title>
<body style="font-family:-apple-system,sans-serif;max-width:480px;margin:2em auto;padding:0 1em;line-height:1.7">
<h2>WhisPrompt — iPhone 首次設定</h2>
<ol>
<li><a href="/ca.crt"><b>下載憑證</b></a>(點擊後選「允許」)</li>
<li>開啟「設定」→「一般」→「VPN 與裝置管理」→ 安裝 <b>WhisPrompt Local CA</b></li>
<li>「設定」→「一般」→「關於本機」→「憑證信任設定」→ 開啟 <b>WhisPrompt Local CA</b></li>
<li>完成後前往 <a href="https://{ip}:{https_port}/">https://{ip}:{https_port}/</a>,並可「加入主畫面」</li>
</ol>
<p>此憑證僅由你電腦上的 WhisPrompt 產生與持有,只對區網連線生效。</p>
</body></html>"""

    return app


class ServerManager:
    """Runs both uvicorn servers in daemon threads."""

    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.settings = pipeline.settings
        self._servers: list[uvicorn.Server] = []

    def start(self) -> None:
        ensure_dirs()
        cert, key = ensure_certs()
        https = uvicorn.Config(
            build_app(self.pipeline), host="0.0.0.0", port=self.settings.https_port,
            ssl_certfile=str(cert), ssl_keyfile=str(key), log_level="warning",
        )
        http = uvicorn.Config(
            build_cert_helper_app(self.settings.https_port),
            host="0.0.0.0", port=self.settings.http_port, log_level="warning",
        )
        for cfg in (https, http):
            server = uvicorn.Server(cfg)
            t = threading.Thread(target=server.run, daemon=True)
            t.start()
            self._servers.append(server)
        log.info("HTTPS on :%d, HTTP helper on :%d",
                 self.settings.https_port, self.settings.http_port)

    def stop(self) -> None:
        for s in self._servers:
            s.should_exit = True

    @property
    def app_url(self) -> str:
        return f"https://{get_lan_ips()[0]}:{self.settings.https_port}/"

    @property
    def helper_url(self) -> str:
        return f"http://{get_lan_ips()[0]}:{self.settings.http_port}/"
