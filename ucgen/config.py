"""Configuration loading and typed settings."""

from __future__ import annotations

import logging
import os
import sys
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


def safe_output_dir(raw: str | Path) -> Path:
    """Resolve ``output_dir``, reject obvious system paths, ensure directory exists."""
    resolved = Path(raw).expanduser().resolve()
    forbidden: list[Path] = []
    if sys.platform == "win32":
        win = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        forbidden.extend(
            [
                win,
                Path("C:/Program Files"),
                Path("C:/Program Files (x86)"),
            ]
        )
    else:
        forbidden.extend(
            [
                Path("/etc"),
                Path("/usr"),
                Path("/bin"),
                Path("/sbin"),
                Path("/sys"),
                Path("/dev"),
            ]
        )
    for root in forbidden:
        try:
            root_res = root.resolve()
        except OSError:
            root_res = root
        try:
            resolved.relative_to(root_res)
        except ValueError:
            continue
        raise ValueError(f"output_dir must not resolve under system path {root_res}: {resolved}")
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(
            f"Cannot create or write to output_dir. Check permissions on: {resolved}"
        ) from exc
    return resolved


def _flatten_ucgen_toml(data: dict) -> dict:
    """Merge [defaults], [providers], and [hooks] into flat keys for ``Config``."""
    if not data:
        return {}
    flat: dict = {}
    if "defaults" in data and isinstance(data["defaults"], dict):
        flat.update(data["defaults"])
    if "providers" in data and isinstance(data["providers"], dict):
        prov = data["providers"]
        if "ollama_base_url" in prov:
            flat["ollama_base_url"] = prov["ollama_base_url"]
        if "custom_base_url" in prov:
            flat["custom_base_url"] = prov["custom_base_url"] or None
        if "custom_prompts_dir" in prov:
            c = prov["custom_prompts_dir"]
            flat["custom_prompts_dir"] = Path(c) if c else None
    if "hooks" in data and isinstance(data["hooks"], dict):
        hooks = data["hooks"]
        if "on_generate" in hooks:
            flat["hooks_on_generate"] = hooks["on_generate"] or None
        if "on_batch_complete" in hooks:
            flat["hooks_on_batch_complete"] = hooks["on_batch_complete"] or None
    for key, val in data.items():
        if key in ("defaults", "providers", "hooks"):
            continue
        flat[key] = val
    return flat


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
    project_raw = _load_toml(root / ".ucgenrc.toml")
    home_raw = _load_toml(Path.home() / ".ucgenrc.toml")
    merged = {**_flatten_ucgen_toml(home_raw), **_flatten_ucgen_toml(project_raw)}
    if "output_dir" in merged:
        merged["output_dir"] = safe_output_dir(merged["output_dir"])
    else:
        merged["output_dir"] = safe_output_dir("./use-cases")
    config = Config(**merged)
    logger.debug("Loaded config provider=%s model=%s", config.provider, config.model)
    return config
