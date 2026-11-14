# Ecrivez Secretary v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A CLI that turns a rough dictation, an audio file or a recorded consultation into a clean French medical note following the doctor's templates, and remembers corrections.

**Architecture:** Four small stdlib modules: `desk` (private data folder), `audio` (record + local transcription), `writer` (prompt building + `claude -p` call + memory parsing), `cli` (argparse wiring). External programs are called through one injectable `run` function so tests never touch the microphone, Whisper or the network.

**Tech Stack:** Python 3.13 stdlib only, `uv`, `pytest`, `ruff`, `pyright`; external binaries `pw-record`, `ffmpeg`, `whisper-cli` (whisper.cpp), `claude`, `wl-copy`.

**Spec:** `SPEC.md`

## Global Constraints

- No runtime dependencies in `pyproject.toml`; dev group: `pytest`, `ruff`, `pyright`.
- Branch `dev/secretary`. Commit after each green task.
- Data folder: `$ECRIVEZ_DATA`, default `~/.local/share/ecrivez/`. Nothing patient-related is ever written inside the repo.
- Whisper model: `$ECRIVEZ_WHISPER_MODEL`, default `~/.local/opt/whisper.cpp/models/ggml-large-v3.bin`.
- Drafting call, verified working on the subscription (5 s on the diazepam example):
  `claude -p --safe-mode --tools "" --no-session-persistence --system-prompt <system>` with the user content on stdin. `--safe-mode` is required: the user's hooks and output styles would otherwise leak into the note.
- Code, identifiers, commits in English. Prompts, templates and CLI messages in French.
- Type hints on public signatures. No real network, microphone or model in tests.

## Review Focus

- Template name that does not exist → French error listing available templates, exit code 2, nothing recorded.
- Empty or silent transcription → stop before calling Claude, say so, keep the audio file.
- `ecrivez non` with no previous output → French error, exit code 2.
- `claude` or `whisper-cli` missing or failing → French one-line error with the program name; audio is kept, never deleted on failure.
- Memory block malformed or absent in a revision → the revised note is still delivered; nothing is appended to `lexique.md`/`regles.md`.

## Amendments (2026-11-14, after user review — these override the tasks below)

- **Audio is always kept.** Record straight into the output folder; after transcription convert to `audio.flac` next to the note and remove the WAV only once the FLAC exists. No `--garder-audio` flag, no automatic deletion anywhere.
- **Output is plain text.** `desk.save` writes `note.txt` and `source.txt` (no Markdown markup in the note; the system prompt forbids `#`, `*`, tables). The CLI prints the path of `note.txt`.
- **Menu first.** `ecrivez` with no argument opens a one-key menu: `c` consult, `d` dictate, `f` audio file, `t` typed text, `m` change template, `q` quit. Recording stops on Enter. After each note the prompt `Une remarque ? (Entrée = c'est bon)` loops `revise` until an empty answer. Subcommands kept: `fichier`, `texte`; `non` is dropped.
- **Transcription backend is swappable.** `transcribe` dispatches on `ECRIVEZ_TRANSCRIBER` (`local` default). Only `local` is implemented in v0; the seam is the function signature.
- Menu logic lives in `src/ecrivez/menu.py` as `run_menu(desk, read=input, out=print) -> None` so tests drive it with scripted answers.

---

### Task 1: Clean slate and data desk

**Files:**
- Delete: `src/ecrivez/{chat,editor,nvim_api,project}.py`, `src/ecrivez/{config,ui,tools}/`, `src/ecrivez/resources/templates/`, all of `tests/`, `dev/`, `.opencode/`, `OpenCode.md`, `ARCHITECTURE.md`, `EXPLORATION.md`, `NEXT_STEPS.md`, `PROJECT_EXPLORATION_SUMMARY.md`, `QUICK_REFERENCE.md`, `ROADMAP.md`, `ecrivez.qmd`, `ecrivez.html`, `ecrivez_files/`, `_quarto.yml`, `pytest.ini`, `uv.lock`, the root symlink `ecrivez`
- Modify: `pyproject.toml` (description, no dependencies, script `ecrivez = "ecrivez.cli:main"`, pytest `testpaths = ["tests"]`), `README.md` (short French usage from SPEC commands)
- Create: `src/ecrivez/desk.py`, `src/ecrivez/resources/trames/tca.md`, `src/ecrivez/resources/regles.md`, `tests/test_desk.py`

**Interfaces — Produces:**
```python
@dataclass(frozen=True)
class Desk:
    root: Path
    def template(self, name: str) -> str            # raises UnknownTemplate(name, available)
    def templates(self) -> list[str]
    def examples(self) -> list[str]
    def lexicon(self) -> str
    def rules(self) -> str
    def save(self, source: str, note: str, template: str | None) -> Path   # sorties/YYYY-MM-DD/HHMMSS/{source.txt,note.md,meta.json}
    def last(self) -> SavedNote | None               # SavedNote(dir, source, note, template)
    def remember(self, lexicon: list[str], rules: list[str]) -> None       # append lines, skip duplicates

def open_desk(env: Mapping[str, str] = os.environ) -> Desk   # creates folders, seeds trames/tca.md and regles.md if absent
```
`tca.md` headings, provisional until the doctor supplies his own: Motif de la demande; Antécédents (médicaux, psychiatriques, familiaux); Allergies; Mode de vie; Histoire de la maladie; Examen clinique; Conduite à tenir.

