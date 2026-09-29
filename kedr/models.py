from __future__ import annotations

from dataclasses import dataclass, field


class KedrError(Exception):
    """Ошибка, которую можно показать человеку как есть."""


class Cancelled(KedrError):
    def __init__(self) -> None:
        super().__init__("Остановлено")


@dataclass
class Track:
    number: int
    title: str = ""
    performer: str = ""
    composer: str = ""
    isrc: str = ""
    duration_seconds: float = 0.0

    def to_json(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "performer": self.performer,
            "composer": self.composer,
            "isrc": self.isrc,
            "duration_seconds": round(self.duration_seconds, 3),
        }


@dataclass
class Area:
    index: int
    mode: str
    label: str
    channels: int
    speaker: str = ""
    tracks: list[Track] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return sum(track.duration_seconds for track in self.tracks)

    def to_json(self) -> dict:
        return {
            "index": self.index,
            "mode": self.mode,
            "label": self.label,
            "channels": self.channels,
            "speaker": self.speaker,
            "duration_seconds": round(self.duration_seconds, 3),
            "tracks": [track.to_json() for track in self.tracks],
        }


@dataclass
class Disc:
    source: str
    kind: str
    title: str = ""
    artist: str = ""
    genre: str = ""
    date: str = ""
    catalog: str = ""
    areas: list[Area] = field(default_factory=list)

    @property
    def year(self) -> str:
        head = self.date[:4]
        return head if len(head) == 4 and head.isdigit() else ""

    def area(self, mode: str) -> Area:
        for item in self.areas:
            if item.mode == mode:
                return item
        if mode == "stereo":
            raise KedrError("На этом диске нет стереофонической зоны.")
        raise KedrError("На этом диске нет многоканальной зоны.")

    def to_json(self) -> dict:
        return {
            "source": self.source,
            "kind": self.kind,
            "title": self.title,
            "artist": self.artist,
            "genre": self.genre,
            "date": self.date,
            "year": self.year,
            "catalog": self.catalog,
            "areas": [area.to_json() for area in self.areas],
        }


@dataclass
class EncodeSettings:
    rate: int = 176400
    bits: int = 24
    lowpass: int = 40000
    compression: int = 8

    def validate(self) -> None:
        if self.rate not in (88200, 176400, 352800):
            raise KedrError("Частота дискретизации: 88,2, 176,4 или 352,8 кГц.")
        if self.bits not in (16, 24):
            raise KedrError("Разрядность: 16 или 24 бита.")
        if not 0 <= self.compression <= 8:
            raise KedrError("Сжатие FLAC — от 0 до 8.")
        if self.lowpass < 0 or self.lowpass > 80000:
            raise KedrError("Частота среза должна быть от 0 до 80 кГц.")
        if self.lowpass and self.lowpass >= self.rate / 2:
            raise KedrError(
                "Срез выше частоты Найквиста для выбранной дискретизации. "
                "Уменьшите срез или поднимите частоту."
            )
