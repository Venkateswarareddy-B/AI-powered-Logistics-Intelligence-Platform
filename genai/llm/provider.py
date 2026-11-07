"""LLM provider abstraction.

This module abstracts the LLM behind a single interface so the provider
can be changed later without touching business logic. Currently uses Groq
with a Llama model. OpenAI is intentionally NOT used.

Usage:
    from genai.llm.provider import get_llm
    llm = get_llm()
    if llm:
        response = llm.chat("Why is SHP-2026-000001 delayed?")
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import get_settings

settings = get_settings()
log = logging.getLogger("genai.llm.provider")


class LLMNotConfiguredError(Exception):
    """Raised when the LLM provider is not configured (no API key)."""


class GroqProvider:
    """Groq + Llama provider. Swappable via this abstraction."""

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float):
        from groq import Groq
        self._client = Groq(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = model
        self._timeout = timeout

    def chat(
        self,
        message: str,
        system_prompt: str | None = None,
        context: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Send a chat completion request and return the text response.

        Args:
            message: The user's question.
            system_prompt: System instructions for the assistant.
            context: Additional context (e.g. live DB data, RAG policy text).
            temperature: Sampling temperature (lower = more deterministic).
            max_tokens: Maximum response length.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context:
            messages.append({"role": "system",
                             "content": f"Context data:\n{context}"})
        messages.append({"role": "user", "content": message})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def is_available(self) -> bool:
        """Check if the provider can make requests."""
        try:
            self._client.models.list()
            return True
        except Exception:
            return False


_provider: GroqProvider | None = None


def get_llm() -> GroqProvider | None:
    """Get the configured LLM provider instance.

    Returns None if Groq is not configured (no API key or GROQ_ENABLED=False).
    Never raises — callers should check for None and return a config message.
    """
    global _provider
    if _provider is not None:
        return _provider

    if not settings.GROQ_ENABLED or not settings.GROQ_API_KEY:
        return None

    try:
        _provider = GroqProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            base_url=settings.GROQ_BASE_URL,
            timeout=settings.GROQ_REQUEST_TIMEOUT_SECONDS,
        )
        log.info("Groq LLM provider initialized: model=%s", settings.GROQ_MODEL)
        return _provider
    except Exception as exc:
        log.error("failed to initialize Groq provider: %s", exc)
        return None


def reset_provider() -> None:
    """Reset the cached provider (used after config changes)."""
    global _provider
    _provider = None
