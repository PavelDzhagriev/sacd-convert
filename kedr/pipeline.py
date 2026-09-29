from __future__ import annotations

import re
import shutil
import threading
import uuid
from pathlib import Path

from kedr.models import Area, Cancelled, Disc, EncodeSettings, KedrError, Track
from kedr.naming import album_dirname, track_filename
from kedr.probe import probe, resolve_source
from kedr.tools import ProcSlot, ffmpeg_has_lame, ffmpeg_has_soxr, ffmpeg_path, run_piped, sacd_extract_path

_COMPLETED = re.compile(r"Completed:\s*(\d+)%")
_TOTAL = re.compile(r"Total:\s*(\d+)%")
_OUT_TIME = re.compile(r"out_time=(\d+):(\d+):(\d+(?:\.\d+)?)")
_FILE_NUMBER = re.compile(r"^(\d{2,3})\b")


class Reporter:
    def phase(self, phase: str, message: str) -> None:
        return None

    def extract_percent(self, value: float) -> None:
        return None

    def track(self, number: int, status: str, percent: float | None = None, path: str | None = None) -> None:
        return None

    def should_stop(self) -> bool:
        return False


def convert(
    source: str,
    output_dir: str,
    settings: EncodeSettings,
    mode: str = "stereo",
    track_numbers: list[int] | None = None,
    reporter: Reporter | None = None,
    stop: threading.Event | None = None,
    slot: ProcSlot | None = None,
) -> tuple[Path, list[Path]]:
    settings.validate()
    report = reporter or Reporter()
    stop = stop or threading.Event()
    slot = slot or ProcSlot()
    disc = probe(source, stop, slot)
    if disc.kind == "iso":
        area = disc.area(mode)
    else:
        area = disc.areas[0]
    chosen = _select_tracks(area, track_numbers)
    if not chosen:
        raise KedrError("Не выбрано ни одной дорожки.")
    if settings.format == "mp3" and area.channels > 2:
        raise KedrError("MP3 хранит только моно и стерео. Для многоканальной зоны выберите FLAC.")

    destination_root = _output_dir(output_dir)
    album_dir = destination_root / album_dirname(disc, area)
    album_dir.mkdir(parents=True, exist_ok=True)
    for track in chosen:
        report.track(track.number, "pending", 0)

    work = destination_root / f".kedr-work-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True)
    written: list[Path] = []
    try:
        sources = _materialize(disc, area, chosen, work, report, stop, slot)
        report.phase("encode", f"Пишу {settings.label}")
        for track in chosen:
            if stop.is_set():
                raise Cancelled()
            src = sources[track.number]
            target = album_dir / track_filename(track.number, track.title, settings.suffix)
            report.track(track.number, "encoding", 0)
            _encode(src, target, disc, area, track, settings, report, stop, slot)
            written.append(target)
            report.track(track.number, "done", 100, str(target))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    report.phase("done", "Готово")
    return album_dir, written


def build_ffmpeg_cmd(
    src: Path,
    dst: Path,
    settings: EncodeSettings,
    metadata: dict[str, str],
) -> list[str]:
    filters: list[str] = []
    if settings.lowpass:
        filters.append(f"lowpass=f={settings.lowpass}:poles=2")
    if ffmpeg_has_soxr():
        resample = (
            "aresample="
            f"resampler=soxr:precision=28:osr={settings.rate}:dither_method=triangular"
        )
    else:
        resample = f"aresample=osr={settings.rate}:dither_method=triangular"
    filters.append(resample)
    cmd = [
        str(ffmpeg_path()),
        "-y",
        "-hide_banner",
        "-i",
        str(src),
        "-af",
        ",".join(filters),
    ]
    cmd.extend(_codec_args(settings))
    cmd.extend(["-map_metadata", "-1"])
    for key, value in metadata.items():
        if value:
            cmd.extend(["-metadata", f"{key}={value.replace(chr(10), ' ')}"])
    cmd.extend(["-progress", "pipe:1", "-nostats", str(dst)])
    return cmd


def _codec_args(settings: EncodeSettings) -> list[str]:
    if settings.format == "mp3":
        if not ffmpeg_has_lame():
            raise KedrError(
                "В ffmpeg нет кодировщика LAME. На Mac: brew reinstall ffmpeg."
            )
        return ["-c:a", "libmp3lame", "-b:a", f"{settings.bitrate}k", "-id3v2_version", "3"]
    args = ["-c:a", "flac", "-compression_level", str(settings.compression)]
    if settings.bits == 24:
        args.extend(["-sample_fmt", "s32", "-bits_per_raw_sample", "24"])
    else:
        args.extend(["-sample_fmt", "s16"])
    return args


