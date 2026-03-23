"""Use case markdown validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ValidationResult:
    """Validation result for a markdown use case file."""

    file: Path
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _extract_frontmatter(content: str) -> str | None:
    if not content.startswith("---\n"):
        return None
    parts = content.split("\n---\n", maxsplit=1)
    if len(parts) < 2:
        return None
    return parts[0].replace("---\n", "", 1).strip()


def validate_file(path: Path) -> ValidationResult:
    """Validate structure of a markdown use case file.

    Args:
        path: File path to validate.

    Returns:
        ValidationResult with checks and errors.
    """
    checks: dict[str, bool] = {}
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    frontmatter = _extract_frontmatter(text)
    checks["frontmatter_present"] = frontmatter is not None
    if frontmatter is None:
        errors.append("YAML frontmatter missing.")
    checks["has_preconditions"] = "## Preconditions" in text
    checks["has_normal_course"] = "## Normal Course" in text
    checks["has_alternative_courses"] = "## Alternative Courses" in text
    checks["has_postconditions_or_success"] = ("## Postconditions" in text) or (
        "## Success Guarantee" in text
    )
    checks["has_entities"] = "## Implied Entities" in text
    for name, passed in checks.items():
        if not passed:
            errors.append(f"Missing required section: {name}")
    return ValidationResult(file=path, passed=not errors, checks=checks, errors=errors)
