"""Ollama provider implementation."""

from __future__ import annotations

import logging
import re
import socket
import time

from ucgen.providers.base import BaseProvider, GenerationResult

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile("`" + "think" + ".*?" + "`" + "think" + "`", re.DOTALL)


class OllamaProvider(BaseProvider):
    """Provider for local Ollama REST API."""

    def __init__(self, model: str = "mistral", base_url: str = "http://localhost:11434") -> None:
        """Initialize Ollama provider."""
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        """Return provider name."""
        return "ollama"

    def is_available(self) -> bool:
        """Check whether Ollama is reachable."""
        try:
            host = self.base_url.replace("http://", "").replace("https://", "").split(":")[0]
            port = int(self.base_url.rsplit(":", maxsplit=1)[1])
            with socket.create_connection((host, port), timeout=2):
                return True
        except Exception:
            return False

    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate model output from Ollama chat endpoint."""
        import httpx

        started = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "think": False,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        content = data["message"]["content"]
        # Strip </think> blocks emitted by reasoning models (qwen3, deepseek-r1)
        content = _THINK_BLOCK_RE.sub("", content).strip()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.debug("Ollama response received in %d ms", elapsed_ms)
        return GenerationResult(
            content=content,
            model=self.model,
            provider=self.name,
            tokens_used=data.get("eval_count"),
            duration_ms=elapsed_ms,
        )
