import time
from pathlib import Path

import pytest

from ecrivez.cli import Deps, copy_to_clipboard, main
from ecrivez.desk import open_desk
from ecrivez.writer import ToolError


class World:
    """Fakes for every program the tool launches, plus scripted keyboard input."""

    def __init__(self, tmp_path: Path) -> None:
        self.env = {"ECRIVEZ_DATA": str(tmp_path / "data")}
        self.desk = open_desk(self.env)
        self.replies = ["NOTE PROPRE"]
        self.heard = "transcription brute"
        self.fail: str | None = None
        self.mic_error: ToolError | None = None
        self.calls: list[list[str]] = []
        self.clipboard = ""
        self.keys: list[str] = []
        self.lines: list[str] = []
        self.printed: list[str] = []
        self.errors: list[str] = []
        self.recorded = 0

    def run(self, argv: list[str], stdin: str | None = None) -> str:
        self.calls.append(argv)
        prog = argv[0]
        if prog == self.fail:
            raise ToolError(prog, "programme introuvable")
        if prog == "claude":
            return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if prog == "whisper":
            out = Path(argv[argv.index("--output_dir") + 1])
            (out / (Path(argv[1]).stem + ".txt")).write_text(self.heard, encoding="utf-8")
        if prog == "ffmpeg":
            Path(argv[-1]).write_bytes(b"flac")
        return ""

    def copy(self, text: str) -> None:
        if self.fail == "wl-copy":
            raise ToolError("wl-copy", "programme introuvable")
        self.clipboard = text

    def record(self, dest: Path) -> None:
        if self.mic_error:
            raise self.mic_error
        self.recorded += 1
        dest.write_bytes(b"w" * 5000)

    def deps(self) -> Deps:
        return Deps(
            env=self.env,
            run=self.run,
            record=self.record,
            copy=self.copy,
            key=lambda: self.keys.pop(0),
            read=lambda prompt="": self.lines.pop(0),
            out=self.printed.append,
            err=self.errors.append,
        )

    def programs(self) -> list[str]:
        return [c[0] for c in self.calls]

    def system(self, i: int = -1) -> str:
        argv = [c for c in self.calls if c[0] == "claude"][i]
        return argv[argv.index("--system-prompt") + 1]

    def folders(self) -> list[Path]:
        return sorted(p for p in (self.desk.root / "sorties").glob("*/*") if p.is_dir())


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_texte_drafts_saves_prints_and_copies(world):
    assert main(["texte", "augmenté le valium"], world.deps()) == 0
    (folder,) = world.folders()
    assert (folder / "note.txt").read_text(encoding="utf-8") == "NOTE PROPRE\n"
    assert (folder / "source.txt").read_text(encoding="utf-8") == "augmenté le valium\n"
    assert world.clipboard == "NOTE PROPRE"
    assert "NOTE PROPRE" in world.printed
    assert any(str(folder / "note.txt") in line for line in world.printed)


def test_texte_without_template_is_a_free_observation(world):
    main(["texte", "phrase"], world.deps())
    assert "TRAME" not in world.system()


def test_unknown_template_stops_before_any_work(world):
    assert main(["texte", "phrase", "nope"], world.deps()) == 2
    assert world.calls == []
    assert "nope" in world.errors[0] and "tca" in world.errors[0]


def test_fichier_keeps_a_copy_of_the_audio_and_drafts(world, tmp_path):
    vocal = tmp_path / "vocal.m4a"
    vocal.write_bytes(b"audio")
    assert main(["fichier", str(vocal), "tca"], world.deps()) == 0
    (folder,) = world.folders()
    assert (folder / "audio.m4a").read_bytes() == b"audio"
    assert (folder / "source.txt").read_text(encoding="utf-8") == "transcription brute\n"
    assert "Motif de la demande" in world.system()


def test_fichier_missing_file_is_reported(world, tmp_path):
    assert main(["fichier", str(tmp_path / "absent.m4a")], world.deps()) == 2
    assert "absent.m4a" in world.errors[0]
    assert world.calls == []


def test_empty_transcription_stops_before_claude_and_keeps_audio(world, tmp_path):
    vocal = tmp_path / "vocal.m4a"
    vocal.write_bytes(b"audio")
    world.heard = "  "
    assert main(["fichier", str(vocal)], world.deps()) == 2
    assert "claude" not in world.programs()
    (folder,) = world.folders()
    assert (folder / "audio.m4a").exists()
    assert str(folder) in world.errors[0]


