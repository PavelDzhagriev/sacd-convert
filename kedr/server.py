from __future__ import annotations

import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from kedr import __version__
from kedr.dialogs import DialogUnavailable, choose, reveal
from kedr.jobs import JobStore, launch
from kedr.models import EncodeSettings, KedrError
from kedr.probe import describe, probe
from kedr.tools import ffmpeg_has_lame, ffmpeg_has_soxr, find_tool, tool_version

WEB = Path(__file__).resolve().parent / "web"
FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/i18n.js": "i18n.js",
    "/styles.css": "styles.css",
    "/favicon.svg": "favicon.svg",
    "/icon.png": "icon.png",
}
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


class KedrServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], store: JobStore) -> None:
        self.store = store
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server: KedrServer

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in FILES:
            self._file(FILES[path])
            return
        if path == "/api/health":
            self._json(200, health())
            return
        if path.startswith("/api/jobs/"):
            self._job_get(path)
            return
        self._json(404, {"error": "Нет такой страницы."})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._body()
            if path == "/api/probe":
                disc = probe(str(payload.get("path", "")))
                self._json(200, describe(disc))
                return
            if path == "/api/convert":
                job = launch(
                    self.server.store,
                    str(payload.get("path", "")),
                    str(payload.get("output_dir", "")),
                    _settings(payload),
                    str(payload.get("mode") or "stereo"),
                    _tracks(payload.get("tracks")),
                )
                self._json(200, job.snapshot())
                return
            if path == "/api/dialog":
                self._json(200, _dialog(str(payload.get("kind", "")), str(payload.get("locale") or "")))
                return
            if path == "/api/reveal":
                reveal(str(payload.get("path", "")))
                self._json(200, {"ok": True})
                return
            if path.startswith("/api/jobs/") and path.endswith("/cancel"):
                job_id = path.removeprefix("/api/jobs/").removesuffix("/cancel").strip("/")
                job = self.server.store.get(job_id)
                if job is None:
                    self._json(404, {"error": "Задача не найдена."})
                    return
                job.cancel()
                self._json(200, job.snapshot())
                return
        except KedrError as exc:
            self._json(400, {"error": str(exc)})
            return
        except (TypeError, ValueError):
            self._json(400, {"error": "Проверьте числа в настройках."})
            return
        except (BrokenPipeError, ConnectionResetError):
            return
        self._json(404, {"error": "Нет такого запроса."})

    def _job_get(self, path: str) -> None:
        events = path.endswith("/events")
        job_id = path.removeprefix("/api/jobs/")
        if events:
            job_id = job_id.removesuffix("/events")
        job_id = job_id.strip("/")
        job = self.server.store.get(job_id)
        if job is None:
            self._json(404, {"error": "Задача не найдена."})
            return
        if not events:
            self._json(200, job.snapshot())
            return
        self._events(job)

    def _events(self, job) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last = ""
        try:
            while True:
                payload = json.dumps(job.snapshot(), ensure_ascii=False)
                if payload != last:
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
                    last = payload
                if job.snapshot()["status"] in {"done", "error", "cancelled"}:
                    break
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _file(self, name: str) -> None:
        path = WEB / name
        if not path.is_file():
            self._json(404, {"error": "Файл интерфейса не найден."})
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 1_000_000:
            raise KedrError("Слишком большой запрос.")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KedrError("Не удалось разобрать запрос.") from exc
        if not isinstance(payload, dict):
            raise KedrError("Не удалось разобрать запрос.")
        return payload

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s\n" % (fmt % args))


def health() -> dict:
    ffmpeg = find_tool("KEDR_FFMPEG", "ffmpeg")
    ffprobe = find_tool("KEDR_FFPROBE", "ffprobe")
    sacd = find_tool("KEDR_SACD_EXTRACT", "sacd_extract")
    if sys.platform == "darwin":
        hint = "Выполните scripts/install-macos.sh — скрипт поставит ffmpeg и соберёт sacd_extract."
    elif sys.platform == "win32":
        hint = "Выполните scripts/install-windows.ps1 — скрипт поставит ffmpeg и соберёт sacd_extract."
    else:
        hint = "Соберите extractor скриптом scripts/build-sacd-extract.sh и поставьте ffmpeg."
    return {
        "version": __version__,
        "platform": sys.platform,
        "hint": hint,
        "soxr": ffmpeg_has_soxr() if ffmpeg else False,
        "mp3": ffmpeg_has_lame() if ffmpeg else False,
        "ffmpeg": {
            "ok": ffmpeg is not None,
            "path": str(ffmpeg) if ffmpeg else "",
            "version": tool_version(ffmpeg) if ffmpeg else "",
        },
        "ffprobe": {"ok": ffprobe is not None, "path": str(ffprobe) if ffprobe else ""},
        "sacd_extract": {"ok": sacd is not None, "path": str(sacd) if sacd else ""},
    }


def _settings(payload: dict) -> EncodeSettings:
    fmt = str(payload.get("format") or "flac")
    if fmt not in ("flac", "mp3"):
        raise KedrError("Формат: FLAC или MP3.")
    rate = payload.get("rate")
    lowpass = payload.get("lowpass")
    if rate is None:
        rate = 44100 if fmt == "mp3" else 176400
    if lowpass is None:
        lowpass = 20000 if fmt == "mp3" else 40000
    return EncodeSettings(
        rate=int(rate),
        bits=int(payload.get("bits") or 24),
        lowpass=int(lowpass),
        compression=int(payload.get("compression") if payload.get("compression") is not None else 8),
        format=fmt,
        bitrate=int(payload.get("bitrate") or 320),
    )


def _tracks(value) -> list[int] | None:
    if not value:
        return None
    if not isinstance(value, list):
        raise KedrError("Список дорожек должен быть массивом номеров.")
    numbers = []
    for item in value:
        number = int(item)
        if number < 1:
            raise KedrError("Номера дорожек начинаются с 1.")
        numbers.append(number)
    return numbers


def _dialog(kind: str, locale: str) -> dict:
    try:
        path = choose(kind, locale if locale == "ru" else "en")
    except DialogUnavailable as exc:
        return {"unavailable": True, "message": str(exc)}
    if not path:
        return {"cancelled": True}
    return {"path": path}


def serve(port: int = 47631, open_browser: bool = False) -> None:
    try:
        server = KedrServer(("127.0.0.1", port), JobStore())
    except OSError as exc:
        print(f"Порт {port} занят. Кедр, возможно, уже открыт: http://127.0.0.1:{port}", file=sys.stderr)
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Кедр слушает {url}", flush=True)
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено")
    finally:
        server.server_close()
