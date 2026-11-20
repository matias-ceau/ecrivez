"""The phone web app, tested from docs/superpowers/specs/2026-11-19-mobile.md."""

from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from ecrivez import live, web
from ecrivez.desk import Desk, open_desk
from ecrivez.writer import ToolError


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def fake_run(argv: list[str], stdin: str | None = None) -> str:
    """Stands in for ffmpeg: assembling writes the output, cutting writes two parts."""
    if "concat" in argv:
        Path(argv[-1]).write_bytes(b"flac")
    elif "segment" in argv:
        if b"illisible" in Path(argv[argv.index("-i") + 1]).read_bytes():
            raise ToolError("ffmpeg", "Invalid data found")
        for n in range(2):
            Path(argv[-1].replace("%03d", f"{n:03d}")).write_bytes(b"x")
    return ""


def transcribe(part: Path, previous: str) -> tuple[str | None, str]:
    text = f"A : {part.stem} ({part.stat().st_size} octets)"
    return text, text


class Kit:
    def __init__(self, root: Path) -> None:
        self.desk: Desk = open_desk({"ECRIVEZ_DATA": str(root)})
        self.clock = Clock()
        self.drafted: list[tuple[str, str | None]] = []
        self.mailed: list[str] = []
        self.sent_to: list[str | None] = []
        self.addresses: list[str] = []
        self.can_mail = True
        self.auto = False
        self.mail_error: ToolError | None = None
        self.heard = True
        self.draft_error: ToolError | None = None
        self.studio = self.new_studio()

    def new_studio(self) -> web.Studio:
        return web.Studio(
            self.desk,
            transcriber=lambda: transcribe if self.heard else (lambda part, previous: (None, "")),
            run=fake_run,
            draft=self.draft,
            send=self.send,
            auto=self.auto,
            can_mail=lambda: self.can_mail,
            addresses=lambda: self.addresses,
            clock=self.clock,
            retry=0,
            poll=0.01,
        )

    def send(self, note: str, *, to: str | None = None) -> None:
        if self.mail_error:
            raise self.mail_error
        self.mailed.append(note)
        self.sent_to.append(to)

    def automatic(self) -> None:
        self.auto = True
        self.studio = self.new_studio()

    def draft(self, desk: Desk, source: str, template: str | None) -> str:
        if self.draft_error:
            raise self.draft_error
        self.drafted.append((source, template))
        return "NOTE"

    def folder(self, sid: str) -> Path:
        day, hour = sid.split("_")
        return self.desk.root / "sorties" / day / hour


@pytest.fixture
def kit(tmp_path):
    k = Kit(tmp_path)
    yield k
    k.studio.shutdown()


def record(kit: Kit, chunks: list[tuple[int, int, bytes]]) -> str:
    sid = kit.studio.create()
    for tranche, rang, data in chunks:
        kit.studio.chunk(sid, tranche, rang, data)
    return sid


# -- recording from the page -----------------------------------------------------------


def test_chunks_are_appended_to_the_current_part(kit):
    sid = record(kit, [(0, 0, b"ab"), (0, 1, b"cd"), (1, 0, b"ef")])
    parts = kit.folder(sid) / "parts"
    assert (parts / "part000.webm").read_bytes() == b"abcd"
    assert (parts / "part001.webm").read_bytes() == b"ef"
    assert kit.studio.state(sid)["etat"] == "enregistrement"


def test_a_chunk_already_received_is_accepted_without_being_rewritten(kit):
    sid = record(kit, [(0, 0, b"ab"), (0, 1, b"cd")])
    assert kit.studio.chunk(sid, 0, 1, b"cd") == "deja"
    assert kit.studio.chunk(sid, 0, 0, b"ab") == "deja"
    assert (kit.folder(sid) / "parts" / "part000.webm").read_bytes() == b"abcd"


def test_a_chunk_ahead_of_the_expected_one_is_refused_with_what_is_expected(kit):
    sid = record(kit, [(0, 0, b"ab")])
    with pytest.raises(web.Refused) as e:
        kit.studio.chunk(sid, 0, 2, b"zz")
    assert e.value.status == 409
    assert e.value.extra["attendu"] == {"tranche": 0, "rang": 1}
    assert (kit.folder(sid) / "parts" / "part000.webm").read_bytes() == b"ab"


