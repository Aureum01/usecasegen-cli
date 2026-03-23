"""Pydantic models for ucgen data contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FrozenModel(BaseModel):
    """Base frozen Pydantic model."""

    model_config = ConfigDict(frozen=True)


class StakeholderEntry(FrozenModel):
    """A stakeholder and their interest in this use case outcome."""

    name: str
    interest: str


class ScaleHints(FrozenModel):
    """Frequency and scale signals that inform architecture selection."""

    frequency: str | None = None
    concurrent_users: str | None = None
    data_volume: str | None = None


class IntakeResult(FrozenModel):
    """Structured metadata extracted from raw user input in stage 1."""

    uc_id: str
    title: str
    goal_level: str = "user_goal"
    actor: str
    supporting_actors: list[str] = Field(default_factory=list)
    stakeholders: list[StakeholderEntry] = Field(default_factory=list)
    domain: str
    system_boundary: str | None = None
    trigger: str
    goal: str
    related_entities: list[str] = Field(default_factory=list)
    scale_hints: ScaleHints | None = None
    raw_input: str


class NormalCourseStep(FrozenModel):
    """A single step in the use case normal course."""

    step: int
    actor: str
    action: str
    system_response: str


class AlternativeCourse(FrozenModel):
    """An alternative path branching from a normal course step."""

    ref: str
    condition: str
    response: str


class InfoRequirement(FrozenModel):
    """Data element required at a specific step."""

    step: int
    data_needed: str
    source: str
    format: str


class NFREntry(FrozenModel):
    """A non-functional requirement for this use case."""

    type: str
    requirement: str
    threshold: str | None = None


class StateMachineState(FrozenModel):
    """A lifecycle state and valid transitions."""

    state: str
    transitions: list[str] = Field(default_factory=list)


class SectionsResult(FrozenModel):
    """Use case body sections generated in pipeline stage 2."""

    preconditions: list[str] = Field(default_factory=list)
    minimal_guarantee: str
    success_guarantee: str
    normal_course: list[NormalCourseStep] = Field(default_factory=list)
    alternative_courses: list[AlternativeCourse] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    information_requirements: list[InfoRequirement] = Field(default_factory=list)
    nfr: list[NFREntry] | None = None
    state_machine: list[StateMachineState] | None = None
    open_issues: list[str] | None = None

    @field_validator("minimal_guarantee", "success_guarantee", mode="before")
    @classmethod
    def coerce_guarantee_to_str(cls, v: object) -> str:
        if isinstance(v, list):
            return " ".join(str(i) for i in v)
        if isinstance(v, dict):
            return ". ".join(f"{k}: {val}" for k, val in v.items())
        return str(v)

    @field_validator("normal_course", mode="before")
    @classmethod
    def coerce_normal_course(cls, v: object) -> list:
        if isinstance(v, list) and v and isinstance(v[0], str):
            return [
                {"step": i + 1, "actor": "System", "action": step, "system_response": ""}
                for i, step in enumerate(v)
            ]
        return v

    @field_validator("nfr", mode="before")
    @classmethod
    def coerce_nfr(cls, v: object) -> list | None:
        if isinstance(v, list) and v and isinstance(v[0], str):
            return [
                {"type": item, "requirement": item, "threshold": None}
                for item in v
            ]
        return v

    @field_validator("postconditions", mode="before")
    @classmethod
    def coerce_postconditions(cls, v: object) -> list:
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("information_requirements", mode="before")
    @classmethod
    def coerce_information_requirements(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v
        coerced = []
        for item in v:
            if isinstance(item, dict):
                # Already correct shape
                if "step" in item or "data_needed" in item:
                    coerced.append(item)
                # Mistral returns {name, source} — remap it
                elif "name" in item or "source" in item:
                    coerced.append(
                        {
                            "step": item.get("name") or item.get("source") or "",
                            "data_needed": item.get("name", ""),
                            "format": item.get("source") or None,
                        }
                    )
            elif isinstance(item, str):
                coerced.append(
                    {
                        "step": item,
                        "data_needed": item,
                        "format": None,
                    }
                )
        return coerced


class EntityField(FrozenModel):
    """A field within an extracted entity model."""

    name: str
    type: str
    constraints: list[str] = Field(default_factory=list)


class Entity(FrozenModel):
    """An extracted domain entity."""

    name: str
    fields: list[EntityField] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


class EntitiesResult(FrozenModel):
    """Entity extraction output from stage 3."""

    entities: list[Entity] = Field(default_factory=list)


class UseCaseDocument(FrozenModel):
    """Complete output of generation pipeline."""

    metadata: IntakeResult
    sections: SectionsResult
    entities: EntitiesResult
    raw_markdown: str
    generated_at: datetime
    provider: str
    model: str
    duration_ms: int


class ActorDefinition(FrozenModel):
    """Actor definition from project file."""

    name: str
    description: str
    type: str = "human"


class UseCaseDefinition(FrozenModel):
    """Use case definition from project file."""

    id: str
    title: str
    actor: str
    goal: str
    priority: str = "medium"
    tags: list[str] = Field(default_factory=list)
    status: str = "pending"


class ProjectDefaults(FrozenModel):
    """Default generation settings for project runs."""

    provider: str = "ollama"
    model: str = "mistral"
    template: str = "default"
    output_dir: Path = Path("./use-cases")


class HooksConfig(FrozenModel):
    """Lifecycle hooks for project runs."""

    on_generate: str | None = None
    on_batch_complete: str | None = None


class ProjectMetadata(FrozenModel):
    """Top-level project metadata in ucgen.yaml."""

    name: str
    domain: str | None = None
    stack: str | None = None
    version: str | None = None


class ProjectDefinition(FrozenModel):
    """Project definition loaded from ucgen.yaml."""

    project: ProjectMetadata
    defaults: ProjectDefaults = ProjectDefaults()
    actors: list[ActorDefinition] = Field(default_factory=list)
    use_cases: list[UseCaseDefinition] = Field(default_factory=list)
    knowledge: dict | None = None
    hooks: HooksConfig | None = None
