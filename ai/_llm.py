"""Shared Anthropic client helpers for the ai/ generation calls.

Every generator degrades gracefully: if no credential is configured (or a call
fails), the caller falls back to deterministic local logic so the morning job
never crashes and tests run offline without network.
"""
from __future__ import annotations

import os

MODEL = "claude-opus-4-8"


def available() -> bool:
    """True if an Anthropic credential is present in the environment."""
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def client():
    import anthropic

    return anthropic.Anthropic()


def text_of(response) -> str:
    return next((b.text for b in response.content if b.type == "text"), "").strip()