def test_claude_failure_names_the_program_and_keeps_audio(world, tmp_path):
    vocal = tmp_path / "vocal.m4a"
    vocal.write_bytes(b"audio")
    world.fail = "claude"
    assert main(["fichier", str(vocal)], world.deps()) == 2
    assert "claude" in world.errors[0]
    (folder,) = world.folders()
    assert (folder / "audio.m4a").exists()
    assert (folder / "source.txt").read_text(encoding="utf-8") == "transcription brute\n"


def test_clipboard_failure_does_not_lose_the_note(world):
    world.fail = "wl-copy"
    assert main(["texte", "phrase"], world.deps()) == 0
    assert "NOTE PROPRE" in world.printed


def test_menu_typed_text_then_remark_is_remembered(world):
    world.keys = ["t", "q"]
    world.lines = ["elle a du craie vin", "craving, pas craie vin", ""]
    world.replies = ["NOTE V1", "NOTE V2\n===MEMOIRE===\nlexique: craving"]
    assert main([], world.deps()) == 0
    (folder,) = world.folders()
    assert (folder / "note.txt").read_text(encoding="utf-8") == "NOTE V2\n"
    assert "craving" in world.desk.lexicon()
    assert "Retenu (lexique) : craving" in world.printed
    assert world.clipboard == "NOTE V2"


def test_menu_revision_without_memory_block_still_delivers_note(world):
    world.keys = ["t", "q"]
    world.lines = ["phrase", "plus court", ""]
    world.replies = ["NOTE V1", "NOTE V2"]
    main([], world.deps())
    assert world.desk.lexicon() == ""
    assert "NOTE V2" in world.printed


def test_menu_uses_tca_template_by_default(world):
    world.keys = ["t", "q"]
    world.lines = ["phrase", ""]
    main([], world.deps())
    assert "Motif de la demande" in world.system()


def test_menu_m_switches_to_free_observation_and_remembers_it(world):
    world.keys = ["m", "t", "q"]
    world.lines = ["phrase", ""]
    main([], world.deps())
    assert "TRAME" not in world.system()
    world.keys = ["t", "q"]
    world.lines = ["phrase", ""]
    main([], world.deps())
    assert "TRAME" not in world.system()


def test_menu_consult_records_keeps_flac_and_drafts(world):
    world.keys = ["c", "q"]
    world.lines = [""]
    main([], world.deps())
    (folder,) = world.folders()
    assert world.recorded == 1
    assert (folder / "audio.flac").exists()
    assert not (folder / "audio.wav").exists()
    assert (folder / "note.txt").exists()


def test_menu_keeps_wav_when_flac_conversion_fails(world):
    world.keys = ["c", "q"]
    world.lines = [""]
    world.fail = "ffmpeg"
    main([], world.deps())
    (folder,) = world.folders()
    assert (folder / "audio.wav").exists()
    assert (folder / "note.txt").exists()


def test_menu_microphone_error_is_shown_and_menu_goes_on(world):
    world.keys = ["c", "q"]
    world.mic_error = ToolError("pw-record", "impossible d'ouvrir le micro")
    assert main([], world.deps()) == 0
    assert "micro" in world.errors[0]
    assert "claude" not in world.programs()


def test_menu_unknown_key_is_ignored(world):
    world.keys = ["x", "q"]
    assert main([], world.deps()) == 0
    assert world.calls == []


def test_menu_file_choice_asks_for_a_path(world, tmp_path):
    vocal = tmp_path / "vocal.m4a"
    vocal.write_bytes(b"audio")
    world.keys = ["f", "q"]
    world.lines = [f"'{vocal}'", ""]
    main([], world.deps())
    (folder,) = world.folders()
    assert (folder / "audio.m4a").exists()


def test_clipboard_does_not_wait_for_wl_copy_background_daemon(tmp_path, monkeypatch):
    fake = tmp_path / "wl-copy"
    fake.write_text("#!/bin/sh\ncat > /dev/null\nsleep 20 &\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    start = time.monotonic()
    copy_to_clipboard("note")
    assert time.monotonic() - start < 5


def test_clipboard_missing_program_raises_tool_error(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ToolError):
        copy_to_clipboard("note")
