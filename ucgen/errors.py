"""Custom exceptions for ucgen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class UCGenError(Exception):
    """Base exception for all ucgen errors."""

    message: str
    context: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


@dataclass
class ProviderUnavailableError(UCGenError):
    """Raised when a configured provider is not available."""

    provider: str = ""
    hint: str = ""


@dataclass
class GenerationError(UCGenError):
    """Raised when a pipeline generation stage fails."""

    stage: str = ""
    raw_output: str | None = None


class IntakeParseError(GenerationError):
    """Raised when stage 1 intake parsing fails."""


class SectionsParseError(GenerationError):
    """Raised when stage 2 sections parsing fails."""


class EntitiesParseError(GenerationError):
    """Raised when stage 3 entities parsing fails."""


@dataclass
class AssemblerError(UCGenError):
    """Raised when template rendering fails."""

    template: str = ""


@dataclass
class ConfigError(UCGenError):
    """Raised when configuration parsing or loading fails."""

    path: str = ""


@dataclass
class JSONExtractError(UCGenError):
    """Raised when JSON cannot be extracted from LLM output."""

    raw_preview: str = ""


@dataclass
class ProjectFileError(UCGenError):
    """Raised when ucgen project file loading fails."""

    path: str = ""
