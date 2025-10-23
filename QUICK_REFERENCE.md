# Ecrivez Quick Reference Card

## 🎯 Project Overview

**Ecrivez** is a terminal-based autonomous coding assistant that integrates LLMs with development workflows.

- **Language:** Python 3.13+
- **Architecture:** Modular, provider-based
- **Current State:** ~1000 LOC, early development
- **License:** MIT (recommended to add)

## 📊 Current Status

### ✅ Implemented
- CLI interface (init, config, chat, repl)
- OpenAI + Echo provider system
- JSON tool invocation
- Neovim socket integration
- Config validation with Pydantic
- Tmux-based editor setup

### ⚠️ Partially Complete
- Session persistence (save works, load missing)
- Diff application (naive parsing)

### ❌ Planned
- Agent framework
- RAG/semantic search
- Workflow automation
- Session replay
- MCP protocol

## 🚀 Five Strategic Directions

| Direction | Focus | Priority | Timeline |
|-----------|-------|----------|----------|
| **1. Agentic Workflow** | Autonomous task execution | ⭐ High | Months 4-6 |
| **2. RAG Enhancement** | Codebase understanding | ⭐ High | Months 7-9 |
| **3. Multi-Modal UI** | Rich GUI experience | Medium | Months 10-12 |
| **4. Session Management** | Persistence & replay | ⭐ High | Months 4-6 |
| **5. MCP Integration** | Protocol standardization | Medium | Months 10-12 |

**Recommended:** Combine Directions 1 + 4 (Agents + Sessions) for best synergy

## 🔧 Immediate Actions (Week 1-2)

### Critical Bugs
1. **Fix `_load_history()`** - Function is called but not implemented
2. **Fix `_save_history(session_id)`** - Signature mismatch
3. **Improve diff parsing** - Use `unidiff` library

### Quick Wins
4. Add missing tests for session persistence
5. Create CLI commands for session management
6. Improve error messages with colors and help

## 📁 Code Structure

```
ecrivez/
├── src/ecrivez/
│   ├── cli.py              # Click commands
│   ├── chat.py             # REPL + providers
│   ├── editor.py           # Tmux integration
│   ├── nvim_api.py         # Neovim socket
│   ├── project.py          # Project management
│   ├── tools/              # Built-in tools
│   │   └── __init__.py     # Shell runner
│   ├── config/             # Configuration
│   │   ├── config.py       # Main config
│   │   ├── paths.py        # XDG paths
│   │   └── ...
│   └── ui/                 # Experimental Qt UI
│       └── qt_interface.py
├── tests/                  # Test suite
├── EXPLORATION.md          # This exploration doc
├── NEXT_STEPS.md           # Actionable tasks
└── ARCHITECTURE.md         # Visual diagrams
```

## 🧪 Testing Commands

```bash
# Install dependencies (requires Python 3.13)
uv sync

# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_chat_provider.py

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/

# Format code
uv run ruff format src/
```

## 💡 Key Concepts

### Provider System
```python
# Abstract provider interface
class BaseProvider:
    def chat_completion(self, messages: List[Message]) -> str:
        pass

# Implementations
class EchoProvider(BaseProvider):  # Fallback
class OpenAIProvider(BaseProvider): # OpenAI API
```

### Tool Invocation
```python
# JSON-based tool calls
{"type": "tool", "tool": "shell", "cmd": "ls -la"}

# Shell shortcuts
!echo "hello"

# Diff application
/apply +added line
        -removed line
```

### Session Structure
```python
# Session message format
{
    "role": "user|assistant|system|tool",
    "content": "message text"
}

# Stored as JSONL
.ecrivez/sessions/{session_id}.jsonl
```

## 🎨 Development Workflow

### 1. Initialize Project
```bash
ecrivez init --model gpt-4o --name myproject
cd myproject
```

### 2. Configure
```bash
# Set API key
export OPENAI_API_KEY=sk-...

# Or add to config
echo "openai_api_key: sk-..." >> .ecrivez/config.yaml
```

### 3. Start REPL
```bash
ecrivez repl
```

### 4. Start Editor Mode
```bash
ecrivez chat --file myproject.py
```

## 📦 Dependencies

### Core (Keep)
- `click` - CLI framework
- `pydantic` - Data validation
- `pyyaml` - Config files
- `openai` - LLM provider
- `pynvim` - Editor integration
- `libtmux` - Terminal management

### To Add
- `unidiff` - Proper diff parsing
- `pytest-cov` - Test coverage
- `ruff` - Linting

### To Evaluate
- `gradio` - Unused? Remove or integrate
- `pyqt6` - Experimental UI, document or remove
- `smolagents` - Integrate in Phase 2

## 🗺️ Roadmap Milestones

| # | Milestone | Status | Tests |
|---|-----------|--------|-------|
| 1 | Reliable OpenAI provider | ✅ Done | ✅ Pass |
| 2 | Socket patching | ⚠️ Partial | ⚠️ Needs work |
| 3 | Tool calls | ✅ Done | ✅ Pass |
| 4 | Session persistence | ⚠️ Partial | ❌ Fail |
| 5 | Config validation | ✅ Done | ✅ Pass |

