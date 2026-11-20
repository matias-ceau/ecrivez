"""Send the note to oneself with the user's own mail command."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from datetime import datetime

from ecrivez.writer import Run, run_tool

DEFAULT_COMMAND = "send_email.py"


def available(env: Mapping[str, str] = os.environ) -> bool:
    return shutil.which(env.get("ECRIVEZ_MAIL_COMMAND") or DEFAULT_COMMAND) is not None


def send(note: str, env: Mapping[str, str] = os.environ, run: Run = run_tool) -> None:
    """The subject carries only the date: nothing about the patient outside the body."""
    command = env.get("ECRIVEZ_MAIL_COMMAND") or DEFAULT_COMMAND
    subject = f"Note ecrivez {datetime.now():%Y-%m-%d %H:%M}"
    run([command, "-s", subject, "-c", note], None)
