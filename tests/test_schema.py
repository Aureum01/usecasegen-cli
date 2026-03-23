"""Schema model tests."""

from __future__ import annotations

from datetime import UTC, datetime

from ucgen.schema import (
    EntitiesResult,
    Entity,
    IntakeResult,
    SectionsResult,
    UseCaseDocument,
)


def test_intake_result_minimal_valid() -> None:
    """IntakeResult accepts required fields."""
    model = IntakeResult(
        uc_id="UC-2026-0001",
        title="Patient Books Appointment",
        actor="Patient",
        domain="Health",
        trigger="Patient requests slot",
        goal="Book appointment",
        raw_input="book appointment",
    )
    assert model.uc_id == "UC-2026-0001"


def test_use_case_document_creation() -> None:
    """UseCaseDocument validates nested models."""
    metadata = IntakeResult(
        uc_id="UC-2026-0001",
        title="Sample",
        actor="User",
        domain="General",
        trigger="start",
        goal="finish",
        raw_input="sample",
    )
    sections = SectionsResult(minimal_guarantee="Logged", success_guarantee="Saved")
    entities = EntitiesResult(entities=[Entity(name="Order")])
    document = UseCaseDocument(
        metadata=metadata,
        sections=sections,
        entities=entities,
        raw_markdown="# Sample",
        generated_at=datetime.now(UTC),
        provider="ollama",
        model="mistral",
        duration_ms=100,
    )
    assert document.provider == "ollama"
