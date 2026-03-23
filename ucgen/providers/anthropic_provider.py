"""Anthropic provider implementation."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Iterable

from anthropic import Anthropic
from anthropic.types import MessageParam

from ucgen.providers.base import BaseProvider, GenerationResult


def _sync_anthropic_messages_create(
    client: Anthropic,
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    system: str,
    messages: Iterable[MessageParam],
):
    """Run synchronous Anthropic messages.create (for asyncio.to_thread)."""
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages,
    )


def _message_content_text(message: object) -> str:
    """Extract concatenated text from Anthropic message content blocks."""
    blocks = getattr(message, "content", None) or []
    parts: list[str] = []
    for block in blocks:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


class AnthropicProvider(BaseProvider):
    """Provider backed by Anthropic SDK."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None) -> None:
        """Initialize Anthropic provider."""
        self.model = model
        self._api_key = api_key
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=key) if key else None

    @property
    def name(self) -> str:
        """Return provider name."""
        return "anthropic"

    def is_available(self) -> bool:
        """Check whether Anthropic credentials exist."""
        return bool(self._api_key or os.getenv("ANTHROPIC_API_KEY"))

    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate output via Anthropic messages API."""
        if not self.client:
            raise ValueError("Anthropic API key is required.")
        started = time.perf_counter()
        message = await asyncio.to_thread(
            _sync_anthropic_messages_create,
            self.client,
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        content = _message_content_text(message)
        usage = getattr(message, "usage", None)
        tokens_used = None
        if usage is not None:
            tokens_used = getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)
        return GenerationResult(
            content=content,
            model=self.model,
            provider=self.name,
            tokens_used=tokens_used,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
