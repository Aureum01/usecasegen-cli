"""Generator pipeline tests based on critical scenarios."""

from __future__ import annotations

import json

import pytest

from ucgen.errors import IntakeParseError
from ucgen.generator import generate


def _intake_payload() -> str:
    return json.dumps(
        {
            "title": "Test Use Case",
            "goal_level": "user_goal",
            "actor": "User",
            "supporting_actors": [],
            "stakeholders": [],
            "domain": "General",
            "system_boundary": None,
            "trigger": "Trigger",
            "goal": "Goal",
            "related_entities": ["Order"],
            "scale_hints": None,
        }
    )


def _sections_payload() -> str:
    return json.dumps(
        {
            "preconditions": ["Ready"],
            "minimal_guarantee": "Logged",
            "success_guarantee": "Done",
            "normal_course": [
                {"step": 1, "actor": "User", "action": "Do", "system_response": "Ok"},
            ],
            "alternative_courses": [
                {"ref": "1a", "condition": "Fail", "response": "Abort"},
            ],
            "postconditions": ["Saved"],
            "information_requirements": [
                {"step": 1, "data_needed": "id", "source": "db", "format": "UUID"},
            ],
            "nfr": None,
            "state_machine": None,
            "open_issues": None,
        }
    )


def _entities_payload() -> str:
    return json.dumps({"entities": [{"name": "Order", "fields": [], "relationships": []}]})


@pytest.mark.asyncio
async def test_generate_returns_document(temp_config, mock_provider_factory) -> None:
    """Generate returns UseCaseDocument with markdown."""
    provider = mock_provider_factory(
        [
            _intake_payload(),
            _sections_payload(),
            _entities_payload(),
        ]
    )
    doc = await generate("Build booking", temp_config, provider)
    assert doc.metadata.uc_id.startswith("UC-")
    assert doc.raw_markdown.startswith("---")


@pytest.mark.asyncio
async def test_generate_retries_with_lower_temperature(temp_config, mock_provider_factory) -> None:
    """Generator retries once with temperature 0.1 after a provider failure."""
    provider = mock_provider_factory(
        [
            "__RAISE__",
            _intake_payload(),
            _sections_payload(),
            _entities_payload(),
        ]
    )
    await generate("Build booking", temp_config, provider)
    assert provider.calls[0]["temperature"] == 0.3
    assert provider.calls[1]["temperature"] == 0.1


@pytest.mark.asyncio
async def test_generate_uses_entity_fallback(temp_config, mock_provider_factory) -> None:
    """Generator uses fallback entities when stage 3 parse fails."""
    provider = mock_provider_factory(
        [
            _intake_payload(),
            _sections_payload(),
            "not-json",
        ]
    )
    doc = await generate("Build booking", temp_config, provider)
    assert doc.entities.entities[0].name == "Order"


@pytest.mark.asyncio
async def test_generate_raises_for_intake_parse_failure(temp_config, mock_provider_factory) -> None:
    """Generator raises intake parse error after retry succeeds with invalid JSON."""
    provider = mock_provider_factory(["not-json"])
    with pytest.raises(IntakeParseError):
        await generate("Build booking", temp_config, provider)


@pytest.mark.asyncio
async def test_generate_never_writes_partial_document(temp_config, mock_provider_factory) -> None:
    """Generator never writes markdown files on pipeline failure."""
    provider = mock_provider_factory(["not-json"])
    with pytest.raises(IntakeParseError):
        await generate("Build booking", temp_config, provider)
    assert not list(temp_config.output_dir.glob("*.md"))
