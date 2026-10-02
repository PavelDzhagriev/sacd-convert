from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from kedr.models import KedrError


class DialogUnavailable(KedrError):
    pass


_PROMPTS = {
    "ru": {
        "file": "Выберите SACD ISO или DSF",
        "folder": "Папка для альбомов",
        "filter": "SACD и DSD",
    },
    "en": {
        "file": "Choose a SACD ISO or DSF",
        "folder": "Album folder",
        "filter": "SACD and DSD",
    },
}


def _script(kind: str, locale: str) -> str:
    prompt = _PROMPTS[locale]["file" if kind == "iso" else "folder"]
    noun = "file" if kind == "iso" else "folder"
    return f"""
try
    set picked to choose {noun} with prompt "{prompt}"
    return POSIX path of picked
on error
    return ""
end try
"""


def choose(kind: str, locale: str = "ru") -> str | None:
    if kind not in {"iso", "folder"}:
        raise KedrError("Неизвестный диалог.")
    lang = locale if locale in _PROMPTS else "en"
    if sys.platform == "darwin":
        return _osascript(_script(kind, lang))
    if os.environ.get("DISPLAY") and shutil.which("zenity"):
        return _zenity(kind, lang)
    raise DialogUnavailable(
        "Окно выбора файла доступно в настольном приложении. Вставьте путь вручную."
    )


def reveal(raw: str) -> None:
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise KedrError("Этой папки уже нет.")
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    if sys.platform == "win32":
        os.startfile(path)
        return
    opener = shutil.which("xdg-open")
    if opener and os.environ.get("DISPLAY"):
        subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    raise DialogUnavailable("Открыть папку из этой среды нельзя. Путь есть в строке результата.")


def _osascript(script: str) -> str | None:
    completed = subprocess.run(
        ["osascript"],
        input=script,
        text=True,
        capture_output=True,
        check=False,
    )
    path = (completed.stdout or "").strip()
    if not path:
        return None
    return path


def _zenity(kind: str, locale: str) -> str | None:
    title = _PROMPTS[locale]["file" if kind == "iso" else "folder"]
    cmd = ["zenity", "--file-selection", f"--title={title}"]
    if kind == "folder":
        cmd.append("--directory")
    else:
        label = _PROMPTS[locale]["filter"]
        cmd.extend([f"--file-filter={label} | *.iso *.ISO *.dsf *.DSF"])
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    path = (completed.stdout or "").strip()
    if completed.returncode != 0 or not path:
        return None
    return path
