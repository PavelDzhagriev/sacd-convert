from __future__ import annotations

import re

from kedr.models import Area, Disc, KedrError, Track

_DURATION = re.compile(
    r"Duration:\s*(\d+):(\d+):(\d+)\s*\[mins:secs:frames\]"
)
_TITLE = re.compile(r"Title\[(\d+)\]:\s*(.*)$")
_PERFORMER = re.compile(r"Performer\[(\d+)\]:\s*(.*)$")
_COMPOSER = re.compile(r"Composer\[(\d+)\]:\s*(.*)$")
_AREA = re.compile(r"Area Information \[(\d+)\]")
_ISRC = re.compile(
    r"Country:\s*(\S+),\s*Owner:\s*(\S+),\s*Year:\s*(\S+),\s*Designation:\s*(\S+)"
)
_ISRC_INDEX = re.compile(r"ISRC Track \[(\d+)\]")


def parse_sacd_print(text: str, source: str) -> Disc:
    """Разбирает текст `sacd_extract -P`."""
    if "Can't read Master TOC" in text or "No valid ScarletBook" in text:
        raise KedrError(
            "Файл не похож на SACD ISO. Кедр читает образы Super Audio CD, "
            "не обычные CD, DVD или Blu-ray ISO."
        )
    if "Output not set to wide" in text and "Disc Information" not in text:
        raise KedrError(
            "sacd_extract не смог вывести текст в UTF-8. Нужна локаль UTF-8."
        )

    disc_title = ""
    album_title = ""
    disc_artist = ""
    album_artist = ""
    disc_genre = ""
    album_genre = ""
    disc_catalog = ""
    album_catalog = ""
    date = ""
    section = ""
    areas: list[Area] = []
    area: Area | None = None
    isrc_index: int | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Disc Information"):
            section = "disc"
            area = None
            continue
        if line.startswith("Album Information"):
            section = "album"
            area = None
            continue
        if line.startswith("Area count:"):
            section = ""
            continue

        area_match = _AREA.match(line)
        if area_match:
            section = "area"
            area = Area(index=int(area_match.group(1)), mode="multi", label="", channels=0)
            areas.append(area)
            isrc_index = None
            continue

        if section == "disc":
            if line.startswith("Creation date:"):
                date = _value(line)
            elif line.startswith("Title:"):
                disc_title = _value(line)
            elif line.startswith("Artist:"):
                disc_artist = _value(line)
            elif line.startswith("Disc Catalog Number:"):
                disc_catalog = _value(line)
            elif line.startswith("Disc Genre:"):
                disc_genre = _value(line)
            continue

        if section == "album":
            if line.startswith("Title:"):
                album_title = _value(line)
            elif line.startswith("Artist:"):
                album_artist = _value(line)
            elif line.startswith("Album Catalog Number:"):
                album_catalog = _value(line)
            elif line.startswith("Album Genre:"):
                album_genre = _value(line)
            continue

        if section != "area" or area is None:
            continue

        if line.startswith("Speaker config:"):
            speaker = _value(line) if ":" in line else line
            # «Speaker config: 2 Channel» — значение после двоеточия.
            speaker = line.split(":", 1)[1].strip()
            mode, label, channels = classify_speaker(speaker)
            area.speaker = speaker
            area.mode = mode
            area.label = label
            area.channels = channels
            continue

        title_match = _TITLE.match(line)
        if title_match:
            track = _track(area, int(title_match.group(1)))
            track.title = title_match.group(2).strip()
            continue
        performer_match = _PERFORMER.match(line)
        if performer_match:
            _track(area, int(performer_match.group(1))).performer = performer_match.group(2).strip()
            continue
        composer_match = _COMPOSER.match(line)
        if composer_match:
            _track(area, int(composer_match.group(1))).composer = composer_match.group(2).strip()
            continue
        duration_match = _DURATION.search(line)
        if duration_match:
            minutes, seconds, frames = (int(part) for part in duration_match.groups())
            target = area.tracks[-1] if area.tracks else _track(area, 0)
            target.duration_seconds = minutes * 60 + seconds + frames / 75
            continue
        isrc_head = _ISRC_INDEX.search(line)
        if isrc_head:
            isrc_index = int(isrc_head.group(1))
        isrc_match = _ISRC.search(line)
        if isrc_match and isrc_index is not None:
            country, owner, year, designation = isrc_match.groups()
            _track(area, isrc_index).isrc = f"{country}{owner}{year}{designation}"
            isrc_index = None

    if not areas or not any(item.tracks for item in areas):
        raise KedrError(
            "В выводе sacd_extract нет дорожек. Проверьте, что это полный образ SACD ISO."
        )

    return Disc(
        source=source,
        kind="iso",
        title=album_title or disc_title,
        artist=album_artist or disc_artist,
        genre=album_genre or disc_genre,
        date=date,
        catalog=album_catalog or disc_catalog,
        areas=areas,
    )


def classify_speaker(speaker: str) -> tuple[str, str, int]:
    text = speaker.strip().lower()
    if text.startswith("2"):
        return "stereo", "Стерео", 2
    if text.startswith("5"):
        return "multi", "5.0", 5
    if text.startswith("6"):
        return "multi", "5.1", 6
    return "multi", "Многоканальный", 0


def _value(line: str) -> str:
    return line.split(":", 1)[1].strip()


def _track(area: Area, index: int) -> Track:
    while len(area.tracks) <= index:
        area.tracks.append(Track(number=len(area.tracks) + 1))
    return area.tracks[index]
