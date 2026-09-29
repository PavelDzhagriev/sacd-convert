"""Короткий стерео DSF с синусом, чтобы проверять перевод в FLAC без SACD ISO."""

from __future__ import annotations

import math
import struct
from pathlib import Path

DSD_RATE = 2_822_400
BLOCK = 4096


def write_tone_dsf(path: Path, seconds: float = 0.3, frequency: float = 440.0) -> None:
    count = int(DSD_RATE * seconds)
    count -= count % 8
    left = _modulate(frequency, count, 0.0)
    right = _modulate(frequency, count, 0.4)
    left = _pad(left)
    right = _pad(right)
    payload = bytearray()
    for offset in range(0, len(left), BLOCK):
        payload += left[offset : offset + BLOCK]
        payload += right[offset : offset + BLOCK]

    def u32(value: int) -> bytes:
        return struct.pack("<I", value)

    def u64(value: int) -> bytes:
        return struct.pack("<Q", value)

    fmt_body = b"".join(
        (
            u32(1),
            u32(0),
            u32(2),
            u32(2),
            u32(DSD_RATE),
            u32(1),
            u64(count),
            u32(BLOCK),
            u32(0),
        )
    )
    fmt_chunk = b"fmt " + u64(12 + len(fmt_body)) + fmt_body
    data_chunk = b"data" + u64(12 + len(payload)) + payload
    body = b"DSD " + u64(28) + u64(0) + u64(0) + fmt_chunk + data_chunk
    body = b"DSD " + u64(28) + u64(len(body)) + u64(0) + fmt_chunk + data_chunk
    path.write_bytes(body)


def _modulate(frequency: float, count: int, phase: float) -> bytes:
    accumulator = 0.0
    bits = []
    for index in range(count):
        sample = 0.45 * math.sin(2 * math.pi * frequency * (index / DSD_RATE) + phase)
        accumulator += sample
        if accumulator >= 0:
            bits.append(1)
            accumulator -= 1.0
        else:
            bits.append(0)
            accumulator += 1.0
    out = bytearray()
    for index in range(0, count, 8):
        byte = 0
        for shift in range(8):
            if bits[index + shift]:
                byte |= 1 << (7 - shift)
        out.append(byte)
    return bytes(out)


def _pad(data: bytes) -> bytes:
    extra = len(data) % BLOCK
    if extra:
        data += bytes(BLOCK - extra)
    return data
