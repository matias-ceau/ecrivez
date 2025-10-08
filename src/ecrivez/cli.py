import click
from .editor import start_editor
from .project import init_project, modify_config

@click.group()
def ecrivez():
    """Ecrivez CLI tool for managing coding sessions with LLMs"""
    pass


@click.command()
@click.option("--model", default="gpt-4o", help="Default LLM model to use")
@click.option("--name", default="", help="Filename and project name")
def init(model, name):
    """Initialize a new Ecrivez project"""
    init_project(model, name)
    click.echo(f"Initialized {name} project")


@click.command()
@click.option("--model", help="LLM model to use")
@click.option("--editor", help="Editor to use")
def config(model: str | None, editor: str | None):
    """Modify Ecrivez configuration"""
    modify_config(model, editor)
    click.echo("Updated configuration")


@click.command()
@click.option("--file", default=None, help="Filename to open")
def chat(file: str | None):
    """Start a chat session with file editing capabilities"""
    start_editor(file)


@click.command()
def repl():
    """Start an interactive chat REPL (runs outside tmux as well)."""
    from .chat import start_repl

    start_repl()


# ---------------------------------------------------------------------------
# Wire sub-commands into the group
# ---------------------------------------------------------------------------


ecrivez.add_command(init)
ecrivez.add_command(config)
ecrivez.add_command(chat)
ecrivez.add_command(repl)
