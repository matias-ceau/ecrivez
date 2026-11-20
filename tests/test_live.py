import threading
from pathlib import Path

import pytest

from ecrivez import live
from ecrivez.writer import ToolError


def make_parts(session: live.Session, n: int) -> list[Path]:
    session.parts_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for i in range(n):
        p = session.parts_dir / f"part{i:03d}.flac"
        p.write_bytes(b"x")
        parts.append(p)
    return parts


def fake_assemble(argv: list[str], stdin: str | None) -> str:
    Path(argv[-1]).write_bytes(b"flac")
    return ""


def test_record_command_writes_closed_flushed_parts_and_never_overwrites():
    argv = live.record_command(Path("/x/parts"), 120, start=3)
    assert argv[:2] == ["ffmpeg", "-nostdin"]
    assert argv[argv.index("-segment_time") + 1] == "120"
    assert argv[argv.index("-segment_start_number") + 1] == "3"
    assert "flush_packets=1" in argv
    assert argv[-1] == "/x/parts/part%03d.flac"


def test_the_part_being_recorded_is_not_pending(tmp_path):
    s = live.Session(tmp_path)
    parts = make_parts(s, 3)
    assert s.pending(recording=True) == parts[:2]
    assert s.pending(recording=False) == parts


def test_transcript_grows_part_by_part_with_context_from_previous_part(tmp_path):
    s = live.Session(tmp_path)
    a, b, c = make_parts(s, 3)
    s.store(a, "A : bonjour", "[00:00] A : bonjour")
    s.store(b, None, "[inaudible]")
    assert s.transcript() == "A : bonjour\n" + live.INAUDIBLE_PART
    assert (tmp_path / live.TRANSCRIPT).read_text().startswith("A : bonjour")
    assert s.context(c) == "[00:00] A : bonjour"
    assert s.pending(recording=False) == [c]


def run_worker(s: live.Session, transcribe, recording=None, **kw) -> live.Worker:
    w = live.Worker(
        s, transcribe, lambda m: None, recording or threading.Event(), run=fake_assemble,
        retry=0, poll=0, **kw,
    )  # fmt: skip
    w.run()
    return w


def test_worker_transcribes_everything_then_assembles_and_keeps_text(tmp_path):
    s = live.Session(tmp_path)
    make_parts(s, 2)
    seen = []

    def transcribe(part: Path, previous: str):
        seen.append((part.name, previous))
        return f"A : {part.stem}", f"[00:00] A : {part.stem}"

    w = run_worker(s, transcribe)
    assert seen == [("part000.flac", ""), ("part001.flac", "[00:00] A : part000")]
    assert w.audio == tmp_path / "audio.flac"
    assert not s.parts_dir.exists()
    assert s.transcript() == "A : part000\nA : part001"
    assert w.done.is_set()


def test_worker_retries_network_errors_until_it_works(tmp_path):
    s = live.Session(tmp_path)
    make_parts(s, 1)
    calls = []

    def transcribe(part: Path, previous: str):
        calls.append(1)
        if len(calls) < 3:
            raise ToolError("transcription en ligne", "service injoignable")
        return "A : ok", "A : ok"

    run_worker(s, transcribe)
    assert len(calls) == 3
    assert s.transcript() == "A : ok"


def test_a_part_cut_off_by_a_crash_is_skipped_not_retried_forever(tmp_path):
    s = live.Session(tmp_path)
    _, broken = make_parts(s, 2)
    broken.write_bytes(b"")

    def transcribe(part: Path, previous: str):
        if part == broken:
            raise live.BrokenPart("audio vide")
        return "A : ok", "A : ok"

    listed = []

    def assemble(argv, stdin):
        listed.append(Path(argv[argv.index("-i") + 1]).read_text())
        return fake_assemble(argv, stdin)

    w = live.Worker(s, transcribe, lambda m: None, threading.Event(), run=assemble, retry=0)
    w.run()
    assert listed == ["file 'part000.flac'\n"]
    assert live.BROKEN_PART in s.transcript()


def test_failed_assembly_keeps_the_parts(tmp_path):
    s = live.Session(tmp_path)
    make_parts(s, 1)

    def broken_ffmpeg(argv, stdin):
        raise ToolError("ffmpeg", "échec")

    w = live.Worker(
        s, lambda p, prev: ("A : ok", "A : ok"), lambda m: None, threading.Event(),
        run=broken_ffmpeg, retry=0,
    )  # fmt: skip
    w.run()
    assert s.parts_dir.exists() and len(s.parts()) == 1
    assert w.audio is None


def test_interrupted_sessions_are_found_unless_a_live_process_holds_them(tmp_path):
    day = tmp_path / "sorties" / "2026-11-19"
    mine, other, done = (live.Session(day / n) for n in ("100000", "110000", "120000"))
    for s in (mine, other):
        make_parts(s, 1)
    done.folder.mkdir(parents=True)
    other.lock.write_text("1")  # pid 1 is always alive
    dead = live.Session(day / "130000")
    make_parts(dead, 1)
    dead.lock.write_text("999999999")
    found = [s.folder.name for s in live.unfinished_sessions(tmp_path)]
    assert found == ["100000", "130000"]


@pytest.mark.parametrize("pid", ["abc", ""])
def test_unreadable_lock_does_not_block_resume(tmp_path, pid):
    s = live.Session(tmp_path)
    s.lock.write_text(pid)
    assert not s.busy()


def make_phone_parts(session: live.Session, suffixes: list[str]) -> None:
    session.parts_dir.mkdir(parents=True, exist_ok=True)
    for i, suffix in enumerate(suffixes):
        part = session.parts_dir / f"part{i:03d}{suffix}"
        part.write_bytes(b"x")
        part.with_suffix(".txt").write_text("A : texte\n")


def test_compressed_parts_are_joined_as_they_are_not_inflated_to_flac(tmp_path):
    s = live.Session(tmp_path)
    make_phone_parts(s, [".webm", ".webm"])
    calls: list[list[str]] = []

    def run(argv: list[str], stdin: str | None) -> str:
        calls.append(argv)
        return fake_assemble(argv, stdin)

    assert s.assemble(run) == tmp_path / "audio.webm"
    assert len(calls) == 1
    assert calls[0][-3:-1] == ["-c", "copy"]
    assert s.audio() == tmp_path / "audio.webm"
    assert not s.parts_dir.exists()


def test_parts_that_cannot_be_joined_as_they_are_fall_back_to_flac(tmp_path):
    s = live.Session(tmp_path)
    make_phone_parts(s, [".webm", ".webm"])

    def run(argv: list[str], stdin: str | None) -> str:
        if "copy" in argv:
            Path(argv[-1]).write_bytes(b"half")
            raise ToolError("ffmpeg", "Non-monotonic DTS")
        return fake_assemble(argv, stdin)

    assert s.assemble(run) == tmp_path / "audio.flac"
    assert not (tmp_path / "audio.webm").exists()


def test_parts_of_different_formats_are_joined_into_flac(tmp_path):
    s = live.Session(tmp_path)
    make_phone_parts(s, [".webm", ".ogg"])
    assert s.assemble(fake_assemble) == tmp_path / "audio.flac"
