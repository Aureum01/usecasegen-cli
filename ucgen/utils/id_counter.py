"""Counter-based use case ID generation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def next_id(output_dir: Path, prefix: str = "UC") -> str:
    """Read and increment the use-case counter in output directory.

    Args:
        output_dir: Directory where `.ucgen_counter` is stored.
        prefix: ID prefix string.

    Returns:
        Next use-case identifier in `{prefix}-{YYYY}-{NNNN}` format.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    counter_file = output_dir / ".ucgen_counter"
    current = 0
    if counter_file.exists():
        value = counter_file.read_text(encoding="utf-8").strip()
        if value.isdigit():
            current = int(value)
    next_value = current + 1
    counter_file.write_text(str(next_value), encoding="utf-8")
    year = datetime.now(UTC).year
    return f"{prefix}-{year}-{next_value:04d}"