def test_a_closed_part_is_transcribed_while_the_next_one_records(kit):
    sid = record(kit, [(0, 0, b"ab"), (1, 0, b"ef")])
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert state["transcription"] == "A : part000 (2 octets)"
    assert state["etat"] == "enregistrement"
    assert (state["tranches"], state["transcrites"]) == (2, 1)


def test_stop_transcribes_the_last_part_and_assembles_the_audio(kit):
    sid = record(kit, [(0, 0, b"ab"), (1, 0, b"ef")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert state["etat"] == "terminee"
    assert state["transcription"] == "A : part000 (2 octets)\nA : part001 (2 octets)"
    assert (kit.folder(sid) / "audio.webm").exists()
    assert not (kit.folder(sid) / "parts").exists()


def test_no_chunk_is_accepted_once_the_session_is_stopped(kit):
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    with pytest.raises(web.Refused) as e:
        kit.studio.chunk(sid, 0, 1, b"cd")
    assert e.value.status == 409


def test_unknown_session_and_forged_identifiers_are_refused(kit):
    for sid in ("2026-11-19_101500", "../../etc_passwd", "x"):
        with pytest.raises(web.Refused) as e:
            kit.studio.state(sid)
        assert e.value.status == 404


# -- edge cases ------------------------------------------------------------------------


def test_a_silent_phone_gets_its_session_transcribed_after_ten_minutes(kit):
    sid = record(kit, [(0, 0, b"ab"), (1, 0, b"ef")])
    kit.clock.now += 9 * 60
    kit.studio.sweep()
    assert kit.studio.state(sid)["etat"] == "enregistrement"
    kit.clock.now += 2 * 60
    kit.studio.sweep()
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert state["etat"] == "pause"
    assert state["transcription"].endswith("A : part001 (2 octets)")
    assert (kit.folder(sid) / "parts" / "part001.webm").exists()  # audio kept as received


def test_audio_held_by_an_offline_phone_is_still_accepted_after_the_pause(kit):
    sid = record(kit, [(0, 0, b"ab")])
    kit.clock.now += 11 * 60
    kit.studio.sweep()
    kit.studio.settle(sid)
    assert kit.studio.state(sid)["transcription"] == "A : part000 (2 octets)"
    assert kit.studio.chunk(sid, 0, 1, b"cdef") == "recu"
    assert kit.studio.state(sid)["etat"] == "enregistrement"
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    assert kit.studio.state(sid)["transcription"] == "A : part000 (6 octets)"


def test_a_session_left_paused_for_half_a_day_is_closed_for_good(kit):
    sid = record(kit, [(0, 0, b"ab")])
    kit.clock.now += 11 * 60
    kit.studio.sweep()
    kit.clock.now += 13 * 3600
    kit.studio.sweep()
    kit.studio.settle(sid)
    assert kit.studio.state(sid)["etat"] == "terminee"
    assert (kit.folder(sid) / "audio.webm").exists()


def test_a_restarted_server_resumes_the_session_and_accepts_the_next_chunks(kit):
    sid = record(kit, [(0, 0, b"ab"), (1, 0, b"ef")])
    kit.studio.shutdown()
    kit.studio = kit.new_studio()
    kit.studio.resume()
    assert kit.studio.chunk(sid, 1, 0, b"ef") == "deja"
    assert kit.studio.chunk(sid, 1, 1, b"gh") == "recu"
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert state["etat"] == "terminee"
    assert state["transcription"] == "A : part000 (2 octets)\nA : part001 (4 octets)"


def test_a_chunk_half_written_by_a_crash_is_not_duplicated_when_resent(kit):
    sid = record(kit, [(0, 0, b"ab")])
    part = kit.folder(sid) / "parts" / "part000.webm"
    part.write_bytes(b"abXX")  # bytes on disk, but the server died before recording them
    kit.studio.shutdown()
    kit.studio = kit.new_studio()
    kit.studio.resume()
    kit.studio.chunk(sid, 0, 1, b"cd")
    assert part.read_bytes() == b"abcd"


def test_a_lost_chunk_never_blocks_the_following_parts(kit):
    sid = record(kit, [(0, 0, b"ab")])
    assert kit.studio.chunk(sid, 2, 0, b"ef") == "recu"  # a later part can always start
    assert (kit.folder(sid) / "parts" / "part002.webm").read_bytes() == b"ef"


def test_transcription_errors_are_retried(tmp_path):
    kit = Kit(tmp_path)
    calls = []

    def flaky(part: Path, previous: str):
        calls.append(part.name)
        if len(calls) < 3:
            raise ToolError("transcription en ligne", "service injoignable")
        return "A : ok", "A : ok"

    kit.studio.transcriber = lambda: flaky
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    assert kit.studio.state(sid)["transcription"] == "A : ok"
    assert len(calls) == 3
    kit.studio.shutdown()


# -- sending a file --------------------------------------------------------------------


def test_an_uploaded_file_is_kept_as_is_cut_in_parts_and_transcribed(kit):
    sid = kit.studio.create()
    kit.studio.upload(sid, io.BytesIO(b"contenu m4a"), 11, "Consultation 3.M4A")
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert (kit.folder(sid) / "original.m4a").read_bytes() == b"contenu m4a"
    assert state["etat"] == "terminee"
    assert state["transcription"] == "A : part000 (1 octets)\nA : part001 (1 octets)"
    assert (kit.folder(sid) / "audio.flac").exists()


def test_an_unreadable_file_is_reported_and_kept(kit):
    sid = kit.studio.create()
    kit.studio.upload(sid, io.BytesIO(b"illisible"), 9, "x.mp3")
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert "illisible" in state["erreur"]
    assert (kit.folder(sid) / "original.mp3").exists()


def test_a_file_that_is_not_audio_is_refused(kit):
    sid = kit.studio.create()
    with pytest.raises(web.Refused) as e:
        kit.studio.upload(sid, io.BytesIO(b"x"), 1, "virus.exe")
    assert e.value.status == 400


# -- the note --------------------------------------------------------------------------


def finished(kit: Kit) -> str:
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    return sid


def test_drafting_writes_the_note_with_the_chosen_template(kit):
    sid = finished(kit)
    kit.studio.start_draft(sid, "tca", "")
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert state["note"] == "NOTE" and state["redaction"] is False
    assert kit.drafted == [("A : part000 (2 octets)", "tca")]
    assert (kit.folder(sid) / "note.txt").read_text() == "NOTE\n"


def test_pasted_text_is_given_to_the_writer_under_its_own_heading(kit):
    sid = finished(kit)
    kit.studio.start_draft(sid, None, "Poids 48 kg le 12/11")
    kit.studio.settle(sid)
    source, template = kit.drafted[0]
    assert template is None
    before, after = source.split("Poids 48 kg le 12/11")
    assert "A : part000 (2 octets)" in before
    heading = before.split("A : part000 (2 octets)")[1].strip()
    assert heading and after == ""


def test_a_note_can_be_drafted_from_pasted_text_alone(kit):
    sid = kit.studio.create()
    kit.studio.start_draft(sid, None, "Patiente vue ce jour, va mieux.")
    kit.studio.settle(sid)
    assert kit.studio.state(sid)["note"] == "NOTE"


def test_drafting_is_refused_while_recording_or_with_nothing_to_write(kit):
    recording = record(kit, [(0, 0, b"ab")])
    with pytest.raises(web.Refused) as e:
        kit.studio.start_draft(recording, None, "")
    assert e.value.status == 409
    with pytest.raises(web.Refused) as e:
        kit.studio.start_draft(kit.studio.create(), None, "  ")
    assert e.value.status == 400


def test_an_unknown_template_is_refused(kit):
    with pytest.raises(web.Refused) as e:
        kit.studio.start_draft(finished(kit), "inconnue", "")
    assert e.value.status == 400


def test_a_failed_draft_is_reported_and_can_be_tried_again(kit):
    sid = finished(kit)
    kit.draft_error = ToolError("claude", "quota atteint")
    kit.studio.start_draft(sid, None, "")
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert "quota atteint" in state["erreur"] and state["note"] is None
    assert state["transcription"] == "A : part000 (2 octets)"
    kit.draft_error = None
    kit.studio.start_draft(sid, None, "")
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert state["note"] == "NOTE" and state["erreur"] is None


def test_the_note_is_mailed_only_once_it_exists(kit):
    sid = finished(kit)
    with pytest.raises(web.Refused) as e:
        kit.studio.send_mail(sid)
    assert e.value.status == 409
    kit.studio.start_draft(sid, None, "")
    kit.studio.settle(sid)
    kit.studio.send_mail(sid)
    assert kit.mailed == ["NOTE"]


# -- today's sessions ------------------------------------------------------------------


def test_todays_sessions_templates_and_part_length_are_listed(kit):
    done = finished(kit)
    live_one = record(kit, [(0, 0, b"ab")])
    kit.studio.create()  # opened but never used: not worth listing
    today = kit.studio.today()
    assert {s["id"]: s["etat"] for s in today["seances"]} == {
        done: "terminee",
        live_one: "enregistrement",
    }
    assert today["trames"] == ["psy", "tca"]
    assert today["duree_tranche"] == live.PART_SECONDS


def test_two_devices_see_the_same_session(kit):
    sid = finished(kit)
    assert kit.studio.state(sid) == kit.studio.state(sid)
    assert sid in [s["id"] for s in kit.studio.today()["seances"]]


# -- over HTTP -------------------------------------------------------------------------


# -- the note written and mailed without being asked ----------------------------------


def test_a_stopped_session_gets_its_note_drafted_and_mailed_by_itself(kit):
    kit.automatic()
    sid = kit.studio.create(web.Wish("psy"))
    kit.studio.chunk(sid, 0, 0, b"ab")
    kit.studio.finish(sid, web.Wish("tca", "Poids 52 kg"))
    kit.studio.settle(sid)
    ((source, template),) = kit.drafted
    assert template == "tca"
    assert "A : part000 (2 octets)" in source and "Poids 52 kg" in source
    assert kit.mailed == ["NOTE"]
    state = kit.studio.state(sid)
    assert state["note"] == "NOTE" and state["envoye"] and state["auto"] is False
    kit.studio.sweep()
    kit.studio.settle(sid)
    assert kit.mailed == ["NOTE"]


def test_without_a_choice_the_automatic_note_uses_the_usual_template(kit):
    kit.automatic()
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    assert kit.drafted[0][1] == "tca"


def test_the_free_form_choice_is_kept_for_the_automatic_note(kit):
    kit.automatic()
    sid = kit.studio.create(web.Wish(None))
    kit.studio.chunk(sid, 0, 0, b"ab")
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    assert kit.drafted[0][1] is None


def test_an_uploaded_file_also_ends_in_a_mailed_note(kit):
    kit.automatic()
    sid = kit.studio.create(web.Wish("psy", "Contexte"))
    kit.studio.upload(sid, io.BytesIO(b"contenu m4a"), 11, "dictaphone.m4a")
    kit.studio.settle(sid)
    assert kit.drafted[0][1] == "psy" and "Contexte" in kit.drafted[0][0]
    assert kit.mailed == ["NOTE"]


def test_nothing_is_drafted_or_mailed_unless_asked_when_automatic_notes_are_off(kit):
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid, web.Wish("tca"))
    kit.studio.settle(sid)
    assert kit.drafted == [] and kit.mailed == []


def test_a_failed_automatic_draft_is_tried_again_later(kit):
    kit.automatic()
    kit.draft_error = ToolError("claude", "hors ligne")
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    assert "Rédaction impossible" in kit.studio.state(sid)["erreur"]
    kit.draft_error = None
    kit.studio.sweep()
    kit.studio.settle(sid)
    assert kit.mailed == []  # too early: the next try waits a minute
    kit.clock.now += 61
    kit.studio.sweep()
    kit.studio.settle(sid)
    assert kit.mailed == ["NOTE"]
    assert kit.studio.state(sid)["erreur"] is None


def test_a_failed_automatic_mail_keeps_the_note_and_is_tried_again(kit):
    kit.automatic()
    kit.mail_error = ToolError("send_email.py", "SMTP")
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert state["note"] == "NOTE" and "Envoi automatique" in state["erreur"]
    kit.mail_error = None
    kit.clock.now += 61
    kit.studio.sweep()
    kit.studio.settle(sid)
    assert kit.mailed == ["NOTE"] and len(kit.drafted) == 1


def test_automatic_tries_stop_after_too_many_failures(kit):
    kit.automatic()
    kit.draft_error = ToolError("claude", "hors ligne")
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    for _ in range(web.AUTO_TRIES + 2):
        kit.clock.now += 3600
        kit.studio.sweep()
        kit.studio.settle(sid)
    assert kit.studio.state(sid)["auto"] is False
    kit.draft_error = None
    kit.clock.now += 3600
    kit.studio.sweep()
    kit.studio.settle(sid)
    assert kit.drafted == [] and kit.mailed == []


def test_a_recording_with_nothing_audible_gets_no_automatic_note(kit):
    kit.heard = False
    kit.automatic()
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    assert kit.drafted == [] and kit.mailed == []
    assert "Rien d'audible" in kit.studio.state(sid)["erreur"]


def test_mailing_by_hand_first_prevents_a_second_automatic_mail(kit):
    kit.automatic()
    kit.mail_error = ToolError("send_email.py", "SMTP")
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    kit.mail_error = None
    kit.studio.send_mail(sid)
    kit.clock.now += 3600
    kit.studio.sweep()
    kit.studio.settle(sid)
    assert kit.mailed == ["NOTE"]


# -- choosing where the note is mailed -------------------------------------------------


def auto_session(kit: Kit, wish: web.Wish) -> str:
    kit.automatic()
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid, wish)
    kit.studio.settle(sid)
    return sid


