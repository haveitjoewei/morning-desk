"""Shared Anthropic client helpers for the ai/ generation calls.

Every generator degrades gracefully: if no credential is configured (or a call
fails), the caller falls back to deterministic local logic so the morning job
never crashes and tests run offline without network.
"""
from __future__ import annotations

import os

MODEL = os.environ.get("MD_CLAUDE_MODEL", "claude-opus-4-8")


def available() -> bool:
    """True if an Anthropic credential is present in the environment."""
    if os.environ.get("MD_OFFLINE") == "1":
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def client():
    import anthropic

    return anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        auth_token=os.environ.get("ANTHROPIC_AUTH_TOKEN"),
        timeout=12.0,
        max_retries=1,
    )


def text_of(response) -> str:
    return next((b.text for b in response.content if b.type == "text"), "").strip()
