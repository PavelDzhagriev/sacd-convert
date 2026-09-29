from __future__ import annotations

import json
import subprocess
from pathlib import Path

import threading

from kedr.models import Area, Disc, KedrError, Track
from kedr.naming import album_dirname
from kedr.parse import parse_sacd_print
from kedr.tools import ProcSlot, ffprobe_path, run_piped, sacd_extract_path, utf8_env


def describe(disc: Disc) -> dict:
    payload = disc.to_json()
    for raw, area in zip(payload["areas"], disc.areas):
        raw["dirname"] = album_dirname(disc, area)
    payload["suggested_output"] = str(Path(disc.source).resolve().parent)
    return payload


def resolve_source(raw: str) -> Path:
    if not raw or not raw.strip():
        raise KedrError("Укажите путь к SACD ISO или DSF.")
    path = Path(raw.strip()).expanduser().resolve()
    if not path.exists():
        raise KedrError(f"Файл не найден: {path}")
    if not path.is_file():
        raise KedrError("Нужен файл, а не папка.")
    return path


def probe(raw: str, stop: threading.Event | None = None, slot: ProcSlot | None = None) -> Disc:
    path = resolve_source(raw)
    suffix = path.suffix.lower()
    if suffix in {".dsf", ".dff"}:
        return probe_dsd_file(path)
    if suffix not in {".iso", ""}:
        raise KedrError("Нужен образ SACD (.iso) или файл DSD (.dsf).")
    return probe_iso(path, stop, slot)


def probe_iso(
    path: Path,
    stop: threading.Event | None = None,
    slot: ProcSlot | None = None,
) -> Disc:
    binary = sacd_extract_path()
    code, tail = run_piped(
        [str(binary), "-P", "-i", str(path)],
        on_line=lambda _line: None,
        stop=stop or threading.Event(),
        slot=slot or ProcSlot(),
    )
    text = "\n".join(tail)
    if code not in (0, None) and "Disc Information" not in text:
        raise KedrError(
            "Не удалось прочитать образ. Файл не похож на SACD ISO "
            "или sacd_extract не смог его открыть."
        )
    return parse_sacd_print(text, str(path))


def probe_dsd_file(path: Path) -> Disc:
    try:
        completed = subprocess.run(
            [
                str(ffprobe_path()),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=utf8_env(),
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise KedrError("ffprobe слишком долго читал файл.") from exc
    if completed.returncode != 0:
        raise KedrError("ffmpeg не смог прочитать этот DSD-файл.")
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise KedrError("ffmpeg вернул непонятный ответ.") from exc

    streams = [item for item in payload.get("streams", []) if item.get("codec_type") == "audio"]
    if not streams:
        raise KedrError("В файле нет звуковой дорожки.")
    stream = streams[0]
    info = payload.get("format", {})
    tags = {str(key).lower(): value for key, value in (info.get("tags") or {}).items()}
    channels = int(stream.get("channels") or 2)
    if channels <= 2:
        mode, label = "stereo", "Стерео"
    elif channels == 5:
        mode, label = "multi", "5.0"
    elif channels == 6:
        mode, label = "multi", "5.1"
    else:
        mode, label = "multi", f"{channels} кан."
    try:
        duration = float(info.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    title = str(tags.get("title") or path.stem)
    artist = str(tags.get("album_artist") or tags.get("artist") or "")
    album = str(tags.get("album") or path.stem)
    date = str(tags.get("date") or "")
    genre = str(tags.get("genre") or "")
    track = Track(
        number=1,
        title=title,
        performer=str(tags.get("artist") or artist),
        duration_seconds=duration,
    )
    return Disc(
        source=str(path),
        kind="dsf",
        title=album,
        artist=artist,
        genre=genre,
        date=date,
        areas=[Area(index=0, mode=mode, label=label, channels=channels, tracks=[track])],
    )
