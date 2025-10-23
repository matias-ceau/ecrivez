# Ecrivez

Ecrivez is a terminal-based autonomous coding assistant that integrates LLMs with development workflows. It orchestrates tests, implementations, and tooling interactions to evolve features incrementally.

## 📚 Documentation

### Quick Start
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - At-a-glance guide, commands, troubleshooting
- **[OpenCode.md](OpenCode.md)** - Build/test/lint commands

### Project Planning
- **[PROJECT_EXPLORATION_SUMMARY.md](PROJECT_EXPLORATION_SUMMARY.md)** - Executive summary of exploration
- **[ROADMAP.md](ROADMAP.md)** - Milestone tracking and acceptance criteria

### Deep Dive
- **[EXPLORATION.md](EXPLORATION.md)** - Complete analysis with 5 strategic directions
- **[NEXT_STEPS.md](NEXT_STEPS.md)** - Actionable tasks with code examples
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Visual diagrams and architecture

### Other
- [ecrivez.qmd](ecrivez.qmd) - Quarto notebook documentation

---

## Current Status

**Version:** 0.1.0 (Early Development)  
**LOC:** ~1000  
**Test Coverage:** ~60% (target: >80%)  
**Python:** 3.13+

✅ **Implemented:** CLI, REPL, OpenAI provider, tool invocation, config validation  
⚠️ **Partial:** Session persistence, diff application  
🚧 **Planned:** Agent framework, RAG, workflow automation
  
## Quick Start

```bash
# Initialize a project
ecrivez init --model gpt-4o --name myproject

# Set API key
export OPENAI_API_KEY=sk-your-key

# Start interactive REPL
cd myproject
ecrivez repl

# Start editor mode (tmux + Neovim)
ecrivez chat --file myproject.py
```

See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for detailed usage and examples.

## Key Features

- 🤖 **LLM Integration** - OpenAI API with fallback echo provider
- 🛠️ **Tool System** - JSON-based tool invocation (shell, custom tools)
- 📝 **Editor Integration** - Neovim socket communication via tmux
- ⚙️ **Configuration** - Pydantic validation with XDG directory support
- 💾 **Session Persistence** - Save and resume conversations
- 🔧 **Extensible** - Provider abstraction for multiple LLM backends

## Strategic Directions

Ecrivez is exploring 5 directions for future development:

1. **🤖 Agentic Workflow Engine** - Autonomous task execution with multi-step reasoning
2. **📚 RAG-Enhanced Assistant** - Vector DB and semantic code search
3. **🖥️ Multi-Modal UI** - Rich Qt interface with integrated tools
4. **💾 Session Management** - Complete persistence, replay, and analytics
5. **🔌 MCP Integration** - Model Context Protocol for standardized tools

See [EXPLORATION.md](EXPLORATION.md) for detailed analysis and implementation plans.

## Contributing

Ecrivez is in early development and welcomes contributions!

**Getting Started:**
1. Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for project overview
2. Check [NEXT_STEPS.md](NEXT_STEPS.md) for immediate tasks
3. Review [ARCHITECTURE.md](ARCHITECTURE.md) for visual understanding
4. Look for issues labeled "good first issue"

**Critical bugs** needing immediate attention:
- Session history loading not implemented
- Diff application needs improvement
- See [NEXT_STEPS.md](NEXT_STEPS.md) for details

## Project Structure

```
ecrivez/
├── src/ecrivez/         # Source code
│   ├── cli.py           # CLI commands
│   ├── chat.py          # REPL and providers
│   ├── editor.py        # Editor integration
│   ├── config/          # Configuration system
│   └── ui/              # Experimental Qt UI
├── tests/               # Test suite
└── docs/                # Documentation
```
