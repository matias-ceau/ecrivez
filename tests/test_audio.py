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


class FakeOnline:
    """ffmpeg splits into two parts; the API answers one text per part."""

    def __init__(self, answers: list[dict]) -> None:
        self.answers = answers
        self.posts: list[tuple[str, str, dict]] = []
        self.ran: list[list[str]] = []

    def run(self, argv: list[str], stdin: str | None = None) -> str:
        self.ran.append(argv)
        pattern = Path(argv[-1])
        for i in range(len(self.answers)):
            (pattern.parent / f"part{i:03d}.mp3").write_bytes(f"mp3-{i}".encode())
        return ""

    def post(self, url: str, key: str, payload: dict) -> dict:
        self.posts.append((url, key, payload))
        return self.answers[len(self.posts) - 1]


def _answer(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


ONLINE = {"OPENAI_API_KEY": "sk-test", "OPENAI_BASE_URL": "https://example.test/api/v1/"}


def test_online_transcription_joins_the_parts_in_order(tmp_path):
    fake = FakeOnline([_answer("Bonjour."), _answer("Au revoir.")])
    text = transcribe(tmp_path / "a.flac", "", ONLINE, fake.run, fake.post)
    assert text == "Bonjour.\nAu revoir."
    assert fake.ran[0][0] == "ffmpeg" and "segment" in fake.ran[0]


def test_online_transcription_sends_each_part_as_base64_mp3_with_key_and_model(tmp_path):
    import base64

    fake = FakeOnline([_answer("x")])
    transcribe(tmp_path / "a.flac", "", ONLINE, fake.run, fake.post)
    url, key, payload = fake.posts[0]
    assert url == "https://example.test/api/v1/chat/completions"
    assert key == "sk-test"
    assert payload["model"] == "google/gemini-4-hydrogen"
    sound = payload["messages"][0]["content"][1]["input_audio"]
    assert sound == {"data": base64.b64encode(b"mp3-0").decode(), "format": "mp3"}


def test_online_model_and_lexicon_hint_are_configurable(tmp_path):
    fake = FakeOnline([_answer("x")])
    env = {**ONLINE, "ECRIVEZ_AUDIO_MODEL": "autre/modele"}
    transcribe(tmp_path / "a.flac", "craving, diazépam", env, fake.run, fake.post)
    payload = fake.posts[0][2]
    assert payload["model"] == "autre/modele"
    assert "craving, diazépam" in payload["messages"][0]["content"][0]["text"]


def test_inaudible_parts_count_as_nothing_heard(tmp_path):
    fake = FakeOnline([_answer("[inaudible]"), _answer(" [inaudible] ")])
    assert transcribe(tmp_path / "a.flac", "", ONLINE, fake.run, fake.post) == ""


def test_online_api_error_is_reported_as_tool_error(tmp_path):
    fake = FakeOnline([{"error": {"message": "crédit insuffisant"}}])
    with pytest.raises(ToolError) as err:
        transcribe(tmp_path / "a.flac", "", ONLINE, fake.run, fake.post)
    assert "crédit insuffisant" in str(err.value)


def test_local_backend_can_be_forced_even_with_a_key(tmp_path):
    run = FakeWhisper("local")
    env = {**ONLINE, "ECRIVEZ_TRANSCRIBER": "local"}
    assert transcribe(tmp_path / "a.wav", "", env, run) == "local"
    assert run.argv[0] == "whisper"


def test_openrouter_key_alone_enables_online_transcription(tmp_path):
    fake = FakeOnline([_answer("x")])
    transcribe(tmp_path / "a.flac", "", {"OPENROUTER_API_KEY": "sk-or-test"}, fake.run, fake.post)
    url, key, _ = fake.posts[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert key == "sk-or-test"


def test_openrouter_key_wins_over_openai_settings(tmp_path):
    fake = FakeOnline([_answer("x")])
    env = {**ONLINE, "OPENROUTER_API_KEY": "sk-or-test"}
    transcribe(tmp_path / "a.flac", "", env, fake.run, fake.post)
    url, key, _ = fake.posts[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert key == "sk-or-test"


def test_forcing_online_without_any_key_is_a_clear_error(tmp_path):
    fake = FakeOnline([_answer("x")])
    with pytest.raises(ToolError) as err:
        transcribe(tmp_path / "a.flac", "", {"ECRIVEZ_TRANSCRIBER": "online"}, fake.run, fake.post)
    assert "OPENROUTER_API_KEY" in str(err.value)
