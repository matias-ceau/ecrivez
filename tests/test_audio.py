from pathlib import Path

import pytest

from ecrivez.audio import hint_from_lexicon, record, to_flac, transcribe
from ecrivez.writer import ToolError


class FakeWhisper:
    def __init__(self, text: str) -> None:
        self.text = text
        self.argv: list[str] = []

    def __call__(self, argv: list[str], stdin: str | None = None) -> str:
        self.argv = argv
        out = Path(argv[argv.index("--output_dir") + 1])
        (out / (Path(argv[1]).stem + ".txt")).write_text(self.text, encoding="utf-8")
        return ""


def test_transcribe_returns_text_written_by_whisper(tmp_path):
    run = FakeWhisper(" Bonjour docteur. \n")
    assert transcribe(tmp_path / "a.wav", "craving", {}, run) == "Bonjour docteur."


def test_transcribe_asks_for_french_with_hint_and_default_model(tmp_path):
    run = FakeWhisper("x")
    transcribe(tmp_path / "a.wav", "craving, diazépam", {}, run)
    argv = run.argv
    assert argv[0] == "whisper"
    assert argv[argv.index("--language") + 1] == "fr"
    assert argv[argv.index("--initial_prompt") + 1] == "craving, diazépam"
    assert argv[argv.index("--model") + 1] == "large-v3-turbo"


def test_transcribe_model_comes_from_environment(tmp_path):
    run = FakeWhisper("x")
    transcribe(tmp_path / "a.wav", "", {"ECRIVEZ_WHISPER_MODEL": "medium"}, run)
    assert run.argv[run.argv.index("--model") + 1] == "medium"
    assert "--initial_prompt" not in run.argv


def test_hint_joins_lexicon_terms():
    assert hint_from_lexicon("- craving\n- diazépam\n\n") == "craving, diazépam"


def test_hint_is_capped_at_600_characters_on_a_term_boundary():
    hint = hint_from_lexicon("\n".join(f"- terme{i:04d}" for i in range(500)))
    assert len(hint) <= 600
    assert hint.endswith(f"terme{hint.count(','):04d}")


def test_to_flac_converts_with_ffmpeg(tmp_path):
    calls = []
    to_flac(
        tmp_path / "a.wav", tmp_path / "a.flac", lambda argv, stdin=None: calls.append(argv) or ""
    )
    assert calls[0][0] == "ffmpeg"
    assert calls[0][-1] == str(tmp_path / "a.flac")
    assert str(tmp_path / "a.wav") in calls[0]


class FakeProcess:
    def __init__(self, exited: int | None = None) -> None:
        self.signals: list[int] = []
        self.waited = False
        self.exited = exited

    def poll(self) -> int | None:
        return self.exited

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return 0


def test_record_runs_until_wait_returns_then_interrupts(tmp_path):
    import signal

    proc = FakeProcess()
    spawned: list[list[str]] = []
    order: list[str] = []

    def spawn(argv: list[str]) -> FakeProcess:
        spawned.append(argv)
        return proc

    (tmp_path / "a.wav").write_bytes(b"x" * 5000)
    record(tmp_path / "a.wav", wait=lambda: order.append("waited"), spawn=spawn, settle=0)
    assert spawned[0][0] == "pw-record"
    assert spawned[0][-1] == str(tmp_path / "a.wav")
    assert order == ["waited"]
    assert proc.signals == [signal.SIGINT] and proc.waited


def test_record_fails_at_once_when_recorder_dies_at_start(tmp_path):
    waited: list[str] = []
    with pytest.raises(ToolError) as err:
        record(
            tmp_path / "a.wav",
            wait=lambda: waited.append("x"),
            spawn=lambda argv: FakeProcess(exited=1),
            settle=0,
        )
    assert "micro" in str(err.value)
    assert waited == []


def test_record_fails_when_nothing_was_captured(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x" * 44)
    with pytest.raises(ToolError):
        record(tmp_path / "a.wav", wait=lambda: None, spawn=lambda argv: FakeProcess(), settle=0)