def test_the_automatic_note_goes_to_the_address_chosen_on_the_page(kit):
    sid = auto_session(kit, web.Wish("tca", mail="hopital@example.org"))
    assert kit.mailed == ["NOTE"] and kit.sent_to == ["hopital@example.org"]
    assert kit.studio.state(sid)["envoye_a"] == "hopital@example.org"


def test_without_a_chosen_address_the_note_goes_to_the_usual_one(kit):
    sid = auto_session(kit, web.Wish("tca", mail=""))
    assert kit.sent_to == [None]
    state = kit.studio.state(sid)
    assert state["envoye"] and state["envoye_a"] is None


@pytest.mark.parametrize(
    "address", ["pas une adresse", "-o@example.org", "a@b", "a@example.org,b@example.org"]
)
def test_a_malformed_address_is_ignored_and_the_note_goes_to_the_usual_one(kit, address):
    auto_session(kit, web.Wish("tca", mail=address))
    assert kit.mailed == ["NOTE"] and kit.sent_to == [None]


def test_no_mail_can_be_chosen_and_the_note_still_gets_drafted(kit):
    sid = auto_session(kit, web.Wish("tca", mail=web.NO_MAIL))
    kit.studio.sweep()
    kit.studio.settle(sid)
    state = kit.studio.state(sid)
    assert state["note"] == "NOTE" and state["envoye"] is None and state["auto"] is False
    assert kit.mailed == []


