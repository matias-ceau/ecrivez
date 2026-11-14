"""Recording (PipeWire) and local transcription (openai-whisper CLI)."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ecrivez.writer import Run, ToolError, run_tool

DEFAULT_MODEL = "large-v3-turbo"
HINT_LIMIT = 600
WAV_HEADER = 44


def _spawn(argv: list[str]) -> Any:
    try:
        return subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise ToolError(argv[0], "programme introuvable") from None


def record(
    dest: Path,
    wait: Callable[[], object] = input,
    spawn: Callable[[list[str]], Any] = _spawn,
    settle: float = 0.7,
) -> None:
    """Record the default microphone into `dest` until `wait()` returns."""
    proc = spawn(["pw-record", "--rate", "16000", "--channels", "1", str(dest)])
    time.sleep(settle)
    if proc.poll() is not None:
        raise ToolError("pw-record", "impossible d'ouvrir le micro (branché ? sélectionné ?)")
    try:
        wait()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)
    if not dest.exists() or dest.stat().st_size <= WAV_HEADER:
        raise ToolError("pw-record", "aucun son capté par le micro")


def to_flac(src: Path, dest: Path, run: Run = run_tool) -> None:
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), str(dest)], None)


def hint_from_lexicon(lexicon: str) -> str:
    hint = ""
    for line in lexicon.splitlines():
        term = line.strip().removeprefix("-").strip()
        if not term:
            continue
        candidate = f"{hint}, {term}" if hint else term
        if len(candidate) > HINT_LIMIT:
            break
        hint = candidate
    return hint


def transcribe(
    audio: Path, hint: str, env: Mapping[str, str] = os.environ, run: Run = run_tool
) -> str:
    model = env.get("ECRIVEZ_WHISPER_MODEL") or DEFAULT_MODEL
    with tempfile.TemporaryDirectory() as out:
        argv = ["whisper", str(audio), "--model", model, "--language", "fr"]
        argv += ["--output_format", "txt", "--output_dir", out, "--verbose", "False"]
        if hint:
            argv += ["--initial_prompt", hint]
        run(argv, None)
        result = Path(out) / f"{audio.stem}.txt"
        return result.read_text(encoding="utf-8").strip() if result.exists() else ""
