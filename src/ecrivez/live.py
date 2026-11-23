"""Record in closed parts and transcribe each part while the next one records.

Every part is a complete file on disk, and each transcribed part gets its own text file,
so a crash or power cut loses at most the part being recorded; an interrupted session is
picked up again (transcription then assembly) the next time it is opened.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ecrivez import audio
from ecrivez.writer import Run, ToolError, run_tool

PART_SECONDS = 120
PARTS = "parts"
PART_SUFFIXES = (".flac", ".webm", ".ogg", ".m4a")
TRANSCRIPT = "transcription.txt"
INAUDIBLE_PART = "[tranche inaudible]"
BROKEN_PART = "[tranche illisible : enregistrement interrompu]"
RETRY_SECONDS = 15.0


def record_command(parts: Path, seconds: int = PART_SECONDS, start: int = 0) -> list[str]:
    argv = ["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "pulse", "-i", "default"]
    argv += ["-ac", "1", "-ar", "16000", "-c:a", "flac"]
    argv += ["-f", "segment", "-segment_time", str(seconds), "-reset_timestamps", "1"]
    argv += ["-segment_format_options", "flush_packets=1", "-segment_start_number", str(start)]
    return [*argv, str(parts / "part%03d.flac")]


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


class Session:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.parts_dir = folder / PARTS

    def parts(self) -> list[Path]:
        found = self.parts_dir.glob("part*") if self.parts_dir.exists() else []
        return sorted(p for p in found if p.suffix in PART_SUFFIXES)

    def pending(self, recording: bool) -> list[Path]:
        parts = self.parts()
        if recording:
            parts = parts[:-1]  # the last one is still being written
        return [p for p in parts if not p.with_suffix(".txt").exists()]

    def texts(self) -> list[str]:
        return [
            p.with_suffix(".txt").read_text(encoding="utf-8")
            for p in self.parts()
            if p.with_suffix(".txt").exists()
        ]

    def transcript(self) -> str:
        if not self.parts_dir.exists():
            path = self.folder / TRANSCRIPT
            return path.read_text(encoding="utf-8").strip() if path.exists() else ""
        return "\n".join(t.strip() for t in self.texts() if t.strip()).strip()

    def context(self, part: Path) -> str:
        previous = [p for p in self.parts() if p < part]
        for p in reversed(previous):
            ctx = p.with_suffix(".ctx")
            if ctx.exists():
                return ctx.read_text(encoding="utf-8")
        return ""

    def store(self, part: Path, text: str | None, raw: str, empty: str = INAUDIBLE_PART) -> None:
        if text is not None:
            _write_atomic(part.with_suffix(".ctx"), audio.context_of(raw))
        _write_atomic(part.with_suffix(".txt"), (text or empty) + "\n")
        _write_atomic(self.folder / TRANSCRIPT, self.transcript() + "\n")

    @property
    def lock(self) -> Path:
        return self.folder / ".verrou"

    def take(self) -> None:
        self.lock.write_text(str(os.getpid()), encoding="utf-8")

    def release(self) -> None:
        self.lock.unlink(missing_ok=True)

    def busy(self) -> bool:
        """Another live process (recording or transcribing) holds this session."""
        try:
            pid = int(self.lock.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if pid == os.getpid():
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def audio(self) -> Path | None:
        return next(iter(sorted(self.folder.glob("audio.*"))), None)

    def assemble(self, run: Run = run_tool) -> Path:
        """Join the parts into one audio file, then drop them (only once all are transcribed).

        Parts that all share a compressed format (a phone's webm) are joined as they are:
        decoding them to FLAC would make the file about ten times larger.
        """
        parts = [
            p
            for p in self.parts()
            if p.stat().st_size > 0
            and p.with_suffix(".txt").read_text(encoding="utf-8").strip() != BROKEN_PART
        ]
        suffixes = {p.suffix for p in parts}
        dest = self.folder / "audio.flac"
        if parts:
            listing = self.parts_dir / "liste.txt"
            listing.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
            argv = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0"]
            argv += ["-i", str(listing)]
            same = suffixes.pop() if len(suffixes) == 1 else ".flac"
            if same != ".flac":
                kept = self.folder / f"audio{same}"
                try:
                    run([*argv, "-c", "copy", str(kept)], None)
                except ToolError:
                    kept.unlink(missing_ok=True)  # a half-written join is not an audio file
                if kept.exists() and kept.stat().st_size > 0:
                    dest = kept
                else:
                    kept.unlink(missing_ok=True)
            if dest.suffix == ".flac":
                run([*argv, "-c:a", "flac", str(dest)], None)
            if not dest.exists() or dest.stat().st_size == 0:
                raise ToolError("ffmpeg", "assemblage de l'audio impossible")
        _write_atomic(self.folder / TRANSCRIPT, self.transcript() + "\n")
        for f in self.parts_dir.iterdir():
            f.unlink()
        self.parts_dir.rmdir()
        return dest


def unfinished_sessions(root: Path) -> list[Session]:
    found = [Session(p.parent) for p in sorted((root / "sorties").glob(f"*/*/{PARTS}"))]
    return [s for s in found if not s.busy()]


class BrokenPart(Exception):
    """The part's audio cannot be decoded (cut off by a crash): retrying will not help."""


TranscribePart = Callable[[Path, str], tuple[str | None, str]]


def online_transcriber(
    hint: str, env: Mapping[str, str] = os.environ, run: Run = run_tool
) -> TranscribePart:
    prompt = audio.online_prompt(hint)

    def transcribe(part: Path, previous: str) -> tuple[str | None, str]:
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "part.mp3"
            try:
                audio.to_mp3(part, mp3, run)
            except ToolError as e:
                raise BrokenPart(str(e)) from None
            if not mp3.exists() or mp3.stat().st_size == 0:
                raise BrokenPart("audio vide")
            return audio.transcribe_part(mp3, prompt, previous, env)

    return transcribe


class Worker(threading.Thread):
    """Transcribes closed parts as they appear; retries forever on errors; then assembles."""

    def __init__(
        self,
        session: Session,
        transcribe: TranscribePart,
        notify: Callable[[str], None],
        recording: threading.Event,
        run: Run = run_tool,
        retry: float = RETRY_SECONDS,
        poll: float = 1.0,
        hold: threading.Event | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.session = session
        self.transcribe = transcribe
        self.notify = notify
        self.recording = recording
        self.run_tool = run
        self.retry = retry
        self.poll = poll
        self.hold = hold  # while set, a stopped session is transcribed but not assembled
        self.done = threading.Event()
        self.stop = threading.Event()  # leave at once, touching nothing (server shutdown)
        self.audio: Path | None = None
        self.trouble = ""  # why the last try failed; empty again once something goes through

    def run(self) -> None:
        while True:
            if self.stop.is_set():
                self.done.set()
                return
            still_recording = self.recording.is_set()
            pending = self.session.pending(recording=still_recording)
            if not pending:
                if not still_recording and not (self.hold and self.hold.is_set()):
                    break
                self.stop.wait(self.poll)
                continue
            part = pending[0]
            try:
                text, raw = self.transcribe(part, self.session.context(part))
            except BrokenPart:
                self.session.store(part, None, "", BROKEN_PART)
                self.notify("tranche illisible ignorée")
                continue
            except (ToolError, OSError) as e:
                self.trouble = str(e)
                self.notify(f"Transcription en attente ({e}), nouvel essai dans un instant")
                self.stop.wait(self.retry)
                continue
            self.trouble = ""
            if part not in self.session.pending(recording=self.recording.is_set()):
                continue  # recording resumed into this part meanwhile: transcribe it again later
            self.session.store(part, text, raw)
            self.notify("tranche transcrite")
        try:
            self.audio = self.session.assemble(self.run_tool)
            self.notify("terminé")
        except (ToolError, OSError) as e:
            self.trouble = str(e)
            self.notify(f"Assemblage de l'audio impossible ({e}) ; les tranches sont gardées")
        self.session.release()
        self.done.set()


def _spawn(argv: list[str]) -> Any:
    try:
        return subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise ToolError(argv[0], "programme introuvable") from None


class Recorder:
    def __init__(
        self,
        session: Session,
        spawn: Callable[[list[str]], Any] = _spawn,
        seconds: int = PART_SECONDS,
    ) -> None:
        self.session = session
        self.spawn = spawn
        self.seconds = seconds
        self.proc: Any = None

    def start(self, settle: float = 1.0) -> None:
        """Start (or restart after a failure) without overwriting the parts already there."""
        self.session.parts_dir.mkdir(parents=True, exist_ok=True)
        self.session.take()
        start = len(self.session.parts())
        self.proc = self.spawn(record_command(self.session.parts_dir, self.seconds, start))
        time.sleep(settle)
        if self.proc.poll() is not None:
            detail = (self.proc.stderr.read() or b"").decode(errors="replace").strip()
            raise ToolError("ffmpeg", f"impossible d'ouvrir le micro {detail}".strip())

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.alive():
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
