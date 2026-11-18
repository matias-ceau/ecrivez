"""Recording (PipeWire) and local transcription (openai-whisper CLI)."""

from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ecrivez.writer import Run, ToolError, run_tool

DEFAULT_MODEL = "large-v3-turbo"
HINT_LIMIT = 600
WAV_HEADER = 44
ONLINE = "transcription en ligne"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_AUDIO_MODEL = "google/gemini-4-hydrogen"
PART_SECONDS = 600
INAUDIBLE = "[inaudible]"
ONLINE_PROMPT = (
    "Transcris mot à mot cet enregistrement en français (consultation ou dictée médicale, "
    "psychiatrie). N'ajoute rien, ne résume pas, ne commente pas. Distingue les personnes à "
    "leur voix : la première voix est A, la deuxième B ; toute autre voix (téléphone, autre "
    "personne) reçoit la lettre suivante. Écris une ligne par prise de parole, au format "
    f"exact : A : texte. Un passage incompréhensible est noté {INAUDIBLE}. "
    f"Si rien n'est audible, réponds exactement : {INAUDIBLE}"
)
CONTEXT_LINES = 8
CONTINUATION = (
    "\nCet extrait est la suite d'un enregistrement. Voici la fin de la transcription "
    "précédente : garde les mêmes lettres pour les mêmes voix et ne la recopie pas.\n---\n{}\n---"
)


def _spawn(argv: list[str]) -> Any:
    try:
        return subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise ToolError(argv[0], "programme introuvable") from None


def record(
    dest: Path,
    wait: Callable[[], object] = input,
    spawn: Callable[[list[str]], Any] = _spawn,
    settle: float = 0.7,
) -> None:
    """Record the default microphone into `dest` until `wait()` returns."""
    proc = spawn(["pw-record", "--rate", "16000", "--channels", "1", str(dest)])
    time.sleep(settle)
    if proc.poll() is not None:
        raise ToolError("pw-record", "impossible d'ouvrir le micro (branché ? sélectionné ?)")
    try:
        wait()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)
    if not dest.exists() or dest.stat().st_size <= WAV_HEADER:
        raise ToolError("pw-record", "aucun son capté par le micro")


def to_flac(src: Path, dest: Path, run: Run = run_tool) -> None:
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), str(dest)], None)


def hint_from_lexicon(lexicon: str) -> str:
    hint = ""
    for line in lexicon.splitlines():
        term = line.strip().removeprefix("-").strip()
        if not term:
            continue
        candidate = f"{hint}, {term}" if hint else term
        if len(candidate) > HINT_LIMIT:
            break
        hint = candidate
    return hint


def post_json(url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except ValueError:
            raise ToolError(ONLINE, f"erreur HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ToolError(ONLINE, f"service injoignable ({e})") from None


Post = Callable[[str, str, dict[str, Any]], dict[str, Any]]
Warn = Callable[[str], None]


def _silent(_: str) -> None:
    pass


def _transcribe_local(audio: Path, hint: str, env: Mapping[str, str], run: Run) -> str:
    model = env.get("ECRIVEZ_WHISPER_MODEL") or DEFAULT_MODEL
    with tempfile.TemporaryDirectory() as out:
        argv = ["whisper", str(audio), "--model", model, "--language", "fr"]
        argv += ["--output_format", "txt", "--output_dir", out, "--verbose", "False"]
        if hint:
            argv += ["--initial_prompt", hint]
        run(argv, None)
        result = Path(out) / f"{audio.stem}.txt"
        return result.read_text(encoding="utf-8").strip() if result.exists() else ""


def _account(env: Mapping[str, str]) -> tuple[str, str]:
    """(base URL, key): OpenRouter's own variable first, OpenAI-style settings otherwise."""
    if key := env.get("OPENROUTER_API_KEY"):
        return DEFAULT_BASE_URL, key
    return (env.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"), env["OPENAI_API_KEY"]


def _transcribe_online(
    audio: Path, hint: str, env: Mapping[str, str], run: Run, post: Post, warn: Warn
) -> str:
    base, key = _account(env)
    model = env.get("ECRIVEZ_AUDIO_MODEL") or DEFAULT_AUDIO_MODEL
    prompt = ONLINE_PROMPT + (f"\nTermes susceptibles d'apparaître : {hint}" if hint else "")
    texts: list[str | None] = []
    previous = ""
    with tempfile.TemporaryDirectory() as tmp:
        argv = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio)]
        argv += ["-ac", "1", "-ar", "16000", "-b:a", "48k"]
        argv += ["-f", "segment", "-segment_time", str(PART_SECONDS), f"{tmp}/part%03d.mp3"]
        run(argv, None)
        for part in sorted(Path(tmp).glob("part*.mp3")):
            sound = {"data": base64.b64encode(part.read_bytes()).decode(), "format": "mp3"}
            content = [
                {
                    "type": "text",
                    "text": prompt + (CONTINUATION.format(previous) if previous else ""),
                },
                {"type": "input_audio", "input_audio": sound},
            ]
            payload = {
                "model": model,
                "temperature": 0,
                "reasoning": {"effort": "minimal"},
                "messages": [{"role": "user", "content": content}],
            }
            answer = post(f"{base}/chat/completions", key, payload)
            if "error" in answer or not answer.get("choices"):
                detail = (answer.get("error") or {}).get("message") or "réponse vide"
                raise ToolError(ONLINE, str(detail))
            text = (answer["choices"][0]["message"].get("content") or "").strip()
            if text.replace(INAUDIBLE, "").strip():
                texts.append(text)
                previous = "\n".join(text.splitlines()[-CONTEXT_LINES:])
            else:
                texts.append(None)
    if not any(texts):
        return ""
    for number, text in enumerate(texts, 1):
        if text is None:
            warn(f"  Attention : tranche {number} inaudible (10 minutes sans rien de transcrit)")
    return "\n".join(t or f"[tranche {n} inaudible]" for n, t in enumerate(texts, 1))


def transcribe(
    audio: Path,
    hint: str,
    env: Mapping[str, str] = os.environ,
    run: Run = run_tool,
    post: Post = post_json,
    warn: Warn = _silent,
) -> str:
    """Online when an API key is set (or forced), local Whisper otherwise."""
    has_key = bool(env.get("OPENROUTER_API_KEY") or env.get("OPENAI_API_KEY"))
    choice = env.get("ECRIVEZ_TRANSCRIBER") or ("online" if has_key else "local")
    if choice == "local":
        return _transcribe_local(audio, hint, env, run)
    if not has_key:
        raise ToolError(ONLINE, "variable OPENROUTER_API_KEY absente")
    return _transcribe_online(audio, hint, env, run, post, warn)
