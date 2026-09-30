import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocaleTests(unittest.TestCase):
    def test_catalogs_and_negotiation(self) -> None:
        page = (ROOT / "kedr" / "web" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "kedr" / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="locale"', page)
        self.assertIn("/i18n.js", page)
        self.assertIn("kedr-settings", app)
        self.assertIn("localePinned", app)
        subprocess.check_call(["node", "--check", str(ROOT / "kedr" / "web" / "i18n.js")])
        subprocess.check_call(["node", "--check", str(ROOT / "kedr" / "web" / "app.js")])
        subprocess.check_call(
            ["node", "-e", _SCRIPT],
            cwd=ROOT,
        )


_SCRIPT = r"""
const i18n = require("./kedr/web/i18n.js");
const ru = Object.keys(i18n.TEXT.ru).sort();
const en = Object.keys(i18n.TEXT.en).sort();
if (ru.join("\n") !== en.join("\n")) {
  const missingEn = ru.filter((key) => !en.includes(key));
  const missingRu = en.filter((key) => !ru.includes(key));
  throw new Error(`missing en: ${missingEn} missing ru: ${missingRu}`);
}
const cases = [
  [null, ["ru-RU"], "ru"],
  [null, ["de-DE", "fr"], "en"],
  [null, ["en-GB", "ru"], "en"],
  ["ru", ["en-US"], "ru"],
  ["en", ["ru-RU"], "en"],
  ["de", ["ru"], "ru"],
  [undefined, [], "en"],
  [null, ["ru_RU"], "ru"],
];
for (const [saved, tags, expected] of cases) {
  const got = i18n.negotiate(saved, tags);
  if (got !== expected) throw new Error(JSON.stringify({ saved, tags, got, expected }));
}
const english = i18n.mount("en");
const russian = i18n.mount("ru");
if (english.serverText("Дорожка 3: boom") !== "Track 3: boom") throw new Error("track");
if (english.serverText("Пишу MP3") !== "Writing MP3") throw new Error("write");
if (russian.serverText("Пишу MP3") !== "Пишу MP3") throw new Error("write ru");
if (english.areaLabel({ label: "Стерео", mode: "stereo", channels: 2 }) !== "Stereo") throw new Error("area");
if (english.areaLabel({ label: "5.1", mode: "multi", channels: 6 }) !== "5.1") throw new Error("5.1");
if (english.formatHz(176400) !== "176.4 kHz") throw new Error(english.formatHz(176400));
if (russian.formatHz(88200) !== "88,2 кГц") throw new Error(russian.formatHz(88200));
if (english.filesLabel(1) !== "1 file" || english.filesLabel(3) !== "3 files") throw new Error("files");
if (russian.filesLabel(1) !== "1 файл" || russian.filesLabel(2) !== "2 файла" || russian.filesLabel(5) !== "5 файлов") {
  throw new Error("files ru");
}
if (english.formatBytes(2 * 1024 ** 3) !== "2.0 GB") throw new Error(english.formatBytes(2 * 1024 ** 3));
if (russian.formatBytes(2 * 1024 ** 3) !== "2,0 ГБ") throw new Error(russian.formatBytes(2 * 1024 ** 3));
"""