def _output_dir(raw: str) -> Path:
    if not raw or not raw.strip():
        raise KedrError("Укажите папку, куда сохранить файлы.")
    path = Path(raw.strip()).expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise KedrError("Папка назначения оказалась файлом.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _select_tracks(area: Area, numbers: list[int] | None) -> list[Track]:
    if not numbers:
        return list(area.tracks)
    wanted = set(numbers)
    chosen = [track for track in area.tracks if track.number in wanted]
    missing = wanted - {track.number for track in chosen}
    if missing:
        listed = ", ".join(str(number) for number in sorted(missing))
        raise KedrError(f"На диске нет дорожек: {listed}.")
    return chosen


def _materialize(
    disc: Disc,
    area: Area,
    tracks: list[Track],
    work: Path,
    report: Reporter,
    stop: threading.Event,
    slot: ProcSlot,
) -> dict[int, Path]:
    if disc.kind != "iso":
        report.phase("encode", "DSD-файл уже извлечён")
        return {tracks[0].number: resolve_source(disc.source)}

    report.phase("extract", "Извлекаю DSD из образа")
    for track in tracks:
        report.track(track.number, "extracting", 0)
    binary = sacd_extract_path()
    cmd = [str(binary), "-s", "-c", "-o", str(work), "-i", disc.source]
    cmd.append("-2" if area.mode == "stereo" else "-m")
    if len(tracks) != len(area.tracks):
        cmd.extend(["-t", ",".join(str(track.number) for track in tracks)])

    def on_line(line: str) -> None:
        total = _TOTAL.search(line)
        completed = _COMPLETED.search(line)
        if total:
            report.extract_percent(float(total.group(1)))
        elif completed:
            report.extract_percent(float(completed.group(1)))

    code, tail = run_piped(cmd, on_line, stop, slot, cwd=work)
    files = [path for path in work.rglob("*") if path.suffix.lower() == ".dsf"]
    if not files:
        detail = _interesting_error(tail) or "sacd_extract не создал DSF."
        raise KedrError(detail)
    if code not in (0, None) and len(files) < len(tracks):
        detail = _interesting_error(tail) or f"sacd_extract завершился с кодом {code}."
        raise KedrError(detail)

    by_number: dict[int, Path] = {}
    for path in files:
        match = _FILE_NUMBER.match(path.name)
        if match:
            by_number[int(match.group(1))] = path
    missing = [track.number for track in tracks if track.number not in by_number]
    if missing and len(files) == len(tracks):
        ordered = sorted(files, key=lambda item: item.name)
        by_number = {track.number: path for track, path in zip(tracks, ordered)}
        missing = []
    if missing:
        names = ", ".join(path.name for path in files[:8])
        raise KedrError(f"Не нашёл DSF для дорожек {missing}. В папке: {names}.")
    report.extract_percent(100)
    return by_number


def _encode(
    src: Path,
    dst: Path,
    disc: Disc,
    area: Area,
    track: Track,
    settings: EncodeSettings,
    report: Reporter,
    stop: threading.Event,
    slot: ProcSlot,
) -> None:
    metadata = {
        "title": track.title or f"Дорожка {track.number}",
        "artist": track.performer or disc.artist,
        "albumartist": disc.artist,
        "album": disc.title,
        "track": f"{track.number}/{len(area.tracks)}",
        "date": disc.year,
        "genre": disc.genre,
        "composer": track.composer,
        "isrc": track.isrc,
        "comment": f"{'SACD ISO' if disc.kind == 'iso' else 'DSF'} → PCM {settings.label}, Кедр",
    }
    cmd = build_ffmpeg_cmd(src, dst, settings, metadata)
    duration = track.duration_seconds

    def on_line(line: str) -> None:
        match = _OUT_TIME.search(line)
        if not match or duration <= 0:
            return
        hours, minutes, seconds = match.groups()
        elapsed = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        report.track(track.number, "encoding", min(99, elapsed / duration * 100))

    try:
        code, tail = run_piped(cmd, on_line, stop, slot)
    except Cancelled:
        dst.unlink(missing_ok=True)
        raise
    if code != 0 or not dst.is_file() or dst.stat().st_size == 0:
        if dst.exists():
            dst.unlink()
        detail = _interesting_error(tail) or f"ffmpeg завершился с кодом {code}."
        raise KedrError(f"Дорожка {track.number}: {detail}")


_NOISE = (
    "output not set to byte oriented",
    "output not set to wide",
    "program terminates",
)


def _interesting_error(tail: list[str]) -> str:
    for line in reversed(tail):
        lowered = line.lower()
        if any(noise in lowered for noise in _NOISE):
            continue
        if any(word in lowered for word in ("error", "can't", "cannot", "failed")):
            return line[:240]
    return ""
