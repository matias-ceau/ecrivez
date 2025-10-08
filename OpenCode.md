# OpenCode Configuration for Ecrivez

## Build/Test/Lint Commands
- **Install dependencies**: `uv sync`
- **Run application**: `uv run ecrivez --help`
- **Type checking**: `uv run mypy src/`
- **Linting**: `uv run ruff check src/`
- **Format code**: `uv run ruff format src/`
- **Run single test**: No test framework configured yet

## Code Style Guidelines
- **Python version**: >=3.13 (modern Python features encouraged)
- **Type hints**: Use modern union syntax (`str | None` not `Optional[str]`)
- **Imports**: Standard library first, third-party, then local imports with blank lines between groups
- **Models**: Use Pydantic with `strict=True` for data validation
- **CLI**: Use Click for command-line interfaces
- **Configuration**: YAML for project config, TOML for package config
- **Paths**: Use `pathlib.Path` instead of string paths
- **Error handling**: Use Click exceptions for CLI errors, standard Python exceptions elsewhere
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Documentation**: Docstrings for public functions, inline comments sparingly
- **Dependencies**: Check existing imports before adding new libraries