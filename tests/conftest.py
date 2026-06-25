"""Make the suite hermetic by default.

Several tests build the full briefing, which would otherwise reach the live
weather, calendar, Gmail, and Claude backends — slow and flaky. Default every
test to offline mode with no Claude credential. Tests that exercise the online
code paths opt back in explicitly (they patch MD_OFFLINE and mock the network).
"""
import pytest


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch):
    monkeypatch.setenv("MD_OFFLINE", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
