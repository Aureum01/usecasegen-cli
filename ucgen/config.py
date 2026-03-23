"""Configuration loading and typed settings."""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path

from pydantic import ConfigDict

from ucgen.errors import ConfigError
from ucgen.schema import FrozenModel

logger = logging.getLogger(__name__)

_EXAMPLE_CONFIG = """# ucgen configuration example
# Copy this file to .ucgenrc.toml and customize values.

[defaults]
provider = "ollama"
model = "mistral"
output_dir = "./use-cases"
template = "default"
id_prefix = "UC"
temperature = 0.3
max_tokens = 4000

[providers]
ollama_base_url = "http://localhost:11434"
custom_base_url = ""
custom_prompts_dir = ""

[hooks]
on_generate = ""
on_batch_complete = ""
"""


class Config(FrozenModel):
    """Runtime configuration for ucgen."""

    model_config = ConfigDict(frozen=True)
    provider: str = "ollama"
    model: str = "mistral"
    output_dir: Path = Path("./use-cases")
    template: str = "default"
    id_prefix: str = "UC"
    ollama_base_url: str = "http://localhost:11434"
    custom_base_url: str | None = None
    custom_prompts_dir: Path | None = None
    temperature: float = 0.3
    max_tokens: int = 4000
    hooks_on_generate: str | None = None
    hooks_on_batch_complete: str | None = None


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except OSError as exc:
        logger.exception("Failed reading config file: %s", path)
        raise ConfigError(message="Unable to read config file.", path=str(path)) from exc
    except tomllib.TOMLDecodeError as exc:
        logger.exception("Invalid TOML in config: %s", path)
        raise ConfigError(message="Invalid TOML in config file.", path=str(path)) from exc


def load(project_dir: Path | None = None) -> Config:
    """Load config from project then home file, then defaults.

    Args:
        project_dir: Optional project directory.

    Returns:
        Merged runtime config.
    """
    root = project_dir or Path.cwd()
    project_config = _load_toml(root / ".ucgenrc.toml")
    home_config = _load_toml(Path.home() / ".ucgenrc.toml")
    merged: dict = {}
    merged.update(home_config)
    merged.update(project_config)
    config = Config(**merged)
    logger.debug("Loaded config provider=%s model=%s", config.provider, config.model)
    return config
