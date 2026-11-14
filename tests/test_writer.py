import pytest

from ecrivez.desk import open_desk
from ecrivez.writer import Revision, draft, parse_revision, revise


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
