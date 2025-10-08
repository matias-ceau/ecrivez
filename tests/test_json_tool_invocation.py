import json
import pytest

from ecrivez.chat import _process_input, EchoProvider


def test_json_tool_shell_invocation(tmp_path, monkeypatch):
    # Prepare config and history
    cfg = {}
    provider = EchoProvider()
    history = []

    user_input = json.dumps({"type": "tool", "tool": "shell", "cmd": "echo hello_json"})
    reply = _process_input(user_input, cfg, provider, history)
    assert reply.strip() == "hello_json"
    # History should record the user and assistant messages
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_json_tool_unknown_tool(tmp_path):
    cfg = {}
    provider = EchoProvider()
    history = []

    user_input = json.dumps({"type": "tool", "tool": "foo", "cmd": ""})
    reply = _process_input(user_input, cfg, provider, history)
    assert reply == "Unknown tool: foo"


def test_json_tool_invalid_json(tmp_path):
    cfg = {}
    provider = EchoProvider()
    history = []

    user_input = "{not a valid json"
    reply = _process_input(user_input, cfg, provider, history)
    assert reply == "Invalid JSON tool invocation"


def test_json_plain_chat():
    # Non-JSON fallback uses chat provider
    # Non-JSON fallback uses chat provider
    cfg = {}
    provider = EchoProvider()
    history = []

    user_input = "Hello world"
    reply = _process_input(user_input, cfg, provider, history)
    assert reply.startswith("(echo)")
