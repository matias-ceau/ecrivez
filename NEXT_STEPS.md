# Ecrivez: Immediate Next Steps

This document provides actionable implementation tasks based on the exploration in [EXPLORATION.md](EXPLORATION.md).

## Critical Bugs to Fix (Priority 0)

### 1. Fix Session History Loading
**File:** `src/ecrivez/chat.py`
**Issue:** `_load_history()` is called but not implemented
**Impact:** Sessions cannot be resumed

```python
def _load_history(session_id: str) -> List[Message]:
    """Load conversation history from disk."""
    sessions_dir = Path(".ecrivez") / "sessions"
    session_file = sessions_dir / f"{session_id}.jsonl"
    
    if not session_file.exists():
        return []
    
    history = []
    with session_file.open() as fh:
        for line in fh:
            if line.strip():  # Skip empty lines
                history.append(json.loads(line))
    return history
```

**Tests to add:**
- `test_save_and_load_history`
- `test_load_nonexistent_history`
- `test_load_corrupted_history`

### 2. Fix Session Save Signature
**File:** `src/ecrivez/chat.py`
**Issue:** `_save_history()` signature doesn't match call site
**Current:** `_save_history(history: List[Message])`
**Expected:** `_save_history(history: List[Message], session_id: str)`

```python
def _save_history(history: List[Message], session_id: str) -> None:
    """Store the conversation next to the session for debugging."""
    sessions_dir = Path(".ecrivez") / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    out_file = sessions_dir / f"{session_id}.jsonl"
    
    with out_file.open("w") as fh:
        for item in history:
            json.dump(item, fh, ensure_ascii=False)
            fh.write("\n")
```

### 3. Improve Diff Application
**File:** `src/ecrivez/nvim_api.py`
**Issue:** Naive line-based diff parsing doesn't handle unified diffs properly
**Solution:** Use `unidiff` library for proper patch parsing

```bash
# Add dependency
uv add unidiff
```

```python
from unidiff import PatchSet

def apply_diff(nvim, diff: str) -> None:
    """Apply a proper unified diff to the current buffer."""
    try:
        patch = PatchSet(diff)
    except Exception as e:
        # Fallback to simple parsing for non-standard diffs
        _apply_simple_diff(nvim, diff)
        return
    
    buf: List[str] = list(nvim.current.buffer)
    
    for patched_file in patch:
        if patched_file.is_modified_file:
            for hunk in patched_file:
                buf = _apply_hunk(buf, hunk)
    
    nvim.current.buffer[:] = buf
    nvim.command("write")

def _apply_hunk(buf: List[str], hunk) -> List[str]:
    """Apply a single hunk to buffer."""
    # Implementation for proper hunk application
    # Handle line numbers, context, additions, deletions
    pass
```

---

## Quick Wins (Priority 1) - 1-2 weeks

### 4. Add Missing Tests
Create `tests/test_session_persistence.py`:

```python
import pytest
import json
from pathlib import Path
from ecrivez.chat import _save_history, _load_history

def test_session_roundtrip(tmp_path, monkeypatch):
    """Test saving and loading a session."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".ecrivez" / "sessions").mkdir(parents=True)
    
    session_id = "test123"
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    
    _save_history(history, session_id)
    loaded = _load_history(session_id)
    
    assert loaded == history

def test_load_empty_session(tmp_path, monkeypatch):
    """Test loading non-existent session returns empty list."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".ecrivez" / "sessions").mkdir(parents=True)
    
    history = _load_history("nonexistent")
    assert history == []
```

### 5. Add CLI Command for Session Management

```python
# src/ecrivez/cli.py
@click.command()
def sessions():
    """List and manage sessions."""
    from .session import list_sessions
    sessions = list_sessions()
    
    if not sessions:
        click.echo("No sessions found.")
        return
    
    click.echo("\nAvailable sessions:")
    for session in sessions:
        click.echo(f"  {session['id'][:8]}... - {session['name']} ({session['created_at']})")

@click.command()
@click.argument('session_id')
def resume(session_id):
    """Resume a previous session."""
    from .chat import resume_session
    resume_session(session_id)

# Add to group
ecrivez.add_command(sessions)
ecrivez.add_command(resume)
```