def test_the_address_chosen_when_stopping_replaces_the_one_from_the_start(kit):
    kit.automatic()
    sid = kit.studio.create(web.Wish("tca", mail="debut@example.org"))
    kit.studio.chunk(sid, 0, 0, b"ab")
    kit.studio.finish(sid, web.Wish("tca", mail="fin@example.org"))
    kit.studio.settle(sid)
    assert kit.sent_to == ["fin@example.org"]


def test_the_mail_button_sends_where_the_page_says(kit):
    sid = finished(kit)
    kit.studio.start_draft(sid, None, "")
    kit.studio.settle(sid)
    kit.studio.send_mail(sid, "ailleurs@example.org")
    kit.studio.send_mail(sid, "")
    assert kit.sent_to == ["ailleurs@example.org", None]
    with pytest.raises(web.Refused) as e:
        kit.studio.send_mail(sid, "pas une adresse")
    assert e.value.status == 400 and len(kit.mailed) == 2


def test_the_mail_button_without_a_choice_uses_the_one_of_the_session(kit):
    sid = auto_session(kit, web.Wish("tca", mail=web.NO_MAIL))
    kit.studio.send_mail(sid)
    assert kit.sent_to == [None]
    other = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(other, web.Wish("tca", mail="hopital@example.org"))
    kit.studio.settle(other)
    kit.studio.send_mail(other)
    assert kit.sent_to == [None, "hopital@example.org", "hopital@example.org"]


