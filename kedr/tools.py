from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

from kedr.models import Cancelled, KedrError

ROOT = Path(__file__).resolve().parents[1]


def utf8_env() -> dict[str, str]:
    env = os.environ.copy()
    locale = "en_US.UTF-8" if sys.platform == "darwin" else "C.UTF-8"
    env["LANG"] = locale
    env["LC_ALL"] = locale
    return env


def _candidates(env_name: str, executable: str) -> list[Path]:
    found: list[Path] = []
    override = os.environ.get(env_name)
    if override:
        found.append(Path(override))
    found.append(ROOT / "bin" / executable)
    found.append(ROOT / "dist" / "Kedr.app" / "Contents" / "Resources" / "bin" / executable)
    resources = os.environ.get("KEDR_RESOURCES")
    if resources:
        found.append(Path(resources) / "bin" / executable)
    which = shutil.which(executable)
    if which:
        found.append(Path(which))
    return found


def find_tool(env_name: str, executable: str) -> Path | None:
    for path in _candidates(env_name, executable):
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def ffmpeg_path() -> Path:
    path = find_tool("KEDR_FFMPEG", "ffmpeg")
    if path is None:
        raise KedrError(
            "Не найден ffmpeg. На Mac: brew install ffmpeg. "
            "Без него DSD не во что переводить: FLAC хранит PCM."
        )
    return path


def ffprobe_path() -> Path:
    path = find_tool("KEDR_FFPROBE", "ffprobe")
    if path is None:
        sibling = ffmpeg_path().parent / "ffprobe"
        if sibling.is_file():
            return sibling
        raise KedrError("Не найден ffprobe. Он ставится вместе с ffmpeg.")
    return path


def sacd_extract_path() -> Path:
    path = find_tool("KEDR_SACD_EXTRACT", "sacd_extract")
    if path is None:
        raise KedrError(
            "Не найден sacd_extract. На Mac выполните scripts/install-macos.sh — "
            "скрипт соберёт его из sacd-ripper. Обычный ffmpeg образ SACD не читает."
        )
    return path


def tool_version(path: Path) -> str:
    try:
        completed = subprocess.run(
            [str(path), "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    line = (completed.stdout or completed.stderr or "").splitlines()
    return line[0].strip() if line else ""


def kill_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        proc.wait(timeout=3)


class ProcSlot:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def set(self, proc: subprocess.Popen | None) -> None:
        with self._lock:
            self._proc = proc

    def kill(self) -> None:
        with self._lock:
            proc = self._proc
        if proc is not None:
            kill_group(proc)


def ffmpeg_has_lame() -> bool:
    global _LAME
    if _LAME is not None:
        return _LAME
    try:
        completed = subprocess.run(
            [str(ffmpeg_path()), "-hide_banner", "-encoders"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired, KedrError):
        _LAME = False
        return False
    _LAME = "libmp3lame" in (completed.stdout or "")
    return _LAME


_LAME: bool | None = None


def ffmpeg_has_soxr() -> bool:
    global _SOXR
    if _SOXR is not None:
        return _SOXR
    try:
        completed = subprocess.run(
            [str(ffmpeg_path()), "-hide_banner", "-h", "filter=aresample"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired, KedrError):
        _SOXR = False
        return False
    _SOXR = "soxr" in (completed.stdout or "").lower()
    return _SOXR


_SOXR: bool | None = None


def run_piped(
    cmd: list[str],
    on_line,
    stop,
    slot: ProcSlot,
    cwd: Path | None = None,
) -> tuple[int, list[str]]:
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=str(cwd) if cwd else None,
            env=utf8_env(),
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise KedrError(f"Не удалось запустить {cmd[0]}: {exc}") from exc

    slot.set(proc)
    kept: list[str] = []
    assert proc.stdout is not None
    buffer = ""
    try:
        while True:
            if stop.is_set():
                kill_group(proc)
                raise Cancelled()
            chunk = proc.stdout.read(512)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", "replace")
            parts = buffer.replace("\r", "\n").split("\n")
            buffer = parts.pop()
            for part in parts:
                text = part.strip()
                if not text:
                    continue
                on_line(text)
                if text.startswith("Completed:"):
                    continue
                kept.append(text)
                del kept[:-20000]
        if buffer.strip():
            text = buffer.strip()
            on_line(text)
            if not text.startswith("Completed:"):
                kept.append(text)
        code = proc.wait()
    finally:
        if proc.poll() is None:
            kill_group(proc)
        if proc.stdout is not None and not proc.stdout.closed:
            proc.stdout.close()
        slot.set(None)
    if stop.is_set():
        kill_group(proc)
        raise Cancelled()
    return code, kept
