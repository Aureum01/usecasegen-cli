"""Provider interfaces and shared response model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationResult:
    """Generated model text and metadata."""

    content: str
    model: str
    provider: str
    tokens_used: int | None
    duration_ms: int


class BaseProvider(ABC):
    """Abstract model provider interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name."""

    @abstractmethod
    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        """Generate content from system and user prompts."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether provider is configured and reachable."""
