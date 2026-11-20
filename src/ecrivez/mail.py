"""Send the note to oneself with the user's own mail command."""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping
from datetime import datetime

from ecrivez.writer import Run, run_tool

DEFAULT_COMMAND = "send_email.py"
# Loose on purpose, but never something the mail command could take for an option.
ADDRESS = re.compile(r"""[^\s@,;<>"'-][^\s@,;<>"']*@[^\s@,;<>"'.]+(\.[^\s@,;<>"'.]+)+""")


def valid(address: str) -> bool:
    return len(address) <= 254 and ADDRESS.fullmatch(address) is not None


def choices(env: Mapping[str, str] = os.environ) -> list[str]:
    """Addresses offered on the phone page besides the usual one."""
    listed = (a.strip() for a in env.get("ECRIVEZ_MAIL_CHOICES", "").split(","))
    return [a for a in listed if valid(a)]


def available(env: Mapping[str, str] = os.environ) -> bool:
    return shutil.which(env.get("ECRIVEZ_MAIL_COMMAND") or DEFAULT_COMMAND) is not None


def send(
    note: str,
    env: Mapping[str, str] = os.environ,
    run: Run = run_tool,
    to: str | None = None,
) -> None:
    """The subject carries only the date: nothing about the patient outside the body."""
    command = env.get("ECRIVEZ_MAIL_COMMAND") or DEFAULT_COMMAND
    subject = f"Note ecrivez {datetime.now():%Y-%m-%d %H:%M}"
    argv = [command, "-s", subject, "-c", note]
    if to := to or env.get("ECRIVEZ_MAIL_TO"):
        argv += ["--email-receiver", to]
    run(argv, None)
