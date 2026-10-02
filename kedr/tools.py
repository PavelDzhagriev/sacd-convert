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
    if sys.platform == "win32":
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        return env
    locale = "en_US.UTF-8" if sys.platform == "darwin" else "C.UTF-8"
    env["LANG"] = locale
    env["LC_ALL"] = locale
    return env


def tool_file_names(executable: str, platform: str | None = None) -> list[str]:
    system = platform or sys.platform
    if system == "win32" and not executable.lower().endswith(".exe"):
        return [executable, f"{executable}.exe"]
    return [executable]


def _is_runnable(path: Path) -> bool:
    if not path.is_file():
        return False
    if sys.platform == "win32":
        return True
    return os.access(path, os.X_OK)


def _candidates(env_name: str, executable: str) -> list[Path]:
    names = tool_file_names(executable)
    found: list[Path] = []
    override = os.environ.get(env_name)
    if override:
        found.append(Path(override))
    for name in names:
        found.append(ROOT / "bin" / name)
        found.append(ROOT / "dist" / "Kedr.app" / "Contents" / "Resources" / "bin" / name)
        resources = os.environ.get("KEDR_RESOURCES")
        if resources:
            found.append(Path(resources) / "bin" / name)
        which = shutil.which(name)
        if which:
            found.append(Path(which))
    return found


def find_tool(env_name: str, executable: str) -> Path | None:
    for path in _candidates(env_name, executable):
        if _is_runnable(path):
            return path
    return None


def _missing_ffmpeg() -> str:
    if sys.platform == "win32":
        return (
            "Не найден ffmpeg. На Windows выполните scripts/install-windows.ps1. "
            "Без него DSD не во что переводить: FLAC хранит PCM."
        )
    if sys.platform == "darwin":
        return (
            "Не найден ffmpeg. На Mac: brew install ffmpeg. "
            "Без него DSD не во что переводить: FLAC хранит PCM."
        )
    return (
        "Не найден ffmpeg. Поставьте пакет ffmpeg. "
        "Без него DSD не во что переводить: FLAC хранит PCM."
    )


def _missing_sacd_extract() -> str:
    if sys.platform == "win32":
        return (
            "Не найден sacd_extract. На Windows выполните scripts/install-windows.ps1 — "
            "скрипт соберёт его из sacd-ripper. Обычный ffmpeg образ SACD не читает."
        )
    if sys.platform == "darwin":
        return (
            "Не найден sacd_extract. На Mac выполните scripts/install-macos.sh — "
            "скрипт соберёт его из sacd-ripper. Обычный ffmpeg образ SACD не читает."
        )
    return (
        "Не найден sacd_extract. Соберите его скриптом scripts/build-sacd-extract.sh "
        "из sacd-ripper. Обычный ffmpeg образ SACD не читает."
    )


def ffmpeg_path() -> Path:
    path = find_tool("KEDR_FFMPEG", "ffmpeg")
    if path is None:
        raise KedrError(_missing_ffmpeg())
    return path


def ffprobe_path() -> Path:
    path = find_tool("KEDR_FFPROBE", "ffprobe")
    if path is None:
        parent = ffmpeg_path().parent
        for name in tool_file_names("ffprobe"):
            sibling = parent / name
            if _is_runnable(sibling):
                return sibling
        raise KedrError("Не найден ffprobe. Он ставится вместе с ffmpeg.")
    return path


def sacd_extract_path() -> Path:
    path = find_tool("KEDR_SACD_EXTRACT", "sacd_extract")
    if path is None:
        raise KedrError(_missing_sacd_extract())
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
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                check=False,
                capture_output=True,
                timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            return
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


class _OutputText:
    """Склеивает вывод процесса в строки. Windows-сборка sacd_extract пишет UTF-16."""

    def __init__(self) -> None:
        self._pending = bytearray()
        self._encoding: str | None = None

    def feed(self, chunk: bytes) -> list[str]:
        if chunk:
            self._pending.extend(chunk)
        self._detect()
        if self._encoding is None:
            return []
        return self._drain(final=False)

    def finish(self) -> list[str]:
        if self._encoding is None and self._pending:
            self._encoding = "utf-8"
        return self._drain(final=True)

    def _detect(self) -> None:
        if self._encoding is not None or not self._pending:
            return
        sample = bytes(self._pending[:64])
        if sample.startswith(b"\xff\xfe"):
            self._encoding = "utf-16-le"
            del self._pending[:2]
            return
        if sample.startswith(b"\xfe\xff"):
            self._encoding = "utf-16-be"
            del self._pending[:2]
            return
        if sample.count(0) > max(2, len(sample) // 4):
            self._encoding = "utf-16-le"
            return
        if b"\n" in sample or b"\r" in sample or len(self._pending) >= 64:
            self._encoding = "utf-8"

    def _drain(self, final: bool) -> list[str]:
        encoding = self._encoding or "utf-8"
        data = bytes(self._pending)
        if encoding.startswith("utf-16"):
            usable = data[: len(data) - (len(data) % 2)]
            hold = data[len(usable) :]
            cut = max(usable.rfind("\n".encode(encoding)), usable.rfind("\r".encode(encoding)))
            if cut < 0:
                if not final:
                    return []
                text = usable.decode(encoding, "replace")
                rest = b""
            else:
                text = usable[: cut + 2].decode(encoding, "replace")
                rest = usable[cut + 2 :] + hold
        else:
            cut = max(data.rfind(b"\n"), data.rfind(b"\r"))
            if cut < 0:
                if not final:
                    return []
                text = data.decode("utf-8", "replace")
                rest = b""
            else:
                text = data[: cut + 1].decode("utf-8", "replace")
                rest = data[cut + 1 :]
        parts = text.replace("\r", "\n").split("\n")
        if cut >= 0 and parts and parts[-1] == "":
            parts = parts[:-1]
        lines = [part.strip() for part in parts if part.strip()]
        if final and rest:
            extra = rest.decode(encoding, "replace").strip()
            if extra:
                lines.append(extra)
            rest = b""
        self._pending = bytearray(rest)
        return lines


def run_piped(
    cmd: list[str],
    on_line,
    stop,
    slot: ProcSlot,
    cwd: Path | None = None,
) -> tuple[int, list[str]]:
    popen_kwargs: dict = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        popen_kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=str(cwd) if cwd else None,
            env=utf8_env(),
            **popen_kwargs,
        )
    except FileNotFoundError as exc:
        raise KedrError(f"Не удалось запустить {cmd[0]}: {exc}") from exc

    slot.set(proc)
    kept: list[str] = []
    assert proc.stdout is not None
    reader = _OutputText()
    try:
        while True:
            if stop.is_set():
                kill_group(proc)
                raise Cancelled()
            chunk = proc.stdout.read(512)
            if not chunk:
                break
            for text in reader.feed(chunk):
                on_line(text)
                if text.startswith("Completed:"):
                    continue
                kept.append(text)
                del kept[:-20000]
        for text in reader.finish():
            on_line(text)
            if text.startswith("Completed:"):
                continue
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