def test_the_page_is_given_the_addresses_to_offer(kit):
    assert kit.studio.today()["adresses"] == []
    kit.addresses = ["hopital@example.org"]
    assert kit.studio.today()["adresses"] == ["hopital@example.org"]


def test_after_a_restart_a_note_still_owed_is_drafted_and_mailed(kit):
    kit.automatic()
    kit.draft_error = ToolError("claude", "hors ligne")
    sid = record(kit, [(0, 0, b"ab")])
    kit.studio.finish(sid)
    kit.studio.settle(sid)
    kit.studio.shutdown()
    kit.draft_error = None
    kit.clock.now += 61
    kit.studio = kit.new_studio()
    kit.studio.resume()
    kit.studio.settle(sid)
    assert kit.mailed == ["NOTE"]


# -- recorded with the house out of reach, sent later ---------------------------------


def test_a_phone_that_recorded_offline_names_its_session_and_may_repeat_itself(kit):
    sid = "2026-11-20_140500-9123"
    assert kit.studio.create(web.Wish("psy"), sid) == sid
    kit.studio.chunk(sid, 0, 0, b"ab")
    assert kit.studio.create(web.Wish("tca"), sid) == sid  # sent twice: nothing is reset
    assert (kit.folder(sid) / "parts" / "part000.webm").read_bytes() == b"ab"
    assert kit.studio.state(sid)["etat"] == "enregistrement"


