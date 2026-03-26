"""Tests for Word export."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ucgen.exporter_docx import export_docx
from ucgen.schema import (
    AlternativeCourse,
    EntitiesResult,
    Entity,
    EntityField,
    InfoRequirement,
    NFREntry,
    NormalCourseStep,
    SectionsResult,
    UseCaseDocument,
)


def test_export_docx_returns_valid_docx(tmp_path: Path, sample_intake) -> None:
    """export_docx writes a file that looks like a zip-based .docx."""
    sections = SectionsResult(
        preconditions=["Account exists"],
        minimal_guarantee="Logged with id.",
        success_guarantee="Confirmed.",
        normal_course=[
            NormalCourseStep(
                step=1,
                actor="User",
                action="Acts",
                system_response="Responds",
            )
        ],
        alternative_courses=[
            AlternativeCourse(ref="2a", condition="Timeout", response="Retry")
        ],
        postconditions=["Done"],
        information_requirements=[
            InfoRequirement(step=1, data_needed="id", format="UUID")
        ],
        nfr=[NFREntry(type="latency", requirement="Fast", threshold="p99 < 1s")],
        open_issues=["TBD?"],
    )
    entities = EntitiesResult(
        entities=[
            Entity(
                name="Order",
                fields=[EntityField(name="id", type="uuid", constraints=["PK"])],
                relationships=["Order has Items"],
            )
        ]
    )
    document = UseCaseDocument(
        metadata=sample_intake,
        sections=sections,
        entities=entities,
        raw_markdown="---\npriority: high\n---\n",
        generated_at=datetime.now(UTC),
        provider="mock",
        model="test-model",
        duration_ms=42,
    )
    out = tmp_path / "uc.docx"
    result = export_docx(document, out)
    assert result == out.resolve()
    assert out.is_file()
    data = out.read_bytes()
    assert data[:2] == b"PK"