## 🔍 Key Files to Review

1. **chat.py** - Core logic, fix session persistence
2. **nvim_api.py** - Improve diff application
3. **config/config.py** - Large spec in comments, implement gradually
4. **ui/qt_interface.py** - Experimental, document or remove

## 📈 Success Metrics

### Technical
- Test coverage: **Target >80%** (currently ~60%)
- Type coverage: **Target 100%**
- LOC: **Keep ~5000** (currently ~1000)

### Product
- Session length: **Target >15 min**
- Tools per session: **Target >5**
- Completion rate: **Target >70%**

### Community
- GitHub stars: **Target 1K**
- Contributors: **Target 10+**
- Plugins: **Target 20+**

## 🤔 Decision Points

### Immediate (Week 1)
**Q: Keep Qt UI code?**
- **A:** Yes, but mark as experimental in README

**Q: Integrate smolagents now?**
- **A:** No, defer until after roadmap completion

### Short Term (Month 1)
**Q: Which direction first?**
- **A:** Directions 1 + 4 (Agents + Sessions) in parallel

### Medium Term (Month 3)
**Q: RAG approach?**
- **A:** Start simple (file search), migrate to vector DB

## 💻 Example Usage

### Basic Chat
```bash
$ ecrivez repl
🖋 Ecrivez REPL – provider = echo, session = abc123 (Ctrl-D to quit)

you › Hello
llm › (echo) Hello

you › {"type": "tool", "tool": "shell", "cmd": "pwd"}
llm › /home/user/myproject
```

### With File Editing
```bash
$ ecrivez chat --file app.py
# Opens tmux with Neovim + REPL
# Chat in right pane, edit in left pane
```

### Apply Diff
```
you › /apply +def hello():
              +    print("world")
llm › (diff applied)
```

## 🔗 Related Projects

- **Aider** - Similar terminal-based approach
- **Cursor** - GUI IDE with LLM
- **Continue.dev** - VSCode extension
- **GitHub Copilot** - IDE integrations

## 📚 Resources

### Documentation
- [README.md](README.md) - Getting started
- [ROADMAP.md](ROADMAP.md) - Milestone tracking
- [OpenCode.md](OpenCode.md) - Build/test commands
- [EXPLORATION.md](EXPLORATION.md) - Full exploration (this doc)
- [NEXT_STEPS.md](NEXT_STEPS.md) - Actionable tasks
- [ARCHITECTURE.md](ARCHITECTURE.md) - Visual diagrams

### External Links
- [Smolagents Docs](https://github.com/huggingface/smolagents)
- [MCP Protocol](https://modelcontextprotocol.io)
- [Neovim RPC](https://neovim.io/doc/user/api.html)

## 🎓 Learning Path

### For New Contributors

**Week 1: Setup & Basics**
1. Clone repo and install dependencies
2. Read README, ROADMAP, OpenCode.md
3. Run tests, explore CLI commands
4. Fix a "good first issue"

**Week 2-3: Core Understanding**
1. Study chat.py provider system
2. Understand session persistence
3. Explore tool invocation
4. Write a new test

**Week 4+: Feature Development**
1. Pick a direction (Agents/RAG/UI)
2. Review detailed specs
3. Implement incrementally
4. Write tests first (TDD)

### For Users

**Day 1: Installation**
```bash
uv pip install ecrivez  # When available on PyPI
export OPENAI_API_KEY=sk-...
```

**Day 2: First Project**
```bash
ecrivez init --name my-first-project
cd my-first-project
ecrivez repl
```

**Week 1: Exploration**
- Try different tools
- Experiment with diffs
- Save and resume sessions

**Month 1: Mastery**
- Create custom workflows
- Integrate with your editor
- Contribute a plugin

## 🐛 Troubleshooting

### "OPENAI_API_KEY not set"
```bash
export OPENAI_API_KEY=sk-your-key-here
# Or add to .ecrivez/config.yaml
```

### "Neovim socket not found"
- Ensure Neovim is running with `--listen` flag
- Check socket path: `/tmp/nvim-ecrivez-{name}.sock`

### "Command failed: uv not found"
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### "Python version mismatch"
- Project requires Python 3.13+
- Use `pyenv` to install: `pyenv install 3.13`

## 🎯 Getting Started Checklist

- [ ] Read EXPLORATION.md for complete context
- [ ] Review NEXT_STEPS.md for actionable tasks
- [ ] Check ARCHITECTURE.md for visual understanding
- [ ] Run tests to verify setup
- [ ] Fix one of the critical bugs (#1-3)
- [ ] Write tests for your changes
- [ ] Submit PR with small, focused change

## 📞 Community

- **GitHub Issues** - Bug reports, feature requests
- **GitHub Discussions** - Q&A, ideas
- **Discord** - Real-time chat (coming soon)
- **Monthly Calls** - Community sync (planned)

---

**Version:** 0.1.0  
**Last Updated:** 2025-10-23  
**Maintainer:** matias-ceau  
**Status:** Active Development 🚧
