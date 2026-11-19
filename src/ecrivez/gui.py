"""A small window: record a consultation, watch it transcribe, draft the note."""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from collections.abc import Mapping
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from ecrivez import audio, live, writer
from ecrivez.cli import _current_template, copy_to_clipboard
from ecrivez.desk import Desk, open_desk
from ecrivez.writer import ToolError

FREE = "libre"
RED = "#D14D41"
BG = "#100F0F"
FIELD = "#282726"
FG = "#CECDC3"
ACCENT = "#4385BE"


class App:
    def __init__(self, root: tk.Tk, desk: Desk, env: Mapping[str, str] = os.environ) -> None:
        self.root = root
        self.desk = desk
        self.env = env
        self.events: queue.Queue[tuple[object, str, str]] = queue.Queue()
        self.session: live.Session | None = None
        self.recorder: live.Recorder | None = None
        self.recording = threading.Event()
        self.workers: list[live.Worker] = []
        self.started = 0.0
        self.drafting = False

        root.title("Ecrivez")
        root.geometry("760x680")
        root.protocol("WM_DELETE_WINDOW", self.close)

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")
        self.button = tk.Button(
            top, text="●  Enregistrer", font=("Sans", 16, "bold"), fg=RED, width=16,
            command=self.toggle,
        )  # fmt: skip
        self.button.pack(side="left")
        self.clock = ttk.Label(top, text="00:00", font=("Sans", 20))
        self.clock.pack(side="left", padx=16)
        ttk.Label(top, text="Trame :").pack(side="left", padx=(16, 4))
        names = [*desk.templates(), FREE]
        self.template = tk.StringVar(value=_current_template(desk) or FREE)
        ttk.Combobox(
            top, textvariable=self.template, values=names, state="readonly", width=10
        ).pack(side="left")

        self.status = ttk.Label(root, text="Prêt.", padding=(10, 0), wraplength=720)
        self.status.pack(fill="x")

        panes = ttk.PanedWindow(root, orient="vertical")
        panes.pack(fill="both", expand=True, padx=10, pady=6)
        frame_t = ttk.Labelframe(panes, text="Transcription (modifiable)")
        self.transcript = ScrolledText(frame_t, wrap="word", height=12, font=("Sans", 11))
        self.transcript.pack(fill="both", expand=True)
        frame_n = ttk.Labelframe(panes, text="Note")
        self.note = ScrolledText(frame_n, wrap="word", height=10, font=("Sans", 11))
        self.note.pack(fill="both", expand=True)
        panes.add(frame_t, weight=3)
        panes.add(frame_n, weight=2)

        bottom = ttk.Frame(root, padding=10)
        bottom.pack(fill="x")
        self.draft_button = ttk.Button(bottom, text="Rédiger la note", command=self.draft)
        self.draft_button.pack(side="left")
        ttk.Button(bottom, text="Copier la note", command=self.copy).pack(side="left", padx=6)
        ttk.Button(bottom, text="Ouvrir le dossier", command=self.open_folder).pack(side="left")

        self.resume()
        root.after(300, self.tick)

    # -- recording ---------------------------------------------------------------------

    def _worker(self, session: live.Session, recording: threading.Event) -> live.Worker:
        hint = audio.hint_from_lexicon(self.desk.lexicon())
        transcriber = live.online_transcriber(hint, self.env)
        worker = live.Worker(
            session, transcriber, lambda m: self.events.put((session, "info", m)), recording
        )
        self.workers.append(worker)
        worker.start()
        return worker

    def toggle(self) -> None:
        if self.recording.is_set():
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        session = live.Session(self.desk.new_output_dir())
        recorder = live.Recorder(session)
        try:
            recorder.start()
        except ToolError as e:
            messagebox.showerror("Micro", str(e))
            return
        self.session, self.recorder = session, recorder
        self.recording = threading.Event()
        self.recording.set()
        self.started = time.monotonic()
        self._worker(session, self.recording)
        self.transcript.delete("1.0", "end")
        self.note.delete("1.0", "end")
        self.button.config(text="■  Arrêter", fg=FG)
        self.set_status(f"Enregistrement… (dossier {session.folder})")

    def stop(self) -> None:
        if self.recorder:
            self.recorder.stop()
        self.recording.clear()
        self.button.config(text="●  Enregistrer", fg=RED)
        self.set_status("Enregistrement terminé. Fin de la transcription…")

    def resume(self) -> None:
        sessions = live.unfinished_sessions(self.desk.root)
        for session in sessions:
            self._worker(session, threading.Event())
        if sessions:
            self.session = sessions[-1]
            self.show_transcript()
            self.set_status(
                f"Séance interrompue retrouvée ({self.session.folder.name}) : "
                "fin de la transcription en cours, rien n'est perdu."
            )

    # -- display -----------------------------------------------------------------------

    def set_status(self, text: str) -> None:
        self.status.config(text=text)

    def show_transcript(self) -> None:
        if self.session is None:
            return
        self.transcript.delete("1.0", "end")
        self.transcript.insert("1.0", self.session.transcript())
        self.transcript.see("end")

    def tick(self) -> None:
        if self.recording.is_set():
            elapsed = int(time.monotonic() - self.started)
            self.clock.config(text=f"{elapsed // 60:02d}:{elapsed % 60:02d}")
            if self.recorder and not self.recorder.alive():
                self.set_status("Le micro a décroché : relance de l'enregistrement…")
                try:
                    self.recorder.start()
                except ToolError as e:
                    self.set_status(f"Micro perdu ({e}). Nouvel essai dans un instant.")
        while True:
            try:
                session, kind, message = self.events.get_nowait()
            except queue.Empty:
                break
            self.handle(session, kind, message)
        self.root.after(500, self.tick)

    def handle(self, session: object, kind: str, message: str) -> None:
        if kind == "note":
            self.drafting = False
            self.draft_button.config(state="normal")
            self.note.delete("1.0", "end")
            self.note.insert("1.0", message)
            try:
                copy_to_clipboard(message)
                self.set_status("Note rédigée et copiée dans le presse-papiers.")
            except ToolError:
                self.set_status("Note rédigée.")
            return
        if kind == "error":
            self.drafting = False
            self.draft_button.config(state="normal")
            self.set_status(message)
            return
        if self.session is None or session is not self.session:
            return
        if message in ("tranche transcrite", "terminé", "tranche illisible ignorée"):
            self.show_transcript()
        if message == "terminé":
            self.set_status(f"Transcription terminée. Audio et texte dans {self.session.folder}")
        elif message != "tranche transcrite" or not self.recording.is_set():
            self.set_status(message)

    # -- note --------------------------------------------------------------------------

    def draft(self) -> None:
        if self.drafting:
            return
        if self.session is None:
            messagebox.showinfo("Ecrivez", "Rien à rédiger : enregistre d'abord une séance.")
            return
        if self.recording.is_set():
            messagebox.showinfo("Ecrivez", "Arrête l'enregistrement avant de rédiger.")
            return
        source = self.transcript.get("1.0", "end").strip()
        if not source:
            messagebox.showinfo("Ecrivez", "La transcription est vide (ou pas encore prête).")
            return
        template = None if self.template.get() == FREE else self.template.get()
        folder = self.session.folder
        self.drafting = True
        self.draft_button.config(state="disabled")
        self.set_status("Rédaction de la note…")

        def work() -> None:
            try:
                note = writer.draft(self.desk, source, template)
                self.desk.save(source, note, template, folder)
                self.events.put((None, "note", note))
            except ToolError as e:
                self.events.put((None, "error", f"Rédaction impossible : {e}. Rien n'est perdu."))

        threading.Thread(target=work, daemon=True).start()

    def copy(self) -> None:
        text = self.note.get("1.0", "end").strip()
        if text:
            try:
                copy_to_clipboard(text)
                self.set_status("Note copiée.")
            except ToolError as e:
                self.set_status(str(e))

    def open_folder(self) -> None:
        folder = self.session.folder if self.session else self.desk.root / "sorties"
        subprocess.Popen(
            ["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def close(self) -> None:
        if self.recording.is_set():
            if not messagebox.askyesno("Ecrivez", "Arrêter l'enregistrement et quitter ?"):
                return
            self.stop()
        busy = [w for w in self.workers if not w.done.is_set()]
        if busy and not messagebox.askyesno(
            "Ecrivez",
            "La transcription n'est pas finie. Quitter quand même ? "
            "Elle reprendra au prochain lancement.",
        ):
            return
        self.root.destroy()


def apply_palette(root: tk.Tk) -> None:
    """Own every colour: Tk reads ~/.Xdefaults raw, where names may be unknown or clash."""
    for option, value in {
        "*background": BG,
        "*foreground": FG,
        "*selectBackground": ACCENT,
        "*selectForeground": BG,
        "*insertBackground": FG,
        "*activeBackground": FIELD,
        "*activeForeground": FG,
        "*highlightBackground": BG,
        "*highlightColor": ACCENT,
        "*troughColor": FIELD,
        "*Text.background": FIELD,
    }.items():
        root.option_add(option, value, "interactive")
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=FIELD)
    style.configure("TButton", background=FIELD, padding=6)
    style.map("TButton", background=[("active", "#403E3C")], foreground=[("disabled", "#6F6E69")])
    style.configure("TLabelframe.Label", background=BG, foreground="#878580")
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", FIELD)],
        foreground=[("readonly", FG)],
        selectbackground=[("readonly", FIELD)],
        selectforeground=[("readonly", FG)],
    )


def main() -> int:
    root = tk.Tk()
    apply_palette(root)
    App(root, open_desk())
    root.mainloop()
    return 0
