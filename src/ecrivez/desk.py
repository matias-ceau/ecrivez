"""The secretary's desk: the private, synced data folder."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path

DEFAULT_ROOT = "~/.local/share/ecrivez"
SEEDS = {
    "trames/tca.md": "trames/tca.md",
    "trames/psy.md": "trames/psy.md",
    "regles.md": "regles.md",
}


class UnknownTemplate(Exception):
    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(name)
        self.name = name
        self.available = available


@dataclass(frozen=True)
class SavedNote:
    dir: Path
    source: str
    note: str
    template: str | None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _append_new(path: Path, lines: list[str]) -> None:
    known = {line.strip() for line in _read(path).splitlines()}
    fresh = [f"- {item}" for item in lines if f"- {item}" not in known]
    if fresh:
        existing = _read(path)
        sep = "" if not existing or existing.endswith("\n") else "\n"
        path.write_text(existing + sep + "\n".join(fresh) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class Desk:
    root: Path

    def templates(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "trames").glob("*.md"))

    def template(self, name: str) -> str:
        path = self.root / "trames" / f"{name}.md"
        if not path.exists():
            raise UnknownTemplate(name, self.templates())
        return _read(path)

    def examples(self) -> list[str]:
        return [_read(p) for p in sorted((self.root / "exemples").glob("*.md"))]

    def lexicon(self) -> str:
        return _read(self.root / "lexique.md")

    def rules(self) -> str:
        return _read(self.root / "regles.md")

    def new_output_dir(self) -> Path:
        now = datetime.now()
        day = self.root / "sorties" / now.strftime("%Y-%m-%d")
        base = now.strftime("%H%M%S")
        folder, n = day / base, 1
        while folder.exists():
            n += 1
            folder = day / f"{base}-{n}"
        folder.mkdir(parents=True)
        return folder

    def save(
        self, source: str, note: str, template: str | None, folder: Path | None = None
    ) -> Path:
        folder = folder or self.new_output_dir()
        (folder / "source.txt").write_text(source.rstrip("\n") + "\n", encoding="utf-8")
        (folder / "note.txt").write_text(note.rstrip("\n") + "\n", encoding="utf-8")
        (folder / "meta.json").write_text(json.dumps({"template": template}), encoding="utf-8")
        (self.root / "sorties" / "last").write_text(
            str(folder.relative_to(self.root)), encoding="utf-8"
        )
        return folder

    def last(self) -> SavedNote | None:
        pointer = self.root / "sorties" / "last"
        if not pointer.exists():
            return None
        folder = self.root / _read(pointer).strip()
        if not (folder / "note.txt").exists():
            return None
        meta = json.loads(_read(folder / "meta.json") or "{}")
        return SavedNote(
            dir=folder,
            source=_read(folder / "source.txt").rstrip("\n"),
            note=_read(folder / "note.txt").rstrip("\n"),
            template=meta.get("template"),
        )

    def remember(self, lexicon: list[str], rules: list[str]) -> None:
        _append_new(self.root / "lexique.md", lexicon)
        _append_new(self.root / "regles.md", rules)


def open_desk(env: Mapping[str, str] = os.environ) -> Desk:
    root = Path(env.get("ECRIVEZ_DATA") or DEFAULT_ROOT).expanduser()
    for sub in ("trames", "exemples", "sorties"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    seeds = resources.files("ecrivez") / "resources"
    for target, source in SEEDS.items():
        dest = root / target
        if not dest.exists():
            dest.write_text((seeds / source).read_text(encoding="utf-8"), encoding="utf-8")
    if not (root / "lexique.md").exists():
        (root / "lexique.md").write_text("", encoding="utf-8")
    return Desk(root)
