from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from kedr.models import KedrError


class DialogUnavailable(KedrError):
    pass


_FILE_SCRIPT = """
try
    set picked to choose file with prompt "Выберите SACD ISO или DSF"
    return POSIX path of picked
on error
    return ""
end try
"""

_FOLDER_SCRIPT = """
try
    set picked to choose folder with prompt "Куда сохранить FLAC"
    return POSIX path of picked
on error
    return ""
end try
"""


def choose(kind: str) -> str | None:
    if kind not in {"iso", "folder"}:
        raise KedrError("Неизвестный диалог.")
    if sys.platform == "darwin":
        return _osascript(_FILE_SCRIPT if kind == "iso" else _FOLDER_SCRIPT)
    if os.environ.get("DISPLAY") and shutil.which("zenity"):
        return _zenity(kind)
    raise DialogUnavailable(
        "Окно выбора файла доступно в приложении на Mac. Вставьте путь вручную."
    )


def reveal(raw: str) -> None:
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise KedrError("Этой папки уже нет.")
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
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


def _zenity(kind: str) -> str | None:
    cmd = ["zenity", "--file-selection", "--title=Кедр"]
    if kind == "folder":
        cmd.append("--directory")
    else:
        cmd.extend(["--file-filter=SACD и DSF | *.iso *.ISO *.dsf *.DSF"])
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    path = (completed.stdout or "").strip()
    if completed.returncode != 0 or not path:
        return None
    return path
