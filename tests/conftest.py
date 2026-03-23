"""Pytest fixtures for ucgen tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ucgen.config import Config
from ucgen.providers.base import BaseProvider, GenerationResult
from ucgen.schema import (
    EntitiesResult,
    Entity,
    IntakeResult,
    SectionsResult,
    StakeholderEntry,
)


@pytest.fixture()
def temp_config(tmp_path: Path) -> Config:
    """Return a test config with temporary output directory."""
    return Config(output_dir=tmp_path / "out")


class MockProvider(BaseProvider):
    """Mock provider used by generator tests."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls: list[dict[str, float]] = []

    @property
    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return True

    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> GenerationResult:
        self.calls.append({"temperature": temperature, "max_tokens": float(max_tokens)})
        if not self._responses:
            raise RuntimeError("No mock responses configured")
        response = self._responses.pop(0)
        if response == "__RAISE__":
            raise RuntimeError("forced provider failure")
        return GenerationResult(
            content=response,
            model="mock",
            provider="mock",
            tokens_used=100,
            duration_ms=50,
        )


@pytest.fixture()
def sample_intake() -> IntakeResult:
    """Return sample intake result fixture."""
    return IntakeResult(
        uc_id="UC-2026-0001",
        title="Patient Books Appointment",
        goal_level="user_goal",
        actor="Patient",
        supporting_actors=["SchedulingService"],
        stakeholders=[StakeholderEntry(name="Clinic", interest="Fill available slots predictably")],
        domain="Health",
        system_boundary="Scheduling Service",
        trigger="Patient requests appointment",
        goal="Patient books a confirmed appointment",
        related_entities=["Patient", "Appointment", "Provider"],
        raw_input="Patient books an appointment.",
    )


@pytest.fixture()
def sample_sections() -> SectionsResult:
    """Return sample sections result fixture."""
    return SectionsResult(
        preconditions=["Patient account exists", "Provider schedule exists", "Clinic is open"],
        minimal_guarantee="Attempt is logged with timestamp and patient ID.",
        success_guarantee="Patient and clinic both have the same confirmed slot.",
        postconditions=["Appointment exists with confirmed status"],
    )


@pytest.fixture()
def sample_entities() -> EntitiesResult:
    """Return sample entities result fixture."""
    return EntitiesResult(entities=[Entity(name="Appointment"), Entity(name="Patient")])


@pytest.fixture()
def mock_provider_factory():
    """Return a factory that creates MockProvider instances."""

    def _factory(responses: list[str]) -> MockProvider:
        return MockProvider(responses=responses.copy())

    return _factory
