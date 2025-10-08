"""Simple interactive REPL for conversing with the configured LLM.

For the time being we keep things minimal:

* Attempts to import ``openai`` (or ``ollama``) and use the model name found
  in ``.ecrivez/config.yaml``.
* If no provider library is available, we fall back to a *local echo* model so
  the rest of the UX can be exercised without network credentials.
* Conversation context is kept in-memory only.  When the session ends the
  history is discarded – later steps can persist it if desired.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, TypedDict

import json
import sys

import yaml

from ecrivez.tools import run_shell
from ecrivez.nvim_api import connect, apply_diff
from pydantic import BaseModel, Extra, ValidationError
from typing import Optional
from pydantic import Extra

# ---------------------------------------------------------------------------
# Input processing helper (Milestone 3)
# ---------------------------------------------------------------------------
def _process_input(
    user_input: str,
    cfg: dict[str, Any],
    provider: BaseProvider,
    history: List[Message],
) -> str:
    """Process one REPL input, update history, and return assistant reply."""
    # record user turn
    history.append({"role": "user", "content": user_input})

    # shell shortcut
    if user_input.startswith("!"):
        reply = run_shell(user_input[1:])
    # JSON-based tool invocation
    elif user_input.strip().startswith("{"):
        try:
            payload = json.loads(user_input)
        except json.JSONDecodeError:
            reply = "Invalid JSON tool invocation"
        else:
            if payload.get("type") == "tool":
                tool_name = payload.get("tool")
                if tool_name == "shell":
                    reply = run_shell(payload.get("cmd", ""))
                else:
                    reply = f"Unknown tool: {tool_name}"
            else:
                reply = provider.chat_completion(history)
    # diff application
    elif user_input.startswith("/apply"):
        diff = user_input[len("/apply"):].strip()
        project = cfg.get("name", "")
        try:
            nvim = connect(project)
            apply_diff(nvim, diff)
            reply = "(diff applied)"
        except Exception as exc:
            reply = f"Error applying diff: {exc}"
    # default chat
    else:
        reply = provider.chat_completion(history)

    # record assistant turn
    history.append({"role": "assistant", "content": reply})
    return reply

__all__ = ["start_repl"]


# ---------------------------------------------------------------------------
# Helper types
# ---------------------------------------------------------------------------


class Message(TypedDict):
    role: str  # "user" | "assistant" | "system"
    content: str

# Pydantic schema for project config validation
class ProjectConfig(BaseModel):
    name: str
    model: str
    provider: str
    openai_api_key: Optional[str] = None

    class Config:
        extra = Extra.forbid


# ---------------------------------------------------------------------------
# Provider abstraction (very small for now)
# ---------------------------------------------------------------------------


class BaseProvider:  # pragma: no cover – interface only
    """Minimal abstraction for an LLM chat completion provider."""

    name: str

    def chat_completion(self, messages: List[Message]) -> str:  # noqa: D401
        """Return the assistant's next reply given the current conversation."""


class EchoProvider(BaseProvider):
    """Fallback implementation that simply echoes the last user message."""

    name = "echo"

    def chat_completion(self, messages: List[Message]) -> str:  # noqa: D401
        for msg in reversed(messages):
            if msg["role"] == "user":
                return f"(echo) {msg['content']}"
        return "(echo) <no user message>"


class OpenAIProvider(BaseProvider):
    """OpenAI wrapper (only instantiated if ``openai`` is importable)."""

    def __init__(self, model: str) -> None:
        import openai  # type: ignore  # noqa: WPS433

        self._openai = openai
        self._model = model

    @property
    def name(self) -> str:  # noqa: D401
        return f"openai:{self._model}"

    def chat_completion(self, messages: List[Message]) -> str:  # noqa: D401
        response = self._openai.chat.completions.create(  # type: ignore[attr-defined]
            model=self._model,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        )
        # OpenAI v1 API returns choices[0].message.content
        return response.choices[0].message.content  # type: ignore[index]


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------


def _load_config() -> dict[str, Any]:
    """Load project config from .ecrivez/config.yaml and validate."""
    cfg_path = Path(".ecrivez/config.yaml")
    if not cfg_path.exists():
        print("Error: not inside an Ecrivez project – run 'ecrivez init' first.", file=sys.stderr)
        sys.exit(1)
    # Load config file
    with cfg_path.open() as fh:
        data = yaml.safe_load(fh) or {}
    # Validate against Pydantic schema
    try:
        proj_cfg = ProjectConfig(**data)
    except ValidationError as exc:
        print(f"Config validation error:\n{exc}", file=sys.stderr)
        sys.exit(1)
    return proj_cfg.dict()


def _choose_provider(cfg: dict[str, Any]) -> BaseProvider:
    """Return the best‐available provider based on *cfg* contents."""

    model_name: str = cfg.get("model", "gpt-4o")
    provider_name: str = cfg.get("provider", "openai")

    if provider_name.lower() == "openai":
        try:
            import importlib

            openai = importlib.import_module("openai")

            import os

            # API key resolution – env var wins, then config field, then openai.api_key
            api_key = (
                os.getenv("OPENAI_API_KEY")
                or cfg.get("openai_api_key")
                or getattr(openai, "api_key", None)
            )
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY not set – export it or add 'openai_api_key' "
                    "to .ecrivez/config.yaml",
                )

            openai.api_key = api_key  # type: ignore[attr-defined]

            return OpenAIProvider(model_name)
        except ModuleNotFoundError as exc:
            print(
                "OpenAI provider requested but 'openai' package not installed. "
                "Install it with 'uv add openai' or switch provider to 'echo' in config.",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            raise SystemExit(1) from exc

    # Fallback to echo for unknown providers
    return EchoProvider()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_repl() -> None:  # noqa: WPS231 – small enough
    """Interactive session executed in the *second* tmux pane or standalone."""

    cfg = _load_config()
    provider = _choose_provider(cfg)

    # generate a session ID for persistence
    import uuid
    session_id = uuid.uuid4().hex
    print(f"🖋  Ecrivez REPL – provider = {provider.name}, session = {session_id}  (Ctrl-D to quit)\n")
    history = _load_history(session_id)

    try:
        while True:
            try:
                user_input = input("you › ")
            except EOFError:
                print()
                break
            if not user_input.strip():
                continue

            assistant_reply = _process_input(user_input, cfg, provider, history)
            print("llm › " + assistant_reply)
    except KeyboardInterrupt:
        print("\nInterrupted – goodbye!")
    # persist history
    _save_history(history, session_id)


# ---------------------------------------------------------------------------
# Persistence (very simple, opt-in later)
# ---------------------------------------------------------------------------


def _save_history(history: List[Message]) -> None:
    """Store the conversation next to the session for debugging."""

    sessions_dir = Path(".ecrivez") / "sessions"
    sessions_dir.mkdir(exist_ok=True)
    out_file = sessions_dir / "last_session.jsonl"

    with out_file.open("w") as fh:
        for item in history:
            json.dump(item, fh, ensure_ascii=False)
            fh.write("\n")
