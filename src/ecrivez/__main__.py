"""Module executed as ``python -m ecrivez``.

It simply forwards to :pyfunc:`ecrivez.cli.cli` so users can run either of:

• ``uv run python -m ecrivez --help``  (always available)
• ``uv run ecrivez --help``             (after project is installed in the env)
"""

from __future__ import annotations

from ecrivez.cli import cli


def _main() -> None:  # noqa: D401 – entry-point convenience
    cli()


if __name__ == "__main__":  # pragma: no cover
    _main()