### 6. Improve Error Messages

```python
# src/ecrivez/chat.py
def _choose_provider(cfg: dict[str, Any]) -> BaseProvider:
    """Return the best‐available provider based on *cfg* contents."""
    
    # ... existing code ...
    
    except ModuleNotFoundError as exc:
        click.echo(click.style(
            "❌ OpenAI provider requested but 'openai' package not installed.",
            fg='red'
        ))
        click.echo("\nTo fix this, run:")
        click.echo(click.style("  uv add openai", fg='cyan'))
        click.echo("\nOr change provider to 'echo' in .ecrivez/config.yaml:")
        click.echo(click.style("  provider: echo", fg='cyan'))
        raise SystemExit(1) from exc
```

---

## Foundation Work (Priority 2) - 2-4 weeks

### 7. Complete Roadmap Milestones

Track in `tests/test_milestones.py`:

```python
def test_milestone_1_reliable_provider():
    """Milestone 1: _choose_provider correctly picks OpenAI when package and key present."""
    # Already passing
    pass

def test_milestone_2_socket_patching():
    """Milestone 2: /apply command patches Neovim buffer."""
    # Needs improved diff application (issue #3)
    pass

def test_milestone_3_tool_calls():
    """Milestone 3: JSON tool invocations work."""
    # Already passing
    pass

def test_milestone_4_session_persistence():
    """Milestone 4: Conversation saves and loads."""
    # Needs fixes from issues #1 and #2
    pass

def test_milestone_5_config_validation():
    """Milestone 5: Config validation with helpful errors."""
    # Already passing
    pass
```

### 8. Add Configuration File Improvements

Create `src/ecrivez/config/loader.py`:

```python
from pathlib import Path
import yaml
from typing import Dict, Any

class ConfigLoader:
    """Multi-layer configuration system."""
    
    def load(self) -> Dict[str, Any]:
        """Load config from multiple sources with precedence."""
        config = {}
        
        # 1. Defaults
        config.update(self._get_defaults())
        
        # 2. User config
        user_config = Path.home() / ".config" / "ecrivez" / "config.yaml"
        if user_config.exists():
            config.update(yaml.safe_load(user_config.read_text()))
        
        # 3. Project config
        project_config = Path(".ecrivez") / "config.yaml"
        if project_config.exists():
            config.update(yaml.safe_load(project_config.read_text()))
        
        # 4. Environment variables
        config.update(self._load_from_env())
        
        return config
    
    def _get_defaults(self) -> Dict[str, Any]:
        return {
            "model": "gpt-4o",
            "provider": "openai",
            "editor": "nvim",
            "autosave": True,
        }
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load ECRIVEZ_* environment variables."""
        import os
        config = {}
        for key, value in os.environ.items():
            if key.startswith("ECRIVEZ_"):
                config_key = key[8:].lower()  # Remove ECRIVEZ_ prefix
                config[config_key] = value
        return config
```

### 9. Add Logging

```python
# src/ecrivez/logging.py
import logging
from pathlib import Path

def setup_logging(level: str = "INFO"):
    """Configure logging for ecrivez."""
    log_dir = Path.home() / ".local" / "share" / "ecrivez" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "ecrivez.log"),
            logging.StreamHandler()
        ]
    )
```

---

## Feature Development (Priority 3) - 4-8 weeks

### 10. Implement Basic Agent Framework

Create `src/ecrivez/agents/`:

```
agents/
├── __init__.py
├── base.py          # Base agent class
├── code_agent.py    # Agent for code-related tasks
├── tools.py         # Agent-specific tools
└── prompts.py       # Agent system prompts
```

