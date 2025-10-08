# Ecrivez Roadmap

This file expresses the upcoming milestones the autonomous agent should
implement. Each milestone should gain an **automated test** in `tests/` that is
initially _failing_. The agent is free to iterate until the whole test suite
passes.

| Milestone | Acceptance criteria |
|-----------|---------------------|
| 1. Reliable OpenAI provider | `_choose_provider` correctly picks OpenAI when the package and `OPENAI_API_KEY` are present; falls back to Echo otherwise.  Corresponding unit tests exist. |
| 2. Socket patching | Given a diff string in the REPL (`/apply` command) the Neovim buffer is patched and `:write` executed. An integration test using a mocked nvim socket passes. |
| 3. Tool calls | Chat recognises JSON tool invocations (`{"type":"tool","tool":"shell","cmd":"ls"}`) and returns combined stdout/stderr; covered by tests. |
| 4. Session persistence | On exit, chat writes conversation to `.ecrivez/sessions/<uuid>.jsonl` and loads it if existing; tested. |
| 5. Config validation | `.ecrivez/config.yaml` is validated on load via Pydantic schema; invalid keys raise a helpful error; tested. |

The agent may progress **without further human confirmation** by picking the
next unchecked milestone, writing tests first, then implementation until green.

_Time-box guideline_: spend up to **20 tool calls** per milestone before
reporting back with partial progress.
