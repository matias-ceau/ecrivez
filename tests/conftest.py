import pytest


@pytest.fixture(autouse=True)
def no_online_drafting_from_the_real_environment(monkeypatch):
    monkeypatch.delenv("ECRIVEZ_DRAFT_MODEL", raising=False)