**File: `src/ecrivez/agents/base.py`**
```python
from smolagents import Agent, Tool
from typing import List, Dict, Any

class EcrivezAgent:
    """Base autonomous agent."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools = self._load_tools()
        self.agent = Agent(
            model=self._create_model(),
            tools=self.tools,
            system_prompt=self._get_system_prompt()
        )
    
    def execute_task(self, task: str) -> Dict[str, Any]:
        """Execute a task with the agent."""
        return self.agent.run(task)
    
    def _load_tools(self) -> List[Tool]:
        """Load available tools for this agent."""
        return []
    
    def _create_model(self):
        """Create LLM model instance."""
        from smolagents import OpenAIModel
        return OpenAIModel(self.config['model'])
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for this agent."""
        return "You are a helpful coding assistant."
```

### 11. Create Tool Registry

```python
# src/ecrivez/tools/registry.py
from typing import Dict, Type, Callable
from smolagents import Tool

class ToolRegistry:
    """Registry for discovering and loading tools."""
    
    def __init__(self):
        self._tools: Dict[str, Type[Tool]] = {}
    
    def register(self, name: str, tool: Type[Tool]):
        """Register a tool."""
        self._tools[name] = tool
    
    def get(self, name: str) -> Type[Tool]:
        """Get a tool by name."""
        return self._tools[name]
    
    def list(self) -> List[str]:
        """List all registered tools."""
        return list(self._tools.keys())
    
    def load_from_entrypoints(self):
        """Load tools from setuptools entry points."""
        from importlib.metadata import entry_points
        
        eps = entry_points()
        if hasattr(eps, 'select'):  # Python 3.10+
            tool_eps = eps.select(group='ecrivez.tools')
        else:  # Python 3.9
            tool_eps = eps.get('ecrivez.tools', [])
        
        for ep in tool_eps:
            tool = ep.load()
            self.register(ep.name, tool)

# Global registry instance
registry = ToolRegistry()
```

### 12. Add Basic RAG Support

```python
# src/ecrivez/rag/indexer.py
from pathlib import Path
from typing import List, Dict, Any

class SimpleIndexer:
    """Simple file-based indexing for small projects."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.index: Dict[str, str] = {}
    
    def index_project(self):
        """Index all Python files."""
        for py_file in self.project_root.rglob("*.py"):
            if self._should_index(py_file):
                self.index[str(py_file)] = py_file.read_text()
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Simple text search."""
        results = []
        for file_path, content in self.index.items():
            if query.lower() in content.lower():
                results.append({
                    "file": file_path,
                    "content": content
                })
        return results
    
    def _should_index(self, path: Path) -> bool:
        """Check if file should be indexed."""
        # Skip common ignore patterns
        ignore_patterns = [
            "__pycache__", ".git", ".venv", "venv",
            "node_modules", ".pytest_cache"
        ]
        return not any(pattern in str(path) for pattern in ignore_patterns)
```

---

## Documentation (Priority 4) - Ongoing

### 13. Improve README

Add sections:
- Quick start guide with examples
- Architecture diagram
- Contributing guide
- Troubleshooting

### 14. Add Inline Documentation

```python
# Example for chat.py
"""
chat.py - Interactive REPL for LLM conversations
================================================

This module provides the core chat/REPL functionality for Ecrivez.

Key Components:
--------------
- BaseProvider: Abstract interface for LLM providers
- EchoProvider: Fallback provider that echoes input
- OpenAIProvider: Integration with OpenAI API
- _process_input: Main message processing loop
- start_repl: Entry point for interactive session

Usage:
------
    from ecrivez.chat import start_repl
    start_repl()

See Also:
---------
- cli.py: Command-line interface
- project.py: Project initialization
"""
```

### 15. Create Developer Guide

Create `CONTRIBUTING.md`:
- Development setup
- Running tests
- Code style guide
- PR process
- Architecture overview

---

## Testing Strategy

### Unit Tests
- ✅ Provider selection
- ✅ Config validation
- ✅ Tool invocation
- 🚧 Session persistence
- 🚧 Diff application
- ❌ Agent execution
- ❌ RAG search

### Integration Tests
- ❌ Full init → chat → save workflow
- ❌ Multi-session management
- ❌ Tool chaining
- ❌ Neovim integration

### E2E Tests
- ❌ CLI command workflows
- ❌ Session replay
- ❌ Configuration layers

