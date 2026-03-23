"""Assembler tests."""

from __future__ import annotations

from ucgen.assembler import assemble
from ucgen.config import Config
from ucgen.schema import EntitiesResult, Entity, IntakeResult, SectionsResult


def test_assemble_renders_markdown() -> None:
    """assemble renders template and frontmatter."""
    intake = IntakeResult(
        uc_id="UC-2026-0001",
        title="Sample",
        actor="User",
        domain="General",
        trigger="Start",
        goal="Finish",
        raw_input="sample input",
    )
    sections = SectionsResult(
        preconditions=["Ready"],
        minimal_guarantee="Logged",
        success_guarantee="Done",
    )
    entities = EntitiesResult(entities=[Entity(name="Order")])
    content = assemble(intake, sections, entities, Config())
    assert content.startswith("---")
    assert "# Sample" in content