def test_audio_recorded_offline_is_accepted_even_if_the_opening_never_arrived(kit):
    sid = "2026-11-20_140500-9123"
    assert kit.studio.chunk(sid, 0, 0, b"ab") == "recu"
    assert (kit.folder(sid) / "parts" / "part000.webm").read_bytes() == b"ab"


@pytest.mark.parametrize("sid", ["2026-13-40_140500", "2026-11-20_996000", "../../etc", "x"])
def test_a_session_name_that_is_not_a_real_date_and_time_is_refused(kit, sid):
    with pytest.raises(web.Refused):
        kit.studio.create(None, sid)
    assert not list((kit.desk.root / "sorties").glob("*/*/web.json"))


CODE = "abcd-efgh-jkmn-pqrs-tuvw"
COOKIE = f"ecrivez={web.Gate(CODE).cookie}"


@pytest.fixture
def server(kit):
    kit.gate_clock = Clock()
    httpd = web.make_server(kit.studio, web.Gate(CODE, kit.gate_clock), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def call(
    method: str, url: str, body: bytes | None = None, cookie: str | None = COOKIE
) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=body, method=method)
    if cookie:
        request.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_a_whole_consultation_over_http(kit, server):
    status, created = call("POST", f"{server}/api/seances")
    sid = created["id"]
    assert status == 200
    assert call("PUT", f"{server}/api/seances/{sid}/tranches/0/0", b"ab")[0] == 200
    status, refused = call("PUT", f"{server}/api/seances/{sid}/tranches/0/2", b"zz")
    assert status == 409 and refused["attendu"] == {"tranche": 0, "rang": 1}
    assert call("POST", f"{server}/api/seances/{sid}/fin")[0] == 200
    kit.studio.settle(sid)
    body = json.dumps({"trame": "tca", "texte": ""}).encode()
    assert call("POST", f"{server}/api/seances/{sid}/note", body)[0] == 202
    kit.studio.settle(sid)
    status, state = call("GET", f"{server}/api/seances/{sid}")
    assert state["note"] == "NOTE" and state["etat"] == "terminee"
    assert call("POST", f"{server}/api/seances/{sid}/mail")[0] == 200
    assert kit.mailed == ["NOTE"]
    assert sid in [s["id"] for s in call("GET", f"{server}/api/seances")[1]["seances"]]


