"""Helpers for talking to a Neovim instance via its msgpack socket.

All real interactions are isolated here so unit-tests can monkey-patch the
`connect` function to return a fake **nvim** object instead of requiring the
`pynvim` package or an actual editor.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

# Real attach is imported lazily inside *connect* to keep dependency optional.

SOCKET_TEMPLATE = "/tmp/nvim-ecrivez-{name}.sock"


def connect(project_name: str):  # noqa: D401 – small factory
    """Return a *pynvim* instance connected to the project’s socket."""

    sock = SOCKET_TEMPLATE.format(name=project_name)

    try:
        from pynvim import attach  # type: ignore  # noqa: WPS433

        return attach("socket", path=sock)
    except FileNotFoundError as exc:  # pragma: no cover – runtime only
        raise RuntimeError(f"Neovim socket not found at {sock}") from exc


# ---------------------------------------------------------------------------
# Diff application (very naive on purpose)
# ---------------------------------------------------------------------------


def apply_diff(nvim, diff: str) -> None:  # noqa: ANN001 – nvim is dynamic
    """Apply a *simple* unified diff to the current buffer.

    Limitations: context lines are ignored; we only support top-level + / -
    prefixes and operate sequentially on the buffer.  Good enough for unit
    tests and small demos.
    """

    buf: List[str] = list(nvim.current.buffer)  # type: ignore[attr-defined]

    for line in diff.splitlines():
        if not line:
            continue
        if line.startswith("+"):
            buf.append(line[1:])
        elif line.startswith("-"):
            try:
                buf.remove(line[1:])
            except ValueError:
                # line not in buffer – skip
                pass

    nvim.current.buffer[:] = buf  # type: ignore[attr-defined]
    nvim.command("write")  # type: ignore[attr-defined]
