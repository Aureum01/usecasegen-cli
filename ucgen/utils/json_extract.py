"""JSON extraction helpers for noisy model outputs."""

from __future__ import annotations

import json
import re

from ucgen.errors import JSONExtractError


def extract_json(raw: str) -> dict:
    """Extract the outermost JSON object from model output text.

    Args:
        raw: Raw text returned by a provider.

    Returns:
        Parsed JSON dictionary.

    Raises:
        JSONExtractError: If no valid JSON object is found.
    """
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise JSONExtractError(
            message="No JSON object found in model output.", raw_preview=raw[:500]
        )
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JSONExtractError(
            message="Model output contained invalid JSON.",
            raw_preview=raw[:500],
        ) from exc
