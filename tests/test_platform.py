import subprocess
import unittest
from pathlib import Path

from kedr.tools import _OutputText, tool_file_names


ROOT = Path(__file__).resolve().parents[1]


class PlatformTests(unittest.TestCase):
    def test_windows_tool_names(self) -> None:
        self.assertEqual(tool_file_names("sacd_extract", "win32"), ["sacd_extract", "sacd_extract.exe"])
        self.assertEqual(tool_file_names("ffmpeg", "linux"), ["ffmpeg"])
        self.assertEqual(tool_file_names("sacd_extract.exe", "win32"), ["sacd_extract.exe"])

    def test_output_text_utf8_and_utf16(self) -> None:
        utf8 = _OutputText()
        lines = utf8.feed(b"frame=1\rframe=2\n")
        lines += utf8.finish()
        self.assertEqual(lines, ["frame=1", "frame=2"])

        payload = "Disc Information\nTitle: Album\n".encode("utf-16-le")
        wide = _OutputText()
        lines = wide.feed(payload[:7]) + wide.feed(payload[7:]) + wide.finish()
        self.assertEqual(lines, ["Disc Information", "Title: Album"])

    def test_windows_installer_is_present(self) -> None:
        script = (ROOT / "scripts" / "install-windows.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("MSYS2.MSYS2", script)
        self.assertIn("Gyan.FFmpeg", script)
        self.assertIn("build-sacd-extract.sh", script)
        self.assertIn("sacd_extract.exe", script)
        build = (ROOT / "scripts" / "build-sacd-extract.sh").read_text(encoding="utf-8")
        self.assertIn("sacd_extract.exe", build)
        self.assertIn("-lxml2 -static", build)
        main = (ROOT / "electron" / "main.js").read_text(encoding="utf-8")
        self.assertIn("taskkill", main)
        self.assertIn('command: "py"', main)

    def test_scripts_parse(self) -> None:
        subprocess.check_call(["bash", "-n", str(ROOT / "scripts" / "build-sacd-extract.sh")])
        subprocess.check_call(["bash", "-n", str(ROOT / "scripts" / "install-macos.sh")])
        subprocess.check_call(["node", "--check", str(ROOT / "electron" / "main.js")])
        subprocess.check_call(["node", "--check", str(ROOT / "electron" / "preload.js")])
