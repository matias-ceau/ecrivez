# Ecrivez

Ecrivez is a terminal-based autonomous coding assistant built by OpenAI. It orchestrates tests, implementations, and tooling interactions to evolve features incrementally.

## Roadmap

The detailed upcoming milestones and acceptance criteria can be found in [ROADMAP.md](ROADMAP.md).

---

For full documentation and getting started instructions, see:
- [OpenCode.md](OpenCode.md)
- [ecrivez.qmd](ecrivez.qmd)
  
## Usage

The `ecrivez` CLI provides several commands to manage your coding sessions:

  - Initialize a new project:
    ```bash
    ecrivez init --model gpt-4o --name myproject
    ```

  - Modify project configuration:
    ```bash
    ecrivez config --model gpt-3.5-turbo --editor vim
    ```

  - Start a coding session/editor integration:
    ```bash
    ecrivez chat --file myproject.py
    ```

  - Open an interactive chat REPL:
    ```bash
    ecrivez repl
    ```

Use `--help` with any command to see available options. For example:
```bash
ecrivez init --help
```
