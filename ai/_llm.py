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


def client(timeout=None):
    import anthropic

    # Default stays tight so the morning job fails fast to its fallback; interactive
    # tools (vision ingest, corrections) pass a longer timeout for slower calls.
    if timeout is None:
        timeout = float(os.environ.get("MD_LLM_TIMEOUT", "12"))
    return anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        auth_token=os.environ.get("ANTHROPIC_AUTH_TOKEN"),
        timeout=timeout,
        # No retry: on a serverless request a retry just doubles the wait toward the
        # function limit; failing fast to the deterministic fallback is better.
        max_retries=int(os.environ.get("MD_LLM_RETRIES", "0")),
    )


def text_of(response) -> str:
    return next((b.text for b in response.content if b.type == "text"), "").strip()