def test_a_file_is_uploaded_over_http(kit, server):
    sid = call("POST", f"{server}/api/seances")[1]["id"]
    status, _ = call("POST", f"{server}/api/seances/{sid}/fichier?nom=dictaphone.m4a", b"son")
    assert status == 202
    kit.studio.settle(sid)
    assert (kit.folder(sid) / "original.m4a").read_bytes() == b"son"


def test_a_refused_upload_leaves_the_connection_usable(kit, server):
    import http.client

    sid = kit.studio.create()
    host = server.removeprefix("http://")
    connection = http.client.HTTPConnection(host, timeout=5)
    headers = {"Cookie": COOKIE}
    connection.request(
        "POST", f"/api/seances/{sid}/fichier?nom=virus.exe", body=b"x" * 100_000, headers=headers
    )
    refused = connection.getresponse()
    assert refused.status == 400 and "audio" in json.load(refused)["erreur"]
    connection.request("GET", f"/api/seances/{sid}", headers=headers)
    again = connection.getresponse()
    assert again.status == 200 and json.load(again)["id"] == sid
    connection.close()


def test_an_oversized_chunk_is_refused(kit, server):
    sid = kit.studio.create()
    status, _ = call("PUT", f"{server}/api/seances/{sid}/tranches/0/0", b"x" * (web.MAX_CHUNK + 1))
    assert status == 413
    assert not (kit.folder(sid) / "parts").exists()


def test_the_page_and_its_install_manifest_are_served(server):
    page = urllib.request.Request(f"{server}/", headers={"Cookie": COOKIE})
    with urllib.request.urlopen(page, timeout=5) as r:
        assert "text/html" in r.headers["Content-Type"]
        assert "Enregistrer" in r.read().decode()
    with urllib.request.urlopen(f"{server}/manifest.webmanifest", timeout=5) as r:
        manifest = json.load(r)
    assert manifest["display"] == "standalone" and manifest["icons"]
    with urllib.request.urlopen(f"{server}{manifest['icons'][0]['src']}", timeout=5) as r:
        assert r.headers["Content-Type"] == "image/png"


def test_unknown_routes_and_sessions_answer_404(server):
    assert call("GET", f"{server}/api/nimporte")[0] == 404
    assert call("GET", f"{server}/api/seances/2026-01-01_000000")[0] == 404


def test_the_server_only_listens_on_this_machine(kit):
    httpd = web.make_server(kit.studio, web.Gate(CODE), port=0)
    assert httpd.server_address[0] == "127.0.0.1"
    httpd.server_close()


# -- the access code -------------------------------------------------------------------


def test_without_the_access_code_no_patient_data_is_served_or_accepted(kit, server):
    sid = finished(kit)
    assert call("GET", f"{server}/api/seances", cookie=None)[0] == 401
    assert call("GET", f"{server}/api/seances/{sid}", cookie=None)[0] == 401
    assert call("PUT", f"{server}/api/seances/{sid}/tranches/5/0", b"zz", cookie=None)[0] == 401
    assert call("POST", f"{server}/api/seances", cookie="ecrivez=deadbeef")[0] == 401
    with urllib.request.urlopen(f"{server}/", timeout=5) as r:
        page = r.read().decode()
    assert "Code d'accès" in page and "Transcription" not in page


def test_the_install_manifest_and_icon_need_no_code(server):
    for path in ("/manifest.webmanifest", "/icon-192.png"):
        with urllib.request.urlopen(f"{server}{path}", timeout=5) as r:
            assert r.status == 200


