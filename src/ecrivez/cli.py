"""Menu and direct commands."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from ecrivez import audio, writer
from ecrivez.desk import Desk, UnknownTemplate, open_desk
from ecrivez.writer import Run, ToolError, run_tool

RULE = "─" * 60
FREE_LABEL = "aucune (observation libre)"


class Stop(Exception):
    """A problem already worded for the doctor."""


def read_key() -> str:
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line.strip()[:1].lower() if line else "q"
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        char = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    return "q" if char in ("\x03", "\x04", "") else char.lower()


def record_with_timer(dest: Path) -> None:
    done = threading.Event()
    start = time.monotonic()

    def tick() -> None:
        while not done.wait(1):
            elapsed = int(time.monotonic() - start)
            size = dest.stat().st_size / 1e6 if dest.exists() else 0
            print(
                f"\r  ● Enregistrement {elapsed // 60:02d}:{elapsed % 60:02d}  ({size:.1f} Mo)"
                "   [Entrée] pour terminer ",
                end="",
                flush=True,
            )

    threading.Thread(target=tick, daemon=True).start()
    try:
        audio.record(dest)
    finally:
        done.set()
        print()


def copy_to_clipboard(text: str) -> None:
    # wl-copy leaves a daemon holding its output pipes: never capture them.
    try:
        subprocess.run(
            ["wl-copy"],
            input=text,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=5,
        )
    except FileNotFoundError:
        raise ToolError("wl-copy", "programme introuvable") from None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise ToolError("wl-copy", "copie impossible") from None


def _stderr(text: str) -> None:
    print(text, file=sys.stderr)


@dataclass
class Deps:
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)
    run: Run = run_tool
    record: Callable[[Path], None] = record_with_timer
    copy: Callable[[str], None] = copy_to_clipboard
    key: Callable[[], str] = read_key
    read: Callable[[str], str] = input
    out: Callable[[str], None] = print
    err: Callable[[str], None] = _stderr


def _deliver(desk: Desk, source: str, note: str, template: str | None, folder: Path, d: Deps):
    desk.save(source, note, template, folder)
    d.out(RULE)
    d.out(note)
    d.out(RULE)
    try:
        d.copy(note)
        copied = "Copié dans le presse-papiers. "
    except ToolError:
        copied = ""
    d.out(f"{copied}Fichier : {folder / 'note.txt'}")


def _write(desk: Desk, source: str, template: str | None, folder: Path, d: Deps) -> None:
    (folder / "source.txt").write_text(source + "\n", encoding="utf-8")
    d.out("  Rédaction…")
    try:
        note = writer.draft(desk, source, template, d.run)
    except ToolError as e:
        raise Stop(f"Erreur : {e}. Rien n'est perdu, tout est dans {folder}") from None
    _deliver(desk, source, note, template, folder, d)


def _from_audio(desk: Desk, sound: Path, template: str | None, folder: Path, d: Deps) -> None:
    d.out("  Transcription…")
    try:
        heard = audio.transcribe(sound, audio.hint_from_lexicon(desk.lexicon()), d.env, d.run)
    except ToolError as e:
        raise Stop(f"Erreur : {e}. L'audio est conservé : {sound}") from None
    if not heard.strip():
        raise Stop(f"Transcription vide : rien d'audible. L'audio est conservé dans {folder}")
    _write(desk, heard, template, folder, d)


def from_text(desk: Desk, text: str, template: str | None, d: Deps) -> None:
    _check(desk, template)
    _write(desk, text.strip(), template, desk.new_output_dir(), d)


def from_file(desk: Desk, path: Path, template: str | None, d: Deps) -> None:
    _check(desk, template)
    if not path.is_file():
        raise Stop(f"Fichier introuvable : {path}")
    folder = desk.new_output_dir()
    kept = folder / f"audio{path.suffix.lower()}"
    shutil.copyfile(path, kept)
    _from_audio(desk, kept, template, folder, d)


def from_microphone(desk: Desk, template: str | None, d: Deps) -> None:
    _check(desk, template)
    folder = desk.new_output_dir()
    wav = folder / "audio.wav"
    try:
        d.record(wav)
    except ToolError as e:
        if not wav.exists() or wav.stat().st_size <= audio.WAV_HEADER:
            shutil.rmtree(folder, ignore_errors=True)
        raise Stop(f"Erreur : {e}") from None
    sound = wav
    try:
        audio.to_flac(wav, folder / "audio.flac", d.run)
        if (folder / "audio.flac").stat().st_size > 0:
            wav.unlink()
            sound = folder / "audio.flac"
    except (ToolError, OSError):
        d.err("  (compression FLAC impossible, l'audio reste en WAV)")
    _from_audio(desk, sound, template, folder, d)


def _check(desk: Desk, template: str | None) -> None:
    if template is None:
        return
    try:
        desk.template(template)
    except UnknownTemplate as e:
        known = ", ".join(e.available) or "aucune"
        raise Stop(f"Trame inconnue : {e.name}. Trames disponibles : {known}") from None


def _feedback_loop(desk: Desk, d: Deps) -> None:
    while True:
        try:
            remark = d.read("\nUne remarque ? (Entrée = c'est bon)\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        last = desk.last()
        if not remark or last is None:
            return
        d.out("  Correction…")
        try:
            revision = writer.revise(desk, last, remark, d.run)
        except ToolError as e:
            d.err(f"Erreur : {e}")
            continue
        if not revision.note:
            d.err("Correction vide, document inchangé.")
            continue
        desk.remember(revision.lexicon, revision.rules)
        _deliver(desk, last.source, revision.note, last.template, last.dir, d)
        for term in revision.lexicon:
            d.out(f"Retenu (lexique) : {term}")
        for rule in revision.rules:
            d.out(f"Retenu (règle) : {rule}")


def _current_template(desk: Desk) -> str | None:
    state = desk.root / "trame"
    names = desk.templates()
    if state.exists():
        name = state.read_text(encoding="utf-8").strip()
        return name if name in names else None
    return "tca" if "tca" in names else (names[0] if names else None)


def _next_template(desk: Desk, current: str | None) -> str | None:
    choices: list[str | None] = [*desk.templates(), None]
    following = choices[(choices.index(current) + 1) % len(choices)]
    (desk.root / "trame").write_text(following or "", encoding="utf-8")
    return following


def run_menu(desk: Desk, d: Deps) -> None:
    template = _current_template(desk)
    while True:
        label = template.upper() if template else FREE_LABEL
        d.out(
            f"\n  Ecrivez — trame : {label}\n\n"
            "  [c] enregistrer une consultation\n"
            "  [d] dicter\n"
            "  [f] fichier audio\n"
            "  [t] taper du texte\n"
            "  [m] changer de trame\n"
            "  [q] quitter\n"
        )
        try:
            choice = d.key()
        except (EOFError, KeyboardInterrupt, IndexError):
            return
        try:
            if choice == "q":
                return
            if choice == "m":
                template = _next_template(desk, template)
                continue
            if choice in ("c", "d"):
                from_microphone(desk, template, d)
            elif choice == "f":
                raw = d.read("Chemin du fichier audio (glisser-déposer possible)\n> ")
                from_file(desk, Path(raw.strip().strip("'\"")).expanduser(), template, d)
            elif choice == "t":
                from_text(desk, d.read("Texte en vrac\n> "), template, d)
            else:
                continue
        except Stop as e:
            d.err(str(e))
            continue
        except (EOFError, KeyboardInterrupt):
            continue
        _feedback_loop(desk, d)


def main(argv: list[str] | None = None, deps: Deps | None = None) -> int:
    d = deps or Deps()
    parser = argparse.ArgumentParser(prog="ecrivez", description="Secrétaire médicale.")
    sub = parser.add_subparsers(dest="command")
    p_file = sub.add_parser("fichier", help="rédiger à partir d'un fichier audio")
    p_file.add_argument("audio", type=Path)
    p_file.add_argument("trame", nargs="?")
    p_text = sub.add_parser("texte", help="rédiger à partir d'un texte en vrac")
    p_text.add_argument("phrase")
    p_text.add_argument("trame", nargs="?")
    args = parser.parse_args(argv)

    desk = open_desk(d.env)
    try:
        if args.command == "fichier":
            from_file(desk, args.audio.expanduser(), args.trame, d)
        elif args.command == "texte":
            from_text(desk, args.phrase, args.trame, d)
        else:
            run_menu(desk, d)
    except Stop as e:
        d.err(str(e))
        return 2
    return 0
