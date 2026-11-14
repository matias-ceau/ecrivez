import pytest

from ecrivez.desk import UnknownTemplate, open_desk


@pytest.fixture
def desk(tmp_path):
    return open_desk({"ECRIVEZ_DATA": str(tmp_path / "data")})


def test_opening_seeds_tca_template(desk):
    assert "Motif de la demande" in desk.template("tca")
    assert desk.templates() == ["tca"]


def test_opening_never_overwrites_edited_template(tmp_path):
    env = {"ECRIVEZ_DATA": str(tmp_path)}
    first = open_desk(env)
    (first.root / "trames" / "tca.md").write_text("ma trame", encoding="utf-8")
    assert open_desk(env).template("tca") == "ma trame"


def test_unknown_template_lists_available(desk):
    with pytest.raises(UnknownTemplate) as err:
        desk.template("nope")
    assert err.value.available == ["tca"]


def test_last_is_none_on_empty_desk(desk):
    assert desk.last() is None


def test_save_then_last_round_trips(desk):
    folder = desk.save("source brute", "note propre", "tca")
    assert (folder / "note.txt").read_text(encoding="utf-8") == "note propre\n"
    last = desk.last()
    assert last is not None
    assert (last.source, last.note, last.template) == ("source brute", "note propre", "tca")
    assert last.dir == folder


def test_save_into_existing_folder_overwrites_note(desk):
    folder = desk.new_output_dir()
    desk.save("s", "v1", None, folder)
    desk.save("s", "v2", None, folder)
    assert desk.last().note == "v2"
    assert desk.last().template is None


def test_two_outputs_get_distinct_folders(desk):
    assert desk.new_output_dir() != desk.new_output_dir()


def test_remember_skips_duplicates(desk):
    desk.remember(["craving"], ["Plus court."])
    desk.remember(["craving"], ["Plus court."])
    assert desk.lexicon().count("craving") == 1
    assert desk.rules().count("Plus court.") == 1


def test_examples_are_read_from_folder(desk):
    (desk.root / "exemples" / "a.md").write_text("exemple un", encoding="utf-8")
    assert desk.examples() == ["exemple un"]
