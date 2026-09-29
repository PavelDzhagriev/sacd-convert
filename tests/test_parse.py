import unittest
from pathlib import Path

from kedr.models import KedrError
from kedr.naming import album_dirname, format_duration, sanitize, track_filename
from kedr.parse import parse_sacd_print

FIXTURE = Path(__file__).parent / "fixtures" / "sample_print.txt"


class ParseTests(unittest.TestCase):
    def test_album_text_wins_and_areas_split(self) -> None:
        disc = parse_sacd_print(FIXTURE.read_text(encoding="utf-8"), "/tmp/vivaldi.iso")
        self.assertEqual(disc.title, "Времена года")
        self.assertEqual(disc.artist, "Антонио Вивальди")
        self.assertEqual(disc.date, "2019-11-02")
        self.assertEqual(disc.year, "2019")
        self.assertEqual(disc.catalog, "ALB-9")
        self.assertEqual(disc.genre, "Jazz")
        self.assertEqual(len(disc.areas), 2)
        stereo, multi = disc.areas
        self.assertEqual(stereo.mode, "stereo")
        self.assertEqual(stereo.label, "Стерео")
        self.assertEqual(stereo.channels, 2)
        self.assertEqual(stereo.tracks[0].title, "Весна")
        self.assertEqual(stereo.tracks[0].performer, "Камерный оркестр")
        self.assertEqual(stereo.tracks[0].composer, "Вивальди")
        self.assertEqual(stereo.tracks[0].isrc, "ITABC1900001")
        self.assertAlmostEqual(stereo.tracks[0].duration_seconds, 200.0)
        self.assertAlmostEqual(stereo.tracks[1].duration_seconds, 8 * 60 + 40 + 15 / 75)
        self.assertEqual(multi.mode, "multi")
        self.assertEqual(multi.label, "5.1")
        self.assertEqual(multi.channels, 6)
        self.assertEqual(album_dirname(disc, multi), "Антонио Вивальди — Времена года (5.1)")

    def test_plain_file_is_rejected(self) -> None:
        with self.assertRaises(KedrError):
            parse_sacd_print("scarletbook_open: Can't read Master TOC !!\n", "x.iso")

    def test_names(self) -> None:
        self.assertEqual(sanitize('a/b:c', "fallback"), "a b c")
        self.assertEqual(track_filename(3, ""), "03.flac")
        self.assertEqual(format_duration(65), "1:05")
        self.assertEqual(format_duration(3661), "1:01:01")


if __name__ == "__main__":
    unittest.main()
