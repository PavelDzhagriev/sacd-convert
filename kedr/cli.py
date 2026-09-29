from __future__ import annotations

import argparse
import signal
import sys
import threading

from kedr import __version__
from kedr.models import EncodeSettings, KedrError
from kedr.naming import format_duration
from kedr.pipeline import Reporter, convert
from kedr.probe import describe, probe
from kedr.server import health, serve
from kedr.tools import ProcSlot


class CliReporter(Reporter):
    def __init__(self) -> None:
        self._extract = -1
        self._encode = ""

    def phase(self, phase: str, message: str) -> None:
        print(f"\n{message}", file=sys.stderr)

    def extract_percent(self, value: float) -> None:
        shown = int(value)
        if shown == self._extract:
            return
        self._extract = shown
        print(f"\rИзвлечение {shown:3d}%", end="", file=sys.stderr, flush=True)

    def track(self, number: int, status: str, percent: float | None = None, path: str | None = None) -> None:
        if status == "encoding" and percent is not None:
            label = f"{number}:{int(percent):3d}%"
            if label == self._encode:
                return
            self._encode = label
            print(f"\rFLAC, дорожка {number}: {int(percent):3d}%", end="", file=sys.stderr, flush=True)
        elif status == "done" and path:
            print(f"\n{path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command is None:
            serve(47631, False)
            return 0
        if args.command == "serve":
            serve(args.port, args.open)
            return 0
        if args.command == "info":
            return _info(args.source)
        if args.command == "tools":
            return _tools()
        if args.command == "convert":
            return _convert(args)
    except KedrError as exc:
        print(exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nОстановлено", file=sys.stderr)
        return 130
    print("Неизвестная команда.", file=sys.stderr)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kedr",
        description="Кедр переводит SACD ISO и DSF в PCM FLAC.",
    )
    parser.add_argument("--version", action="version", version=f"Кедр {__version__}")
    commands = parser.add_subparsers(dest="command")

    serve_cmd = commands.add_parser("serve", help="Локальное окно утилиты")
    serve_cmd.add_argument("--port", type=int, default=47631)
    serve_cmd.add_argument("--open", action="store_true", help="Открыть браузер")

    info = commands.add_parser("info", help="Показать оглавление")
    info.add_argument("source")

    convert_cmd = commands.add_parser("convert", help="Преобразовать в FLAC")
    convert_cmd.add_argument("source")
    convert_cmd.add_argument("-o", "--output", required=True, help="Папка для альбома")
    convert_cmd.add_argument("--mode", choices=("stereo", "multi"), default="stereo")
    convert_cmd.add_argument("--tracks", default="", help="Номера через запятую: 1,2,5")
    convert_cmd.add_argument("--rate", type=int, default=176400)
    convert_cmd.add_argument("--bits", type=int, default=24)
    convert_cmd.add_argument("--lowpass", type=int, default=40000)
    convert_cmd.add_argument("--compression", type=int, default=8)

    commands.add_parser("tools", help="Проверить ffmpeg и sacd_extract")
    return parser


def _info(source: str) -> int:
    disc = probe(source)
    payload = describe(disc)
    title = disc.title or "Без названия"
    artist = disc.artist or "Неизвестный исполнитель"
    print(f"{artist} — {title}")
    if disc.date or disc.catalog or disc.genre:
        print(" · ".join(part for part in (disc.date, disc.catalog, disc.genre) if part))
    for area in payload["areas"]:
        print(f"\n{area['label']} · {len(area['tracks'])} дор. · папка «{area['dirname']}»")
        for track in area["tracks"]:
            name = track["title"] or "Без названия"
            print(f"  {track['number']:02d}  {format_duration(track['duration_seconds']):>7}  {name}")
    return 0


def _convert(args: argparse.Namespace) -> int:
    numbers = None
    if args.tracks.strip():
        numbers = [int(part) for part in args.tracks.split(",") if part.strip()]
    settings = EncodeSettings(args.rate, args.bits, args.lowpass, args.compression)
    stop = threading.Event()
    slot = ProcSlot()

    def interrupt(signum, frame) -> None:
        stop.set()
        slot.kill()

    signal.signal(signal.SIGINT, interrupt)
    folder, _files = convert(
        args.source,
        args.output,
        settings,
        mode=args.mode,
        track_numbers=numbers,
        reporter=CliReporter(),
        stop=stop,
        slot=slot,
    )
    print(f"\nГотово: {folder}")
    return 0


def _tools() -> int:
    report = health()
    for name in ("ffmpeg", "sacd_extract"):
        item = report[name]
        state = "есть" if item["ok"] else "нет"
        extra = f"  {item['path']}" if item["ok"] else ""
        print(f"{name}: {state}{extra}")
    if not report["ffmpeg"]["ok"] or not report["sacd_extract"]["ok"]:
        print(report["hint"], file=sys.stderr)
        return 1
    return 0
