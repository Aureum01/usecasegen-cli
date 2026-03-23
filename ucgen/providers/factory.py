"""Provider factory."""

from __future__ import annotations

from ucgen.config import Config
from ucgen.providers.anthropic_provider import AnthropicProvider
from ucgen.providers.base import BaseProvider
from ucgen.providers.ollama import OllamaProvider
from ucgen.providers.openai_provider import OpenAICompatibleProvider


class ProviderFactory:
    """Factory to instantiate providers from config."""

    @staticmethod
    def create(config: Config) -> BaseProvider:
        """Create a provider instance from configuration.

        Args:
            config: Loaded configuration.

        Returns:
            Provider instance.

        Raises:
            ValueError: If provider is not recognized.
        """
        if config.provider == "ollama":
            return OllamaProvider(model=config.model, base_url=config.ollama_base_url)
        if config.provider == "anthropic":
            return AnthropicProvider(model=config.model)
        if config.provider == "openai":
            return OpenAICompatibleProvider(model=config.model, provider_name="openai")
        if config.provider == "groq":
            return OpenAICompatibleProvider(
                model=config.model,
                base_url="https://api.groq.com/openai/v1",
                provider_name="groq",
            )
        if config.provider == "custom":
            return OpenAICompatibleProvider(
                model=config.model,
                base_url=config.custom_base_url,
                provider_name="custom",
            )
        raise ValueError(f"Unknown provider: {config.provider}")
