"""Markdown table normalization helper."""

from __future__ import annotations


def format_table(raw_table: str) -> str:
    """Normalize markdown table column widths.

    Args:
        raw_table: Raw markdown table text.

    Returns:
        A re-aligned markdown table string.
    """
    lines = [line.strip() for line in raw_table.strip().splitlines() if line.strip()]
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return raw_table
    column_count = max(len(row) for row in rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in rows]
    widths = [max(len(row[index]) for row in padded_rows) for index in range(column_count)]
    rendered = []
    for row_index, row in enumerate(padded_rows):
        rendered_cells = [row[i].ljust(widths[i]) for i in range(column_count)]
        rendered.append("| " + " | ".join(rendered_cells) + " |")
        if row_index == 0:
            separator_cells = ["-" * widths[i] for i in range(column_count)]
            rendered.append("| " + " | ".join(separator_cells) + " |")
    return "\n".join(rendered)