---

## Dependency Management

### Current Dependencies to Review

1. **Keep:**
   - click, pydantic, pyyaml (core)
   - openai, pynvim (integrations)
   - libtmux (terminal management)

2. **Evaluate:**
   - gradio (unused, remove if not needed)
   - pyqt6 (experimental UI, document or remove)
   - smolagents (integrate or remove)

3. **Add:**
   - unidiff (for proper diff parsing)
   - pytest-cov (test coverage)
   - ruff (linting, if not already used)

```bash
# Remove unused
uv remove gradio  # If not used

# Add needed
uv add unidiff pytest-cov

# Development tools
uv add --dev ruff mypy types-PyYAML
```

---

## Success Criteria

### Week 1-2
- ✅ All critical bugs fixed (issues #1, #2, #3)
- ✅ Test coverage for session persistence
- ✅ All roadmap milestones passing

### Week 3-4
- ✅ Quick wins implemented (#4-#6)
- ✅ Improved error messages
- ✅ Session management CLI commands

### Week 5-8
- ✅ Configuration system improvements
- ✅ Basic logging
- ✅ Documentation updates
- ✅ Roadmap milestones completed

### Week 9-16
- ✅ Agent framework MVP
- ✅ Tool registry
- ✅ Basic RAG support
- ✅ Integration tests

---

## Decision Points

### Immediate (Week 1)
**Decision:** Keep or remove Qt UI code?
- **Option A:** Remove (simplify, focus on terminal)
- **Option B:** Keep but document as experimental
- **Recommendation:** Option B - It's interesting work, just mark clearly

**Decision:** Integrate smolagents now or later?
- **Option A:** Start integration now (Priority 3)
- **Option B:** Defer until after roadmap completion
- **Recommendation:** Option B - Stabilize core first

### Short Term (Month 1)
**Decision:** Which direction to pursue first after roadmap?
- **Option A:** Direction 1 (Agents) - Most ambitious
- **Option B:** Direction 4 (Sessions) - Most practical
- **Option C:** Both in parallel - Best synergy
- **Recommendation:** Option C - They complement each other

### Medium Term (Month 3)
**Decision:** RAG implementation approach?
- **Option A:** Simple file-based search (quick, limited)
- **Option B:** Full vector DB (powerful, complex)
- **Option C:** Start simple, migrate to vector DB
- **Recommendation:** Option C - Progressive enhancement

---

## Resources Needed

### Development
- Python 3.13+ environment
- OpenAI API key for testing
- Neovim with socket support
- tmux for terminal management

### Testing
- Multiple LLM providers for testing
- Sample projects for RAG testing
- CI/CD environment (GitHub Actions)

### Documentation
- Mermaid for architecture diagrams
- MkDocs or Sphinx for docs site
- Demo videos/GIFs

---

## Questions to Resolve

1. **Target Audience:** 
   - Power users (Neovim/terminal enthusiasts)?
   - General developers (broader appeal)?
   - AI researchers (experimentation platform)?

2. **License:**
   - Current: Not specified in pyproject.toml
   - Recommendation: Add MIT or Apache 2.0

3. **Package Distribution:**
   - PyPI publishing strategy
   - Version numbering scheme
   - Release cadence

4. **Community:**
   - Discord/Slack for users?
   - GitHub Discussions for Q&A?
   - Contributing guidelines

---

## Monitoring and Metrics

Track these metrics weekly:

```python
# metrics.yaml
development:
  - loc: Lines of code (target: stable ~5000)
  - test_coverage: Test coverage % (target: >80%)
  - type_coverage: Mypy coverage (target: 100%)
  - open_issues: Open GitHub issues (target: trend down)

quality:
  - bug_density: Bugs per 1000 LOC
  - test_pass_rate: % tests passing
  - ci_build_time: CI pipeline duration

adoption:
  - stars: GitHub stars
  - forks: GitHub forks
  - downloads: PyPI downloads
  - active_users: Telemetry opt-in (if implemented)
```

---

*Last Updated: 2025-10-23*
*Status: Ready for Implementation*
