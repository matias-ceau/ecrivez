import importlib
import sys
from types import ModuleType

import pytest

from ecrivez.chat import _choose_provider, BaseProvider


class DummyOpenAI(ModuleType):
    """Minimal stub to satisfy ecrivez.chat.OpenAIProvider."""

    def __init__(self):
        super().__init__("openai")
        self.api_key: str | None = None

        class _Chat:  # noqa: D401 – inner stub
            class _Completions:  # noqa: D401 – inner stub
                @staticmethod
                def create(**kwargs):  # noqa: D401 – minimal signature
                    class _Choices:  # noqa: D401 – inner stub
                        class _Msg:  # noqa: D401 – inner stub
                            content = "assistant reply"

                        message = _Msg()

                    return type("_Resp", (), {"choices": [_Choices()]})()

            completions = _Completions()

        self.chat = _Chat()


@pytest.fixture(autouse=True)
def cleanup_openai():
    original = sys.modules.pop("openai", None)
    yield
    if original is not None:
        sys.modules["openai"] = original


def test_choose_openai_with_key(monkeypatch):
    sys.modules["openai"] = DummyOpenAI()
    monkeypatch.setenv("OPENAI_API_KEY", "testkey")

    cfg = {"model": "gpt-4o", "provider": "openai"}
    provider = _choose_provider(cfg)
    assert isinstance(provider, BaseProvider)
    assert provider.name.startswith("openai:")


def test_choose_echo_when_no_pkg():
    cfg = {"model": "gpt-4o", "provider": "echo"}
    provider = _choose_provider(cfg)
    assert provider.name == "echo"