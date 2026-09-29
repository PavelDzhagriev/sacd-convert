#!/usr/bin/env python3
"""Рисует значок Кедра без внешних библиотек."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "kedr" / "web" / "icon.png"
SIZE = 256


def main() -> None:
    pixels = bytearray()
    for y in range(SIZE):
        pixels.append(0)
        for x in range(SIZE):
            pixels.extend(_pixel(x, y))
    OUT.write_bytes(_png(SIZE, SIZE, bytes(pixels)))


def _pixel(x: int, y: int) -> bytes:
    if _in_triangle(x, y, 40, 108, 34):
        return (227, 154, 75, 255)
    if _in_triangle(x, y, 78, 164, 56):
        return (232, 181, 109, 255)
    if _in_triangle(x, y, 118, 214, 76):
        return (240, 211, 164, 255)
    if 120 <= x <= 136 and 206 <= y <= 232:
        return (196, 132, 74, 255)
    return (28, 23, 18, 255)


def _in_triangle(x: int, y: int, apex: int, base: int, half: int) -> bool:
    if y < apex or y > base:
        return False
    span = (y - apex) / (base - apex)
    return abs(x - (SIZE / 2)) <= half * span


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    main()
