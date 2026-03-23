"""Prompt loading and in-process caching."""

from __future__ import annotations

from pathlib import Path

_cache: dict[str, str] = {}


def load_prompt(name: str, custom_dir: Path | None = None) -> str:
    """Load a prompt markdown file by prompt name.

    Args:
        name: Prompt file stem name, without `.md`.
        custom_dir: Optional custom prompt directory.

    Returns:
        Prompt file contents.

    Raises:
        FileNotFoundError: If prompt does not exist.
    """
    cache_key = f"{custom_dir}:{name}"
    if cache_key in _cache:
        return _cache[cache_key]
    prompt_path: Path
    if custom_dir is not None:
        prompt_path = custom_dir / f"{name}.md"
        if prompt_path.exists():
            text = prompt_path.read_text(encoding="utf-8")
            _cache[cache_key] = text
            return text
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / f"{name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {name}")
    text = prompt_path.read_text(encoding="utf-8")
    _cache[cache_key] = text
    return text
