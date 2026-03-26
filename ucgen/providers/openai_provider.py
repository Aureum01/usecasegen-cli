"""OpenAI-compatible provider implementation."""

from __future__ import annotations

import os
import time

from ucgen.providers.base import BaseProvider, GenerationResult


class OpenAICompatibleProvider(BaseProvider):
    """Provider for OpenAI-compatible chat completion APIs."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        provider_name: str = "openai",
    ) -> None:
        """Initialize OpenAI-compatible provider."""
        from openai import AsyncOpenAI

        self.model = model
        self._provider_name = provider_name
        self.base_url = base_url
        env_keys = ["OPENAI_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY"]
        resolved_key = api_key
        if resolved_key is None:
            for key_name in env_keys:
                key = os.getenv(key_name)
                if key:
                    resolved_key = key
                    break
        self._api_key = resolved_key
        self._client = (
            AsyncOpenAI(api_key=resolved_key, base_url=base_url) if resolved_key else None
        )

    @property
    def name(self) -> str:
        """Return provider name."""
        return self._provider_name

    def is_available(self) -> bool:
        """Check whether API key is set."""
        return bool(self._api_key)

    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate output using chat completions."""
        if not self._client:
            raise ValueError("API key is required.")
        started = time.perf_counter()
        response = await self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        tokens = getattr(usage, "total_tokens", None) if usage else None
        return GenerationResult(
            content=content,
            model=self.model,
            provider=self.name,
            tokens_used=tokens,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
