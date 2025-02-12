from datetime import datetime
from pathlib import Path
import toml
import importlib.resources
from pydantic import BaseModel, Field, 

from typing import List
from collections.abc import Callable
from uuid import uuid4

def generate_session_id() -> str:
    return uuid4().hex()


class Defaults(BaseModel, strict=True):
    chat_model: str = Field("gpt-4o", description="Default LLM model to use")
    embedding_model: str = Field("embedded", description="Default LLM model to use")
    editor: str = Field("nvim", description="Editor to use")
    agent: str = Field("example_agent.json", description="Agent file")
    tool_use: bool = Field(True, description="Use tool")
    session_id_generator: Callable = Field(generate_session_id, description="Session ID generator")
    autosave: bool = Field(True, description="Autosave")
    paths = DefaultPaths()
   