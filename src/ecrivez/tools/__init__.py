"""Built-in helper tools for Ecrivez.

Currently includes only *run_shell* – a thin wrapper around subprocess that is
handy during experiments.  **Do not** expose this to untrusted input in
production.
"""

from __future__ import annotations

import shlex
import subprocess
from typing import List

__all__ = ["run_shell"]


def run_shell(args: str | List[str]) -> str:  # noqa: WPS231 – tiny util
    """Run *args* locally and return combined stdout / stderr.

    If *args* is a string we parse it with :pymod:`shlex.split` to obtain the
    token list.
    """

    cmd = shlex.split(args) if isinstance(args, str) else list(args)

    try:
        completed = subprocess.run(  # noqa: S603,S607 – user-requested cmds
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        output = completed.stdout.strip()
        if completed.stderr:
            output += ("\n" if output else "") + completed.stderr.strip()
        return output or "<no output>"
    except subprocess.CalledProcessError as exc:  # noqa: WPS440
        return (
            "Command failed with exit code "
            f"{exc.returncode}:\n{exc.stdout}\n{exc.stderr}"
        )