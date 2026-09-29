from __future__ import annotations

import re

from kedr.models import Area, Disc

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_SPACE = re.compile(r"\s+")


def sanitize(name: str, fallback: str) -> str:
    cleaned = _SPACE.sub(" ", _UNSAFE.sub(" ", name)).strip(" .")
    return (cleaned[:80] or fallback).strip()


def album_dirname(disc: Disc, area: Area) -> str:
    artist = sanitize(disc.artist, "Неизвестный исполнитель")
    title = sanitize(disc.title, "Без названия")
    name = f"{artist} — {title}"
    if area.mode != "stereo":
        name += f" ({area.label})"
    return name


def track_filename(number: int, title: str, extension: str = "flac") -> str:
    suffix = extension.lstrip(".").lower() or "flac"
    safe = sanitize(title, "")
    if safe:
        return f"{number:02d} {safe}.{suffix}"
    return f"{number:02d}.{suffix}"


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_bytes(size: float) -> str:
    if size < 1024**2:
        return f"{size / 1024:.0f} КБ"
    if size < 1024**3:
        return f"{size / 1024**2:.0f} МБ"
    return f"{size / 1024**3:.1f} ГБ".replace(".", ",")
