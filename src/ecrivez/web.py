"""The phone web app: a private page that records, sends audio home and shows the note.

See docs/superpowers/specs/2026-11-19-mobile.md. The phone sends short chunks of audio;
the server appends them to the part being recorded, and each closed part goes through the
same transcription and assembly as a session recorded on the computer (`live.py`).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlsplit

from ecrivez import audio, live, mail, writer
from ecrivez.cli import _current_template
from ecrivez.desk import Desk, UnknownTemplate, open_desk
from ecrivez.writer import Run, ToolError, run_tool

DEFAULT_PORT = 8377
STATE = "web.json"
SESSION_ID = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{6}(?:-\d+)?)$")
CHUNK_FORMATS = ("webm", "ogg", "m4a")
UPLOAD_FORMATS = ("mp3", "m4a", "mp4", "aac", "wav", "ogg", "opus", "flac", "webm", "amr", "3gp")
MAX_CHUNK = 8 * 1024 * 1024
MAX_UPLOAD = 1024 * 1024 * 1024
TEXT_HEADING = "Texte joint par le médecin :"
TEXT_FILE = "texte.txt"
AUTO_TRIES = 6
TRANSCRIPT_HEADING = "Transcription de la consultation :"

# Phases of a session, kept in web.json:
#   nouvelle   opened, nothing received yet
#   active     the phone is sending audio
#   pause      nothing received for a while: everything is transcribed, more is still accepted
#   decoupage  an uploaded file is being cut into parts
#   close      no more audio will come (transcription and assembly may still be running)
#
# With automatic notes, web.json also carries "auto": "attente" (the note is still to be
# drafted or mailed), then "fait", or "abandon" after too many failures.


class Readable(Protocol):
    def read(self, size: int, /) -> bytes: ...


class _Body:
    """The request body, counted, so that what a refusal left unread can be discarded."""

    def __init__(self, source: Readable, length: int) -> None:
        self.source = source
        self.remaining = length

    def read(self, size: int, /) -> bytes:
        block = self.source.read(min(size, self.remaining)) if self.remaining > 0 else b""
        self.remaining -= len(block)
        return block

    def drain(self) -> None:
        while self.read(1 << 20):
            pass


class Refused(Exception):
    """A request the server will not carry out, worded for the doctor."""

    def __init__(self, status: int, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


NO_MAIL = "aucun"


@dataclass(frozen=True)
class Wish:
    """What the doctor chose on the page for the note: a template (None: free), a text,
    and where to mail it ("": the usual address, NO_MAIL, an address; None: not said)."""

    template: str | None = None
    text: str = ""
    mail: str | None = None


class Send(Protocol):
    def __call__(self, note: str, *, to: str | None = None) -> object: ...


@dataclass
class _Running:
    """What this process holds in memory for one session."""

    session: live.Session
    recording: threading.Event = field(default_factory=threading.Event)
    hold: threading.Event = field(default_factory=threading.Event)
    worker: live.Worker | None = None
    threads: list[threading.Thread] = field(default_factory=list)
    message: str = ""
    drafting: bool = False
    mailing: bool = False


Draft = Callable[[Desk, str, str | None], str]


class Studio:
    def __init__(
        self,
        desk: Desk,
        transcriber: Callable[[], live.TranscribePart],
        run: Run = run_tool,
        draft: Draft = writer.draft,
        send: Send = mail.send,
        can_mail: Callable[[], bool] = mail.available,
        addresses: Callable[[], list[str]] = mail.choices,
        auto: bool = False,
        clock: Callable[[], float] = time.time,
        part_seconds: int = live.PART_SECONDS,
        idle_pause: float = 600,
        idle_close: float = 12 * 3600,
        retry: float = live.RETRY_SECONDS,
        poll: float = 1.0,
    ) -> None:
        self.desk = desk
        self.transcriber = transcriber
        self.run = run
        self.draft = draft
        self.send = send
        self.can_mail = can_mail
        self.addresses = addresses
        self.auto = auto
        self.clock = clock
        self.part_seconds = part_seconds
        self.idle_pause = idle_pause
        self.idle_close = idle_close
        self.retry = retry
        self.poll = poll
        self._mutex = threading.RLock()
        self._running: dict[str, _Running] = {}

    # -- sessions on disk --------------------------------------------------------------

    def _folder(self, sid: str) -> Path:
        match = SESSION_ID.match(sid)
        folder = self.desk.root / "sorties" / match[1] / match[2] if match else None
        if folder is None or not folder.is_dir():
            raise Refused(404, "Séance introuvable.")
        return folder

    def _exists(self, sid: str) -> bool:
        try:
            self._folder(sid)
        except Refused:
            return False
        return True

    @staticmethod
    def _sid(folder: Path) -> str:
        return f"{folder.parent.name}_{folder.name}"

    @staticmethod
    def _load(folder: Path) -> dict[str, Any]:
        meta = {"phase": "close", "tranche": -1, "rang": -1, "taille": 0, "vu": 0.0}
        try:
            meta.update(json.loads((folder / STATE).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        return meta

    @staticmethod
    def _store(folder: Path, meta: dict[str, Any]) -> None:
        live._write_atomic(folder / STATE, json.dumps(meta))

    def _of(self, sid: str, folder: Path) -> _Running:
        if sid not in self._running:
            self._running[sid] = _Running(live.Session(folder))
        return self._running[sid]

    def _work(self, sid: str, running: _Running) -> None:
        """Make sure a worker is transcribing this session."""
        if running.worker is not None and not running.worker.done.is_set():
            return

        def notify(message: str) -> None:
            running.message = message
            self._auto_step(sid)

        running.session.take()
        running.worker = live.Worker(
            running.session,
            self.transcriber(),
            notify,
            running.recording,
            run=self.run,
            retry=self.retry,
            poll=self.poll,
            hold=running.hold,
        )
        running.worker.start()

    # -- recording ---------------------------------------------------------------------

    def _wish(self, folder: Path, meta: dict[str, Any], wish: Wish | None) -> None:
        if wish is None:
            return
        if wish.template is None or wish.template in self.desk.templates():
            meta["trame"] = wish.template
        if wish.mail is not None and (wish.mail in ("", NO_MAIL) or mail.valid(wish.mail)):
            meta["destinataire"] = wish.mail
        text = wish.text.strip()
        if text:
            live._write_atomic(folder / TEXT_FILE, text + "\n")
        else:
            (folder / TEXT_FILE).unlink(missing_ok=True)

    def create(self, wish: Wish | None = None, sid: str | None = None) -> str:
        """Open a session. A phone that recorded offline names it itself: twice is harmless."""
        if sid is None:
            folder = self.desk.new_output_dir()
        else:
            match = SESSION_ID.match(sid)
            if match is None:
                raise Refused(400, "Nom de séance invalide.")
            try:
                datetime.strptime(f"{match[1]} {match[2][:6]}", "%Y-%m-%d %H%M%S")
            except ValueError:
                raise Refused(400, "Nom de séance invalide.") from None
            folder = self.desk.root / "sorties" / match[1] / match[2]
        with self._mutex:
            if sid is not None:
                if (folder / STATE).exists():
                    return sid
                if folder.exists():
                    raise Refused(409, "Ce nom de séance est déjà pris.")
                folder.mkdir(parents=True)
            meta = {**self._load(folder), "phase": "nouvelle", "vu": self.clock()}
            self._wish(folder, meta, wish)
            self._store(folder, meta)
        return self._sid(folder)

    def chunk(self, sid: str, tranche: int, rang: int, data: bytes, ext: str = "webm") -> str:
        """Append one chunk of audio. Returns "recu", or "deja" for a chunk sent twice."""
        if ext not in CHUNK_FORMATS:
            raise Refused(400, "Format audio non pris en charge.")
        with self._mutex:
            if SESSION_ID.match(sid) and not self._exists(sid):
                self.create(sid=sid)  # audio recorded offline must never wait for anything
            folder = self._folder(sid)
            meta = self._load(folder)
            if meta["phase"] in ("close", "decoupage"):
                raise Refused(409, "Cette séance est close.")
            last, rank = meta["tranche"], meta["rang"]
            if tranche < last or (tranche == last and rang <= rank):
                return "deja"
            follows = tranche == last and rang == rank + 1
            if not follows and not (tranche > last and rang == 0):
                expected = {"tranche": max(last, 0), "rang": rank + 1 if last >= 0 else 0}
                raise Refused(409, "Morceau en avance.", attendu=expected)

            running = self._of(sid, folder)
            running.session.parts_dir.mkdir(exist_ok=True)
            part = running.session.parts_dir / f"part{tranche:03d}.{ext}"
            with part.open("r+b" if follows and part.exists() else "wb") as f:
                if follows:
                    f.truncate(meta["taille"])  # drop bytes written but never recorded
                    f.seek(0, os.SEEK_END)
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
                size = f.tell()
            for stale in (".txt", ".ctx"):  # transcribed during a pause: do it again
                part.with_suffix(stale).unlink(missing_ok=True)
            meta.update(phase="active", tranche=tranche, rang=rang, taille=size, vu=self.clock())
            self._store(folder, meta)
            running.recording.set()
            running.hold.set()
            self._work(sid, running)
        return "recu"

    def finish(self, sid: str, wish: Wish | None = None) -> None:
        with self._mutex:
            folder = self._folder(sid)
            meta = self._load(folder)
            if meta["phase"] not in ("active", "pause", "nouvelle"):
                return
            had_audio = meta["phase"] != "nouvelle"
            meta["phase"] = "close"
            self._wish(folder, meta, wish)
            if had_audio and self.auto:
                meta["auto"] = "attente"
            self._store(folder, meta)
            if had_audio:
                running = self._of(sid, folder)
                running.recording.clear()
                running.hold.clear()
                self._work(sid, running)

    def sweep(self) -> None:
        """Pause sessions whose phone went silent; close for good those paused too long."""
        with self._mutex:
            for sid, running in list(self._running.items()):
                folder = running.session.folder
                meta = self._load(folder)
                silent = self.clock() - meta["vu"]
                if meta["phase"] == "active" and silent > self.idle_pause:
                    meta["phase"] = "pause"
                    self._store(folder, meta)
                    running.recording.clear()  # the last part gets transcribed, nothing assembled
                elif meta["phase"] == "pause" and silent > self.idle_close:
                    self.finish(sid)
            for sid in list(self._running):
                self._auto_step(sid)

    def resume(self) -> None:
        """After a restart: pick every unfinished session up where it was."""
        with self._mutex:
            for state in sorted((self.desk.root / "sorties").glob(f"*/*/{STATE}")):
                folder = state.parent
                sid, meta = self._sid(folder), self._load(folder)
                if live.Session(folder).busy():
                    continue
                if meta["phase"] in ("active", "pause"):
                    running = self._of(sid, folder)
                    running.hold.set()
                    if meta["phase"] == "active":
                        running.recording.set()
                        self._store(folder, {**meta, "vu": self.clock()})
                    self._work(sid, running)
                elif meta["phase"] == "decoupage":
                    self._cut_later(sid, folder)
                elif meta.get("auto") == "attente":
                    self._of(sid, folder)
            for session in live.unfinished_sessions(self.desk.root):
                sid = self._sid(session.folder)
                if sid not in self._running:
                    self._work(sid, self._of(sid, session.folder))
            for sid in list(self._running):
                self._auto_step(sid)

    # -- sending a file ----------------------------------------------------------------

    def upload(self, sid: str, source: Readable, length: int, name: str) -> None:
        ext = Path(name).suffix.lower().lstrip(".")
        if ext not in UPLOAD_FORMATS:
            raise Refused(400, "Ce fichier n'est pas un enregistrement audio reconnu.")
        with self._mutex:
            folder = self._folder(sid)
            meta = self._load(folder)
            if meta["phase"] != "nouvelle":
                raise Refused(409, "Cette séance a déjà un enregistrement.")
            self._store(folder, {**meta, "phase": "decoupage"})
        original = folder / f"original.{ext}"
        with original.open("wb") as f:
            remaining = length
            while remaining > 0:
                block = source.read(min(remaining, 1 << 20))
                if not block:
                    break
                f.write(block)
                remaining -= len(block)
            f.flush()
            os.fsync(f.fileno())
        with self._mutex:
            self._cut_later(sid, folder)

    def _cut_later(self, sid: str, folder: Path) -> None:
        running = self._of(sid, folder)
        thread = threading.Thread(target=self._cut, args=(sid, folder, running), daemon=True)
        running.threads.append(thread)
        thread.start()

    def _cut(self, sid: str, folder: Path, running: _Running) -> None:
        """Cut the uploaded file into parts; they appear all at once, never half done."""
        original = next(iter(sorted(folder.glob("original.*"))), None)
        tmp = folder / "decoupe"
        shutil.rmtree(tmp, ignore_errors=True)
        error = None
        try:
            if original is None:
                raise ToolError("ffmpeg", "fichier absent")
            tmp.mkdir()
            argv = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(original)]
            argv += ["-ac", "1", "-ar", "16000", "-c:a", "flac", "-f", "segment"]
            argv += ["-segment_time", str(self.part_seconds), str(tmp / "part%03d.flac")]
            self.run(argv, None)
            if not any(tmp.iterdir()):
                raise ToolError("ffmpeg", "aucun son dans le fichier")
            tmp.rename(running.session.parts_dir)
        except (ToolError, OSError) as e:
            shutil.rmtree(tmp, ignore_errors=True)
            error = f"Fichier audio illisible ({e}). Il est conservé dans la séance."
        with self._mutex:
            meta = {**self._load(folder), "phase": "close"}
            if error:
                meta["erreur"] = error
            elif self.auto:
                meta["auto"] = "attente"
            self._store(folder, meta)
            if not error:
                self._work(sid, running)

    # -- reading -----------------------------------------------------------------------

    def _etat(self, folder: Path, meta: dict[str, Any]) -> str:
        if meta["phase"] == "active":
            return "enregistrement"
        if meta["phase"] == "pause":
            return "pause"
        if meta["phase"] == "decoupage" or (folder / live.PARTS).exists():
            return "transcription"
        kept = (live.TRANSCRIPT, "note.txt")
        sound = any(folder.glob("audio.*")) or any(folder.glob("original.*"))
        if sound or any((folder / name).exists() for name in kept):
            return "terminee"
        return "nouvelle"

    @staticmethod
    def _note(folder: Path) -> str | None:
        path = folder / "note.txt"
        return path.read_text(encoding="utf-8").strip() if path.exists() else None

    @staticmethod
    def _hour(moment: float | None) -> str | None:
        return f"{datetime.fromtimestamp(moment):%H:%M}" if moment else None

    def state(self, sid: str) -> dict[str, Any]:
        with self._mutex:
            folder = self._folder(sid)
            meta = self._load(folder)
            session = live.Session(folder)
            running = self._running.get(sid)
            return {
                "id": sid,
                "etat": self._etat(folder, meta),
                "transcription": session.transcript(),
                "tranches": len(session.parts()),
                "transcrites": len(session.texts()),
                "note": self._note(folder),
                "redaction": bool(running and running.drafting),
                "auto": meta.get("auto") == "attente",
                "envoye": self._hour(meta.get("envoye")),
                "envoye_a": meta.get("envoye_a") or None,
                "erreur": meta.get("erreur"),
                "message": running.message if running else "",
                "panne": running.worker.trouble if running and running.worker else "",
            }

    def today(self) -> dict[str, Any]:
        day = self.desk.root / "sorties" / datetime.now().strftime("%Y-%m-%d")
        sessions = []
        with self._mutex:
            for folder in sorted(p for p in day.glob("*") if p.is_dir()):
                etat = self._etat(folder, self._load(folder))
                if etat == "nouvelle":
                    continue
                hour = folder.name
                sessions.append(
                    {
                        "id": self._sid(folder),
                        "heure": f"{hour[:2]}:{hour[2:4]}",
                        "etat": etat,
                        "note": (folder / "note.txt").exists(),
                    }
                )
        return {
            "seances": sessions,
            "trames": self.desk.templates(),
            "trame": _current_template(self.desk),
            "duree_tranche": self.part_seconds,
            "mail": self.can_mail(),
            "adresses": self.addresses(),
            "auto": self.auto,
        }

    # -- the note ----------------------------------------------------------------------

    def start_draft(self, sid: str, template: str | None, text: str) -> None:
        with self._mutex:
            folder = self._folder(sid)
            meta = self._load(folder)
            running = self._of(sid, folder)
            if running.drafting:
                raise Refused(409, "La rédaction est déjà en cours.")
            pending = running.session.pending(recording=False)
            if meta["phase"] in ("active", "decoupage") or pending:
                raise Refused(409, "La transcription n'est pas finie.")
            if template is not None:
                try:
                    self.desk.template(template)
                except UnknownTemplate:
                    raise Refused(400, f"Trame inconnue : {template}") from None
            self._begin_draft(folder, meta, running, template, text)

    def _begin_draft(
        self, folder: Path, meta: dict[str, Any], running: _Running, template: str | None, text: str
    ) -> None:
        heard, text = running.session.transcript(), text.strip()
        if not heard and not text:
            raise Refused(400, "Rien à rédiger : ni transcription ni texte.")
        source = heard or text
        if heard and text:
            source = f"{TRANSCRIPT_HEADING}\n{heard}\n\n{TEXT_HEADING}\n{text}"
        running.drafting = True
        meta.pop("erreur", None)
        self._store(folder, meta)
        thread = threading.Thread(
            target=self._draft, args=(folder, running, source, template), daemon=True
        )
        running.threads.append(thread)
        thread.start()

    def _draft(self, folder: Path, running: _Running, source: str, template: str | None) -> None:
        error = None
        try:
            note = self.draft(self.desk, source, template)
            self.desk.save(source, note, template, folder)
        except (ToolError, OSError) as e:
            error = f"Rédaction impossible : {e}. La transcription et l'audio sont intacts."
        with self._mutex:
            if error:
                meta = self._load(folder)
                meta["erreur"] = error
                self._later(meta)
                self._store(folder, meta)
            running.drafting = False
        self._auto_step(self._sid(folder))

    @staticmethod
    def _to(meta: dict[str, Any]) -> str | None:
        """The address wished for this session; None is the mail command's usual one."""
        wished = meta.get("destinataire")
        return wished if wished and wished != NO_MAIL else None

    def send_mail(self, sid: str, to: str | None = None) -> None:
        """Mail the note to `to` ("": the usual address), or where the session wished."""
        folder = self._folder(sid)
        note = self._note(folder)
        if not note:
            raise Refused(409, "Pas encore de note à envoyer.")
        if to and not mail.valid(to):
            raise Refused(400, "Adresse mail invalide.")
        target = self._to(self._load(folder)) if to is None else to or None
        try:
            self.send(note, to=target)
        except ToolError as e:
            raise Refused(502, f"Envoi impossible : {e}") from None
        with self._mutex:
            self._sent(folder, self._load(folder), target)

    def _sent(self, folder: Path, meta: dict[str, Any], to: str | None) -> None:
        meta["envoye"] = self.clock()
        meta["envoye_a"] = to or ""
        if meta.get("auto") == "attente":
            meta["auto"] = "fait"
        meta.pop("erreur", None)
        self._store(folder, meta)

    # -- the automatic note ------------------------------------------------------------

    def _later(self, meta: dict[str, Any]) -> None:
        """A failed automatic step is tried again, less and less often, then given up."""
        if meta.get("auto") != "attente":
            return
        tries = meta.get("auto_essais", 0) + 1
        meta["auto_essais"] = tries
        if tries >= AUTO_TRIES:
            meta["auto"] = "abandon"
        else:
            meta["auto_apres"] = self.clock() + min(60 * 2 ** (tries - 1), 1800)

    def _auto_step(self, sid: str) -> None:
        """Draft, then mail, a closed session whose transcript is whole. Nobody has to ask."""
        with self._mutex:
            running = self._running.get(sid)
            if running is None or running.drafting or running.mailing:
                return
            folder = running.session.folder
            meta = self._load(folder)
            if meta.get("auto") != "attente" or meta["phase"] != "close":
                return
            if running.session.pending(recording=False):
                return
            if self.clock() < meta.get("auto_apres", 0):
                return
            note = self._note(folder)
            if note and meta.get("destinataire") == NO_MAIL:
                meta["auto"] = "fait"  # asked to stay on the page
                self._store(folder, meta)
                return
            if note:
                running.mailing = True
                thread = threading.Thread(
                    target=self._mail, args=(folder, running, note, self._to(meta)), daemon=True
                )
                running.threads.append(thread)
                thread.start()
                return
            template = meta["trame"] if "trame" in meta else _current_template(self.desk)
            if template not in self.desk.templates():
                template = None
            path = folder / TEXT_FILE
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            silence = (live.INAUDIBLE_PART, live.BROKEN_PART)
            heard = [t for t in running.session.transcript().splitlines() if t not in silence]
            try:
                if not heard and not text.strip():
                    raise Refused(400, "Rien d'audible.")
                self._begin_draft(folder, meta, running, template, text)
            except Refused:
                meta.update(auto="abandon", erreur="Rien d'audible : pas de note automatique.")
                self._store(folder, meta)

    def _mail(self, folder: Path, running: _Running, note: str, to: str | None) -> None:
        error = None
        try:
            self.send(note, to=to)
        except ToolError as e:
            error = f"Envoi automatique par mail impossible : {e}. La note est prête."
        with self._mutex:
            meta = self._load(folder)
            if error:
                meta["erreur"] = error
                self._later(meta)
                self._store(folder, meta)
            else:
                self._sent(folder, meta, to)
            running.mailing = False

    # -- life cycle --------------------------------------------------------------------

    def settle(self, sid: str, timeout: float = 10.0) -> None:
        """Wait until nothing is left to do for this session in its current phase."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._mutex:
                running = self._running.get(sid)
                if running is None:
                    return
                threads = [t for t in running.threads if t.is_alive()]
                worker = running.worker
                idle = (
                    worker is None
                    or worker.done.is_set()
                    or not running.session.pending(recording=running.recording.is_set())
                )
                waiting = running.hold.is_set() or running.recording.is_set()
                if worker is not None and not worker.done.is_set() and not waiting:
                    idle = False  # it still has to assemble
            if not threads and idle:
                return
            time.sleep(0.01)
        raise TimeoutError(f"session {sid} still busy after {timeout} s")

    def shutdown(self) -> None:
        with self._mutex:
            workers = [r.worker for r in self._running.values() if r.worker is not None]
            self._running.clear()
        for worker in workers:
            worker.stop.set()
        for worker in workers:
            worker.join(timeout=5)


# -- access --------------------------------------------------------------------------

CODE_FILE = "web-code"
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes: typed once on a phone
COOKIE = "ecrivez"
COOKIE_SECONDS = 365 * 24 * 3600
MAX_WAIT = 300.0


def access_code(desk: Desk) -> str:
    """The code that opens the page, made on first use and kept in the private data folder."""
    path = desk.root / CODE_FILE
    if not path.exists():
        letters = [secrets.choice(CODE_ALPHABET) for _ in range(20)]
        groups = ["".join(letters[i : i + 4]) for i in range(0, 20, 4)]
        path.touch(mode=0o600)
        path.write_text("-".join(groups) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path.read_text(encoding="utf-8").strip()


def _plain(code: str) -> str:
    return re.sub(r"[\s-]", "", code).lower()


class Gate:
    """One code for one doctor. Each wrong code makes everyone wait longer before the next."""

    def __init__(self, code: str, clock: Callable[[], float] = time.monotonic) -> None:
        self._code = _plain(code)
        self.cookie = hmac.new(self._code.encode(), b"ecrivez-web", hashlib.sha256).hexdigest()
        self._clock = clock
        self._failures = 0
        self._locked_until = 0.0
        self._mutex = threading.Lock()

    def login(self, code: str) -> str:
        with self._mutex:
            if self._clock() < self._locked_until:
                raise Refused(429, "Trop d'essais : attendez un peu avant de réessayer.")
            if hmac.compare_digest(_plain(code).encode(), self._code.encode()):
                self._failures = 0
                return self.cookie
            self._failures += 1
            self._locked_until = self._clock() + min(2.0**self._failures, MAX_WAIT)
            raise Refused(403, "Code d'accès incorrect.")

    def allows(self, header: str | None) -> bool:
        try:
            morsel = SimpleCookie(header or "").get(COOKIE)
        except CookieError:
            return False
        return morsel is not None and hmac.compare_digest(
            morsel.value.encode(), self.cookie.encode()
        )


# -- HTTP ------------------------------------------------------------------------------

PAGE = ("index.html", "text/html; charset=utf-8")
LOGIN = ("login.html", "text/html; charset=utf-8")
WORKER = ("sw.js", "text/javascript; charset=utf-8")
PUBLIC = {
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
}
ROUTES = [
    ("POST", re.compile(r"^/api/seances$"), "create"),
    ("GET", re.compile(r"^/api/seances$"), "today"),
    ("GET", re.compile(r"^/api/seances/([^/]+)$"), "state"),
    ("PUT", re.compile(r"^/api/seances/([^/]+)$"), "open"),
    ("PUT", re.compile(r"^/api/seances/([^/]+)/tranches/(\d{1,4})/(\d{1,6})$"), "chunk"),
    ("POST", re.compile(r"^/api/seances/([^/]+)/fin$"), "finish"),
    ("POST", re.compile(r"^/api/seances/([^/]+)/fichier$"), "upload"),
    ("POST", re.compile(r"^/api/seances/([^/]+)/note$"), "note"),
    ("POST", re.compile(r"^/api/seances/([^/]+)/mail$"), "mail"),
]


def _wish_of(data: bytes) -> Wish | None:
    if not data.strip():
        return None
    try:
        asked = json.loads(data)
        to = asked.get("mail")
        return Wish(
            asked.get("trame") or None,
            str(asked.get("texte") or ""),
            None if to is None else str(to).strip(),
        )
    except (ValueError, AttributeError):
        raise Refused(400, "Demande illisible.") from None


def make_handler(studio: Studio, gate: Gate) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _send(
            self,
            status: int,
            body: bytes,
            content_type: str,
            cookie: str | None = None,
            mark: str | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if mark:
                self.send_header("X-Ecrivez", mark)  # tells sw.js this is the page worth keeping
            if cookie:
                flags = f"Max-Age={COOKIE_SECONDS}; Path=/; HttpOnly; Secure; SameSite=Strict"
                self.send_header("Set-Cookie", f"{COOKIE}={cookie}; {flags}")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict[str, Any], cookie: str | None = None) -> None:
            self._send(status, json.dumps(payload).encode(), "application/json", cookie)

        def _file(self, entry: tuple[str, str]) -> None:
            name, content_type = entry
            body = (resources.files("ecrivez") / "resources" / "web" / name).read_bytes()
            self._send(200, body, content_type, mark="page" if entry is PAGE else None)

        def _login(self, body: _Body) -> None:
            try:
                if body.remaining > 4096:
                    raise Refused(413, "Envoi trop volumineux.")
                asked = json.loads(body.read(4096) or b"{}")
                cookie = gate.login(str(asked.get("code") or ""))
            except (ValueError, AttributeError):
                self._json(400, {"erreur": "Demande illisible."})
            except Refused as e:
                self._json(e.status, {"erreur": e.message})
            else:
                self._json(200, {"ok": True}, cookie)

        def _length(self, limit: int) -> int:
            raw = self.headers.get("Content-Length") or "0"
            length = int(raw) if raw.isdigit() else limit + 1
            if length > limit:
                self.close_connection = True
                raise Refused(413, "Envoi trop volumineux.")
            return length

        def _dispatch(self, method: str) -> None:
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            allowed = gate.allows(self.headers.get("Cookie"))
            if method == "GET" and url.path in PUBLIC:
                self._file(PUBLIC[url.path])
                return
            if method == "GET" and url.path == "/":
                self._file(PAGE if allowed else LOGIN)
                return
            if method == "GET" and url.path == "/sw.js" and allowed:
                self._file(WORKER)
                return
            try:
                body = _Body(self.rfile, self._length(MAX_UPLOAD))
            except Refused as e:
                self._json(e.status, {"erreur": e.message})
                return
            if method == "POST" and url.path == "/api/acces":
                self._login(body)
                return
            if not allowed:
                self.close_connection = True  # do not read a body nobody is entitled to send
                self._json(401, {"erreur": "Code d'accès requis."})
                return
            status, answer = 404, {"erreur": "Adresse inconnue."}
            for verb, pattern, action in ROUTES:
                match = pattern.match(url.path)
                if verb == method and match:
                    try:
                        status, answer = self._act(action, match.groups(), query, body)
                    except Refused as e:
                        status, answer = e.status, {"erreur": e.message, **e.extra}
                    break
            body.drain()  # keep the connection usable whatever was left unread
            self._json(status, answer)

        def _act(
            self, action: str, args: tuple[str, ...], query: dict[str, list[str]], body: _Body
        ) -> tuple[int, dict[str, Any]]:
            if action == "upload":
                name = (query.get("nom") or ["audio"])[0]
                studio.upload(args[0], body, body.remaining, name)
                return 202, {"ok": True}
            if body.remaining > MAX_CHUNK:
                raise Refused(413, "Envoi trop volumineux.")
            data = body.read(MAX_CHUNK)
            if action == "create":
                return 200, {"id": studio.create(_wish_of(data))}
            if action == "open":
                return 200, {"id": studio.create(_wish_of(data), args[0])}
            if action == "today":
                return 200, studio.today()
            if action == "state":
                return 200, studio.state(args[0])
            if action == "chunk":
                ext = (query.get("ext") or ["webm"])[0]
                return 200, {
                    "resultat": studio.chunk(args[0], int(args[1]), int(args[2]), data, ext)
                }
            if action == "finish":
                studio.finish(args[0], _wish_of(data))
                return 200, {"ok": True}
            if action == "note":
                try:
                    asked = json.loads(data or b"{}")
                    template, text = asked.get("trame") or None, str(asked.get("texte") or "")
                except (ValueError, AttributeError):
                    raise Refused(400, "Demande illisible.") from None
                studio.start_draft(args[0], template, text)
                return 202, {"ok": True}
            try:
                to = json.loads(data or b"{}").get("mail")
            except (ValueError, AttributeError):
                raise Refused(400, "Demande illisible.") from None
            studio.send_mail(args[0], None if to is None else str(to).strip())
            return 200, {"ok": True}

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_PUT(self) -> None:
            self._dispatch("PUT")

    return Handler


def make_server(studio: Studio, gate: Gate, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Loopback only: the page is reached through an HTTPS relay, never directly."""
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(studio, gate))
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ecrivez-web", description="Ecrivez sur le téléphone.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--auto", action="store_true", help="rédiger et envoyer la note par mail sans attendre"
    )
    args = parser.parse_args(argv)
    desk = open_desk()

    def transcriber() -> live.TranscribePart:
        return live.online_transcriber(audio.hint_from_lexicon(desk.lexicon()))

    studio = Studio(desk, transcriber, auto=args.auto)
    studio.resume()

    def sweeper() -> None:
        while True:
            time.sleep(30)
            studio.sweep()

    threading.Thread(target=sweeper, daemon=True).start()
    server = make_server(studio, Gate(access_code(desk)), args.port)
    print(f"ecrivez-web : http://127.0.0.1:{args.port} (données : {desk.root})", flush=True)
    print(f"Code d'accès : dans le fichier {desk.root / CODE_FILE}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        studio.shutdown()
    return 0
