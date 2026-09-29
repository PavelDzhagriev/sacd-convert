import json
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from kedr.models import Area, Disc, EncodeSettings, KedrError, Track
from kedr.pipeline import _fit_lowpass, _interesting_error, _relax_dsf_layout, build_ffmpeg_cmd, convert
from kedr.probe import probe
from kedr.server import KedrServer
from kedr.jobs import JobStore
from kedr.tools import find_tool, ffprobe_path
from tests.dsfutil import write_tone_dsf


class ConvertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_dsf_becomes_24bit_flac_with_tone(self) -> None:
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg is not installed")
        source = self.root / "tone.dsf"
        write_tone_dsf(source, seconds=0.25, frequency=440)
        folder, files = convert(
            str(source),
            str(self.root / "albums"),
            EncodeSettings(rate=176400, bits=24, lowpass=40000, compression=5),
        )
        self.assertTrue(folder.is_dir())
        self.assertEqual(len(files), 1)
        info = _probe(files[0])
        stream = info["streams"][0]
        self.assertEqual(stream["codec_name"], "flac")
        self.assertEqual(int(stream["sample_rate"]), 176400)
        self.assertEqual(int(stream["bits_per_raw_sample"]), 24)
        self.assertEqual(info["format"]["tags"]["title"], "tone")
        self.assertGreater(_magnitude(files[0], 440), 0.05)
        self.assertLess(_magnitude(files[0], 1000), 0.01)

    def test_command_uses_soxr_when_available(self) -> None:
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg is not installed")
        cmd = build_ffmpeg_cmd(
            Path("in.dsf"),
            Path("out.flac"),
            EncodeSettings(),
            {"title": "Весна"},
        )
        text = " ".join(cmd)
        self.assertIn("aresample=", text)
        self.assertIn("precision=20", text)
        self.assertIn("precision=f64", text)
        self.assertIn("bits_per_raw_sample:a", text)
        self.assertIn("-map 0:a:0", text)
        self.assertIn("title=Весна", text)

    def test_bad_iso_is_explained(self) -> None:
        if find_tool("KEDR_SACD_EXTRACT", "sacd_extract") is None:
            self.skipTest("sacd_extract is not built")
        fake = self.root / "not-sacd.iso"
        fake.write_text("this is not a scarletbook image", encoding="utf-8")
        with self.assertRaises(KedrError) as caught:
            probe(str(fake))
        self.assertIn("SACD", str(caught.exception))

    def test_http_converts_dsf(self) -> None:
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg is not installed")
        source = self.root / "http-tone.dsf"
        write_tone_dsf(source, seconds=0.2, frequency=440)
        output = self.root / "http-out"
        server = KedrServer(("127.0.0.1", 0), JobStore())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"

        page = urllib.request.urlopen(base + "/", timeout=5)
        self.assertIn("Кедр", page.read().decode())
        health = _json(base + "/api/health")
        self.assertTrue(health["ffmpeg"]["ok"])

        disc = _json(base + "/api/probe", {"path": str(source)})
        self.assertEqual(disc["kind"], "dsf")
        self.assertEqual(disc["areas"][0]["tracks"][0]["title"], "http-tone")

        job = _json(
            base + "/api/convert",
            {
                "path": str(source),
                "output_dir": str(output),
                "mode": "stereo",
                "tracks": [],
                "rate": 88200,
                "bits": 16,
                "lowpass": 30000,
                "compression": 5,
            },
        )
        seen = job
        for _ in range(80):
            if seen["status"] != "running":
                break
            import time

            time.sleep(0.25)
            seen = _json(f"{base}/api/jobs/{job['id']}")
        self.assertEqual(seen["status"], "done", seen)
        flac = Path(seen["files"][0])
        self.assertTrue(flac.is_file())
        info = _probe(flac)
        self.assertEqual(int(info["streams"][0]["sample_rate"]), 88200)

    def test_mp3_rejects_hires_rate(self) -> None:
        settings = EncodeSettings(format="mp3", rate=176400, lowpass=20000, bitrate=320)
        with self.assertRaises(KedrError) as caught:
            settings.validate()
        self.assertIn("44,1", str(caught.exception))

    def test_mp3_command_uses_lame(self) -> None:
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg is not installed")
        cmd = build_ffmpeg_cmd(
            Path("in.dsf"),
            Path("out.mp3"),
            EncodeSettings(format="mp3", rate=44100, lowpass=20000, bitrate=320),
            {"title": "Весна"},
        )
        text = " ".join(cmd)
        self.assertIn("libmp3lame", text)
        self.assertIn("-b:a 320k", text)
        self.assertIn("osr=44100", text)
        self.assertNotIn("bits_per_raw_sample", text)

    def test_dsf_becomes_mp3(self) -> None:
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg is not installed")
        source = self.root / "tone.dsf"
        write_tone_dsf(source, seconds=0.2, frequency=440)
        _folder, files = convert(
            str(source),
            str(self.root / "albums"),
            EncodeSettings(format="mp3", rate=44100, lowpass=20000, bitrate=320),
        )
        self.assertEqual(files[0].suffix, ".mp3")
        stream = _probe(files[0])["streams"][0]
        self.assertEqual(stream["codec_name"], "mp3")
        self.assertEqual(int(stream["sample_rate"]), 44100)
        self.assertEqual(int(stream["channels"]), 2)

    def test_mp3_refuses_multichannel(self) -> None:
        disc = Disc(
            source="ignored.dsf",
            kind="dsf",
            title="Зал",
            artist="Кедр",
            areas=[
                Area(
                    index=0,
                    mode="multi",
                    label="5.1",
                    channels=6,
                    tracks=[Track(number=1, title="Зал", duration_seconds=1)],
                )
            ],
        )
        with patch("kedr.pipeline.probe", return_value=disc):
            with self.assertRaises(KedrError) as caught:
                convert(
                    "ignored.dsf",
                    str(self.root),
                    EncodeSettings(format="mp3", rate=44100, lowpass=20000, bitrate=320),
                    mode="multi",
                )
        self.assertIn("FLAC", str(caught.exception))

    def test_ffmpeg_trailer_is_not_the_reason(self) -> None:
        text = _interesting_error(
            [
                "[in#0] Channel count mismatch",
                "Error opening input file x.dsf.",
                "Conversion failed!",
            ]
        )
        self.assertIn("mismatch", text)
        text = _interesting_error(
            [
                "[Parsed_lowpass_0] Invalid frequency and/or width!",
                "[af#0:0] Terminating thread with return code -22 (Invalid argument)",
            ]
        )
        self.assertIn("frequency", text)

    def test_lowpass_stays_under_pcm_nyquist(self) -> None:
        import struct

        source = self.root / "rate.dsf"
        write_tone_dsf(source, seconds=0.05, frequency=440)
        data = bytearray(source.read_bytes())
        struct.pack_into("<I", data, 56, 352800)
        source.write_bytes(data)
        self.assertLess(_fit_lowpass(40000, source), 22050)
        self.assertEqual(_fit_lowpass(40000, self.root / "tone-missing.dsf"), 40000)

    def test_dsf_channel_type_cleared_when_it_disagrees(self) -> None:
        import struct

        source = self.root / "layout.dsf"
        write_tone_dsf(source, seconds=0.05, frequency=440)
        data = bytearray(source.read_bytes())
        struct.pack_into("<I", data, 52, 6)
        source.write_bytes(data)
        _relax_dsf_layout(source)
        channel_type, channels = struct.unpack_from("<II", source.read_bytes(), 48)
        self.assertEqual(channel_type, 0)
        self.assertEqual(channels, 6)
        _relax_dsf_layout(source)
        self.assertEqual(struct.unpack_from("<I", source.read_bytes(), 48)[0], 0)


def _json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())


def _probe(path: Path) -> dict:
    completed = subprocess.run(
        [str(ffprobe_path()), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _magnitude(path: Path, frequency: float) -> float:
    raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-"],
    )
    import array
    import math

    samples = array.array("f")
    samples.frombytes(raw[: len(raw) // 4 * 4])
    step = 4
    series = samples[::step]
    rate = 176400 / step
    real = 0.0
    imag = 0.0
    omega = 2 * math.pi * frequency / rate
    for index, sample in enumerate(series):
        real += sample * math.cos(omega * index)
        imag -= sample * math.sin(omega * index)
    return math.hypot(real, imag) / max(1, len(series))


if __name__ == "__main__":
    unittest.main()