def login(server: str, code: str) -> tuple[int, str]:
    request = urllib.request.Request(
        f"{server}/api/acces", data=json.dumps({"code": code}).encode(), method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            return r.status, r.headers.get("Set-Cookie") or ""
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_the_right_code_typed_loosely_opens_the_door_for_a_long_time(server):
    status, cookie = login(server, " ABCD efgh-jkmn pqrs TUVW ")
    assert status == 200
    for flag in ("HttpOnly", "Secure", "SameSite=Strict", "Max-Age=31536000"):
        assert flag in cookie
    assert CODE not in cookie
    assert call("GET", f"{server}/api/seances", cookie=cookie.split(";")[0])[0] == 200


def test_wrong_codes_slow_down_every_further_attempt(kit, server):
    assert login(server, "mauvais-code")[0] == 403
    assert login(server, CODE)[0] == 429  # even the right one must wait
    kit.gate_clock.now += 3
    assert login(server, "encore-faux")[0] == 403
    kit.gate_clock.now += 3
    assert login(server, CODE)[0] == 429  # the wait grows with each failure
    kit.gate_clock.now += 600
    assert login(server, CODE)[0] == 200


def test_the_access_code_is_created_once_private_and_hard_to_guess(tmp_path):
    desk = open_desk({"ECRIVEZ_DATA": str(tmp_path)})
    code = web.access_code(desk)
    assert web.access_code(desk) == code
    assert len(code.replace("-", "")) >= 20
    assert (tmp_path / "web-code").stat().st_mode & 0o077 == 0
    assert web.access_code(open_desk({"ECRIVEZ_DATA": str(tmp_path / "autre")})) != code


def test_the_page_is_told_when_this_machine_cannot_send_mail(kit):
    assert kit.studio.today()["mail"] is True
    kit.can_mail = False
    assert kit.studio.today()["mail"] is False


def test_the_address_travels_over_http_with_the_stop_and_with_the_button(kit, server):
    kit.studio.auto = True
    sid = call("POST", f"{server}/api/seances")[1]["id"]
    assert call("PUT", f"{server}/api/seances/{sid}/tranches/0/0", b"ab")[0] == 200
    body = json.dumps({"trame": "tca", "texte": "", "mail": " hopital@example.org "}).encode()
    assert call("POST", f"{server}/api/seances/{sid}/fin", body)[0] == 200
    kit.studio.settle(sid)
    assert kit.sent_to == ["hopital@example.org"]
    assert call("GET", f"{server}/api/seances/{sid}")[1]["envoye_a"] == "hopital@example.org"
    again = json.dumps({"mail": ""}).encode()
    assert call("POST", f"{server}/api/seances/{sid}/mail", again)[0] == 200
    bad = json.dumps({"mail": "nulle part"}).encode()
    assert call("POST", f"{server}/api/seances/{sid}/mail", bad)[0] == 400
    assert kit.sent_to == ["hopital@example.org", None]


def test_a_session_recorded_offline_arrives_over_http_and_is_mailed(kit, server):
    kit.studio.auto = True
    sid = "2026-11-20_140500-9123"
    wish = json.dumps({"trame": "psy", "texte": "Contexte"}).encode()
    assert call("PUT", f"{server}/api/seances/{sid}", wish) == (200, {"id": sid})
    assert call("PUT", f"{server}/api/seances/{sid}/tranches/0/0", b"ab")[0] == 200
    assert call("POST", f"{server}/api/seances/{sid}/fin", wish)[0] == 200
    kit.studio.settle(sid)
    assert kit.drafted[0][1] == "psy" and "Contexte" in kit.drafted[0][0]
    assert kit.mailed == ["NOTE"]
    state = call("GET", f"{server}/api/seances/{sid}")[1]
    assert state["envoye"] and state["note"] == "NOTE"
    assert call("PUT", f"{server}/api/seances/2026-99-99_000000", b"")[0] == 400


def test_the_offline_helper_is_served_only_with_the_code_and_marks_the_real_page(server):
    worker = urllib.request.Request(f"{server}/sw.js", headers={"Cookie": COOKIE})
    with urllib.request.urlopen(worker, timeout=5) as r:
        assert "javascript" in r.headers["Content-Type"]
    assert call("GET", f"{server}/sw.js", cookie=None)[0] == 401
    page = urllib.request.Request(f"{server}/", headers={"Cookie": COOKIE})
    with urllib.request.urlopen(page, timeout=5) as r:
        assert r.headers["X-Ecrivez"] == "page"
    with urllib.request.urlopen(f"{server}/", timeout=5) as r:
        assert r.headers["X-Ecrivez"] is None
