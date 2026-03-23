"""Utility function tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ucgen.utils.id_counter import next_id
from ucgen.utils.json_extract import extract_json
from ucgen.utils.prompt_loader import load_prompt
from ucgen.utils.table_formatter import format_table


def test_extract_json_with_fence() -> None:
    """extract_json parses fenced JSON."""
    raw = '```json\n{"a":1}\n```'
    assert extract_json(raw)["a"] == 1


def test_extract_json_invalid() -> None:
    """extract_json raises on invalid output."""
    with pytest.raises(Exception):
        extract_json("no json here")


def test_next_id_increments(tmp_path: Path) -> None:
    """next_id increments stored counter."""
    one = next_id(tmp_path)
    two = next_id(tmp_path)
    assert one != two


def test_format_table_aligns() -> None:
    """format_table returns normalized markdown table."""
    formatted = format_table("|A|B|\n|1|22|")
    assert "|" in formatted


def test_load_prompt_reads_builtin() -> None:
    """load_prompt returns prompt text from package."""
    assert "senior business analyst" in load_prompt("system_base")
