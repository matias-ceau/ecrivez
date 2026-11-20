import pytest

from ecrivez.desk import open_desk
from ecrivez.writer import Revision, ToolError, draft, parse_revision, revise


class FakeRun:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, argv: list[str], stdin: str | None = None) -> str:
        self.calls.append((argv, stdin))
        return self.reply

    @property
    def system(self) -> str:
        argv = self.calls[-1][0]
        return argv[argv.index("--system-prompt") + 1]


@pytest.fixture
def desk(tmp_path):
    d = open_desk({"ECRIVEZ_DATA": str(tmp_path)})
    d.remember(["craving"], [])
    return d


def test_draft_isolates_claude_from_user_customizations(desk):
    run = FakeRun("note")
    draft(desk, "dictée", "tca", run)
    argv = run.calls[0][0]
    assert argv[:2] == ["claude", "-p"]
    assert "--safe-mode" in argv
    assert "--no-session-persistence" in argv
    assert argv[argv.index("--tools") + 1] == ""


def test_draft_sends_source_on_stdin_and_returns_stripped_note(desk):
    run = FakeRun("  note propre \n")
    assert draft(desk, "dictée en vrac", "tca", run) == "note propre"
    assert run.calls[0][1] == "dictée en vrac"


def test_draft_prompt_carries_template_lexicon_and_no_invention_rule(desk):
    run = FakeRun("note")
    draft(desk, "dictée", "tca", run)
    assert "Motif de la demande" in run.system
    assert "craving" in run.system
    assert "Non abordé" in run.system
    assert "[?]" in run.system


def test_draft_without_template_has_no_template_section(desk):
    run = FakeRun("note")
    draft(desk, "dictée", None, run)
    assert "Motif de la demande" not in run.system
    assert "TRAME" not in run.system


def test_draft_prompt_includes_examples(desk):
    (desk.root / "exemples" / "a.md").write_text("Vue ce jour. Thymie stable.", encoding="utf-8")
    run = FakeRun("note")
    draft(desk, "dictée", None, run)
    assert "Vue ce jour. Thymie stable." in run.system


def test_parse_revision_splits_note_and_memory():
    text = "note\n===MEMOIRE===\nlexique: craving\nregle: plus court"
    assert parse_revision(text) == Revision("note", ["craving"], ["plus court"])


def test_parse_revision_without_separator_keeps_whole_note():
    assert parse_revision("juste la note") == Revision("juste la note", [], [])


def test_parse_revision_ignores_unknown_and_empty_lines():
    text = "note\n===MEMOIRE===\nbla: x\n\nlexique:   \nLexique: TCA"
    assert parse_revision(text) == Revision("note", ["TCA"], [])


def test_revise_sends_previous_source_note_and_remark(desk):
    folder = desk.save("la source", "ancienne note", "tca")
    last = desk.last()
    assert last is not None and last.dir == folder
    run = FakeRun("nouvelle note\n===MEMOIRE===\nlexique: craving")
    result = revise(desk, last, "craving, pas craie vin", run)
    assert result == Revision("nouvelle note", ["craving"], [])
    stdin = run.calls[0][1] or ""
    assert "la source" in stdin and "ancienne note" in stdin and "craving, pas craie vin" in stdin
    assert "===MEMOIRE===" in run.system


def test_draft_prompt_explains_speaker_letters(desk):
    run = FakeRun("note")
    draft(desk, "A : Bonjour.\nB : Bonjour docteur.", "tca", run)
    assert "lettres en début de ligne" in run.system
    assert "qui est le médecin" in run.system
    assert "autre patient" in run.system


ONLINE = {"ECRIVEZ_DRAFT_MODEL": "anthropic/some-model", "OPENROUTER_API_KEY": "sk-test"}


class FakePost:
    def __init__(self, answer: dict) -> None:
        self.answer = answer
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, url: str, key: str, payload: dict) -> dict:
        self.calls.append((url, key, payload))
        return self.answer


def reply(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def test_draft_goes_online_when_a_draft_model_is_named(desk):
    run, post = FakeRun("jamais"), FakePost(reply("  note en ligne \n"))
    assert draft(desk, "dictée", "tca", run, ONLINE, post) == "note en ligne"
    assert run.calls == []
    url, key, payload = post.calls[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert key == "sk-test"
    assert payload["model"] == "anthropic/some-model"
    system, user = payload["messages"]
    assert system["role"] == "system"
    assert "=== TRAME ===" in system["content"] and "craving" in system["content"]
    assert user == {"role": "user", "content": "dictée"}


def test_online_draft_reports_the_service_error(desk):
    post = FakePost({"error": {"message": "crédit épuisé"}})
    with pytest.raises(ToolError, match="rédaction en ligne : crédit épuisé"):
        draft(desk, "dictée", "tca", FakeRun(""), ONLINE, post)


def test_online_draft_refuses_an_empty_answer(desk):
    with pytest.raises(ToolError, match="réponse vide"):
        draft(desk, "dictée", None, FakeRun(""), ONLINE, FakePost(reply("  ")))


def test_online_draft_without_a_key_says_which_variable_is_missing(desk):
    env = {"ECRIVEZ_DRAFT_MODEL": "anthropic/some-model"}
    with pytest.raises(ToolError, match="OPENROUTER_API_KEY"):
        draft(desk, "dictée", None, FakeRun(""), env, FakePost(reply("x")))


def test_revise_goes_online_too(desk):
    desk.save("source", "note", None)
    last = desk.last()
    assert last is not None
    post = FakePost(reply("note corrigée\n===MEMOIRE===\nlexique: craving"))
    revision = revise(desk, last, "remarque", FakeRun(""), ONLINE, post)
    assert revision == Revision("note corrigée", ["craving"], [])
    assert "=== REMARQUE DU MÉDECIN ===" in post.calls[0][2]["messages"][1]["content"]
