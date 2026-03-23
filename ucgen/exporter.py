"""Export UseCaseDocument into alternate formats."""

from __future__ import annotations

import json

from ucgen.schema import UseCaseDocument


def to_json(doc: UseCaseDocument) -> str:
    """Export a document as JSON.

    Args:
        doc: Document to export.

    Returns:
        JSON string.
    """
    return json.dumps(doc.model_dump(mode="json"), ensure_ascii=True, indent=2)


def to_yaml(doc: UseCaseDocument) -> str:
    """Export a document as YAML.

    Args:
        doc: Document to export.

    Returns:
        YAML string.

    Raises:
        ImportError: If PyYAML is not installed.
    """
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("YAML export requires PyYAML. Run: pip install ucgen[project]") from exc
    return yaml.safe_dump(doc.model_dump(mode="json"), sort_keys=False)
