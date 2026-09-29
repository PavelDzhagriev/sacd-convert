from __future__ import annotations

import threading
import traceback
import uuid
from pathlib import Path

from kedr.models import Cancelled, EncodeSettings, KedrError, Track
from kedr.pipeline import Reporter, convert
from kedr.probe import probe
from kedr.tools import ProcSlot


class Job(Reporter):
    def __init__(self) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.status = "running"
        self.phase_name = "prepare"
        self.message = "Читаю образ"
        self.percent = 0.0
        self._extract_percent = 0.0
        self.error: str | None = None
        self.output_dir = ""
        self.files: list[str] = []
        self.tracks: list[dict] = []
        self.stop = threading.Event()
        self.slot = ProcSlot()
        self._lock = threading.Lock()

    def seed(self, tracks: list[Track]) -> None:
        with self._lock:
            self.tracks = [
                {
                    "number": track.number,
                    "title": track.title,
                    "status": "pending",
                    "percent": 0,
                    "path": None,
                }
                for track in tracks
            ]

    def phase(self, phase: str, message: str) -> None:
        with self._lock:
            self.phase_name = phase
            self.message = message
            if phase == "encode":
                self._extract_percent = 100
            self._recompute()

    def extract_percent(self, value: float) -> None:
        with self._lock:
            self._extract_percent = value
            self.phase_name = "extract"
            self._recompute()

    def track(
        self,
        number: int,
        status: str,
        percent: float | None = None,
        path: str | None = None,
    ) -> None:
        with self._lock:
            found = next((item for item in self.tracks if item["number"] == number), None)
            if found is None:
                found = {"number": number, "title": "", "status": status, "percent": 0, "path": None}
                self.tracks.append(found)
            found["status"] = status
            if percent is not None:
                found["percent"] = round(percent, 1)
            if path:
                found["path"] = path
            self._recompute()

    def should_stop(self) -> bool:
        return self.stop.is_set()

    def finish(self, output_dir: Path, files: list[Path]) -> None:
        with self._lock:
            self.status = "done"
            self.phase_name = "done"
            self.message = "Готово"
            self.percent = 100
            self.output_dir = str(output_dir)
            self.files = [str(path) for path in files]
            for item in self.tracks:
                if item["status"] != "error":
                    item["status"] = "done"
                    item["percent"] = 100

    def fail(self, message: str) -> None:
        with self._lock:
            self.status = "error"
            self.phase_name = "error"
            self.message = message
            self.error = message

    def mark_cancelled(self) -> None:
        with self._lock:
            self.status = "cancelled"
            self.phase_name = "cancelled"
            self.message = "Остановлено"

    def cancel(self) -> None:
        self.stop.set()
        self.slot.kill()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "phase": self.phase_name,
                "message": self.message,
                "percent": round(self.percent, 1),
                "error": self.error,
                "output_dir": self.output_dir,
                "files": list(self.files),
                "tracks": [dict(item) for item in self.tracks],
            }

    def _recompute(self) -> None:
        if self.phase_name == "done":
            self.percent = 100
            return
        count = len(self.tracks) or 1
        if self.phase_name == "extract":
            self.percent = min(40, self._extract_percent * 0.4)
            return
        progressed = 0.0
        for item in self.tracks:
            if item["status"] == "done":
                progressed += 1
            elif item["status"] == "encoding":
                progressed += float(item["percent"] or 0) / 100
        if self.phase_name == "encode":
            self.percent = min(99, 40 + 60 * progressed / count)
        else:
            self.percent = min(99, 100 * progressed / count)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job
            if len(self._jobs) > 40:
                stale = [key for key, item in self._jobs.items() if item.status != "running"]
                for key in stale[:-12]:
                    del self._jobs[key]

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)


def launch(
    store: JobStore,
    source: str,
    output_dir: str,
    settings: EncodeSettings,
    mode: str,
    track_numbers: list[int] | None,
) -> Job:
    settings.validate()
    disc = probe(source)
    area = disc.areas[0] if disc.kind != "iso" else disc.area(mode)
    if track_numbers:
        wanted = set(track_numbers)
        chosen = [track for track in area.tracks if track.number in wanted]
        missing = wanted - {track.number for track in chosen}
        if missing:
            listed = ", ".join(str(number) for number in sorted(missing))
            raise KedrError(f"На диске нет дорожек: {listed}.")
    else:
        chosen = list(area.tracks)
    if not chosen:
        raise KedrError("Не выбрано ни одной дорожки.")

    job = Job()
    job.seed(chosen)
    store.add(job)

    def run() -> None:
        try:
            folder, files = convert(
                source,
                output_dir,
                settings,
                mode=area.mode,
                track_numbers=[track.number for track in chosen],
                reporter=job,
                stop=job.stop,
                slot=job.slot,
            )
            job.finish(folder, files)
        except Cancelled:
            job.mark_cancelled()
        except KedrError as exc:
            job.fail(str(exc))
        except Exception as exc:
            traceback.print_exc()
            job.fail(f"Сбой преобразования: {exc}")

    threading.Thread(target=run, name=f"kedr-{job.id}", daemon=True).start()
    return job