- [ ] Write `tests/test_desk.py` using `tmp_path` as `ECRIVEZ_DATA`: seeding creates `trames/tca.md`; seeding never overwrites an edited template; `template("nope")` raises `UnknownTemplate` whose `.available == ["tca"]`; `save` then `last` round-trips source, note and template; `last()` is `None` on an empty desk; `remember(["craving"], [])` twice leaves one `craving` line.
- [ ] Run `uv run pytest -q` → fails on import.
- [ ] Delete the listed files, rewrite `pyproject.toml`, `uv lock`, implement `desk.py`.
- [ ] `uv run pytest -q` green; `uv run ruff check --fix && uv run ruff format && uv run pyright`.
- [ ] Commit `refactor: replace coding-agent prototype with secretary data desk`.

### Task 2: Writer

**Files:** Create `src/ecrivez/writer.py`, `tests/test_writer.py`

**Interfaces:**
- Consumes: `Desk`
- Produces:
```python
Run = Callable[[list[str], str | None], str]      # (argv, stdin) -> stdout; raises ToolError(program, detail)
def run_tool(argv: list[str], stdin: str | None = None) -> str   # real implementation, subprocess
def draft(desk: Desk, source: str, template: str | None, run: Run = run_tool) -> str
def revise(desk: Desk, last: SavedNote, remark: str, run: Run = run_tool) -> Revision   # Revision(note, lexicon, rules)
def parse_revision(text: str) -> Revision
```
System prompt (French) must state: secretary of a hospital psychiatrist; source may be a dictation or a raw consultation transcript with speech-recognition errors to correct from context using the lexicon; fill the template headings in order, or write a short free observation when no template; add nothing absent from the source; heading not covered → `Non abordé`; doubtful passage → `[?]`; names kept as spoken; INN drug names; output the note only. Examples, lexicon and rules are appended in labelled sections.
Revision output format: the note, then a line `===MEMOIRE===`, then zero or more lines `lexique: <term>` or `regle: <sentence>`. The remark is classified by the model: a misheard word → `lexique`, a style or content instruction worth keeping → `regle`, a one-off fix → neither.

- [ ] Tests with a fake `run` capturing argv and stdin: `draft` passes `--safe-mode`, `--tools`, `""`, `--no-session-persistence`; system prompt contains the template text, the lexicon and `Non abordé`; stdin is the source; without template the prompt contains no template section. `parse_revision("note\n===MEMOIRE===\nlexique: craving\nregle: plus court")` → `Revision("note", ["craving"], ["plus court"])`; no separator → whole text is the note, empty lists; unknown line prefixes ignored. `revise` sends previous source, previous note and the remark.
- [ ] Fail, implement, green, lint, commit `feat: draft and revise notes through claude -p`.

### Task 3: Audio

**Files:** Create `src/ecrivez/audio.py`, `tests/test_audio.py`

**Interfaces — Produces:**
```python
def record(dest: Path) -> None          # pw-record --rate 16000 --channels 1 dest; returns on Ctrl-C (SIGINT forwarded, KeyboardInterrupt swallowed)
def to_wav(src: Path, dest: Path, run: Run = run_tool) -> None     # ffmpeg -y -i src -ar 16000 -ac 1 dest
def transcribe(wav: Path, hint: str, env: Mapping[str, str] = os.environ, run: Run = run_tool) -> str
```
`transcribe` calls `whisper-cli -m <model> -l fr -nt -np --prompt <hint> -f <wav>` and returns stripped stdout. `hint` is the lexicon terms joined by commas, truncated to 600 characters. Confirm the exact flag names with `whisper-cli --help` before coding; adjust the test to the real names.

- [ ] Tests with fake `run`: argv contains the model path from `ECRIVEZ_WHISPER_MODEL`, `-l fr`, the hint; a 5000-character lexicon gives a hint ≤ 600 characters; `to_wav` argv shape.
- [ ] Fail, implement, green, lint.
- [ ] Manual check: `ffmpeg -f lavfi -i sine=d=1` is not speech — instead record 10 s with `pw-record`, say « craving, diazépam, anorexie mentale restrictive », and print the transcription.
- [ ] Commit `feat: local recording and whisper.cpp transcription`.

### Task 4: CLI

**Files:** Create `src/ecrivez/cli.py`, `tests/test_cli.py`; Modify `src/ecrivez/__main__.py`

**Interfaces:**
- Consumes: everything above
- Produces: `def main(argv: list[str] | None = None) -> int`

Subcommands exactly as in SPEC: `consult [trame]` (default `tca`), `dicte [trame]` (default none), `fichier <audio> [trame]`, `texte <phrase> [trame]`, `non <remarque>`; global flag `--garder-audio`. Flow: resolve template first → get source (record/convert/transcribe, or the text) → `draft` → `desk.save` → print note → `wl-copy`. `non`: `desk.last()` → `revise` → `desk.remember` → save → print → copy, then print one line per remembered item (`Retenu (lexique) : craving`). Recordings go to `desk.root / "audio"`; deleted after a successful draft unless `--garder-audio`.

- [ ] Tests (monkeypatch `audio.record`, `audio.transcribe`, `writer.run_tool`, clipboard): `texte "…"` prints the fake note, saves it, returns 0; the five Review Focus cases, each asserting exit code, French message on stderr, and that the audio file still exists where relevant; `non` appends `craving` to `lexique.md`.
- [ ] Fail, implement, green, lint, pyright.
- [ ] `uv tool install -e .`, then real end-to-end: `ecrivez texte "<diazepam sentence from SPEC>"` and a 20-second `ecrivez dicte tca`; then `ecrivez non "craving, pas craie vin"` and check `lexique.md`.
- [ ] Commit `feat: ecrivez CLI for consult, dictation, file, text and corrections`.
