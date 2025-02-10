import click

from .config import Config
from .editor import start_editor
from .project import init_project, modify_config

CFG = Config()


def ecrivez():
    """Ecrivez CLI tool for managing coding sessions with LLMs"""
    pass


@click.command()
@click.option("--model", default="gpt-4o", help="Default LLM model to use")
@click.option("--name", default="", help="Filename and project name")
def init(model: str, name: str) -> None:
    """Initialize a new Ecrivez project"""
    init_project(model=model, name=name)
    click.echo(f"Initialized {name} project")


@click.command()
@click.option("--model", help="LLM model to use")
@click.option("--editor", help="Editor to use")
def config(model: str, editor: str) -> None:
    """Modify Ecrivez configuration"""
    modify_config(model=model, editor=editor)
    click.echo("Updated configuration")


@click.command()
@click.option("--file", default=None, help="Filename to open")
def chat(file: str | None) -> None:
    """Start a chat session with file editing capabilities"""
    start_editor(file)
