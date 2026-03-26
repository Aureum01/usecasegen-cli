"""Assemble final markdown from pipeline outputs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError

from ucgen import __version__
from ucgen.config import Config
from ucgen.errors import AssemblerError
from ucgen.schema import EntitiesResult, IntakeResult, SectionsResult

logger = logging.getLogger(__name__)


def _yaml_scalar(value: Any) -> str:
    """Render a scalar value for simple YAML frontmatter."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", "{", "}", "[", "]", ","]) or text.strip() != text:
        return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
    return text


def _build_frontmatter(
    *,
    intake: IntakeResult,
    sections: SectionsResult,
    config: Config,
    generated_at: datetime,
    duration_ms: int,
) -> str:
    """Build YAML frontmatter string for a generated document."""
    lines = [
        "---",
        f"uc_id: {_yaml_scalar(intake.uc_id)}",
        f"title: {_yaml_scalar(intake.title)}",
        f"actor: {_yaml_scalar(intake.actor)}",
        f"goal_level: {_yaml_scalar(intake.goal_level)}",
        f"domain: {_yaml_scalar(intake.domain)}",
        f"system_boundary: {_yaml_scalar(intake.system_boundary)}",
        f"trigger: {_yaml_scalar(intake.trigger)}",
        "priority: medium",
        "status: generated",
        f"generator: {_yaml_scalar(f'ucgen/{__version__}')}",
        f"provider: {_yaml_scalar(config.provider)}",
        f"model: {_yaml_scalar(config.model)}",
        f'generated_at: "{generated_at.isoformat()}"',
        f"duration_ms: {duration_ms}",
        "tags: []",
    ]

    stakeholders = [item.model_dump() for item in intake.stakeholders]
    if stakeholders:
        lines.append("stakeholders:")
        for item in stakeholders:
            lines.append(f"  - name: {_yaml_scalar(item.get('name'))}")
            lines.append(f"    interest: {_yaml_scalar(item.get('interest'))}")
    else:
        lines.append("stakeholders: []")

    nfr_rows = [item.model_dump() for item in sections.nfr] if sections.nfr else []
    if nfr_rows:
        lines.append("nfr:")
        for row in nfr_rows:
            lines.append(f"  - type: {_yaml_scalar(row.get('type'))}")
            lines.append(f"    requirement: {_yaml_scalar(row.get('requirement'))}")
            lines.append(f"    threshold: {_yaml_scalar(row.get('threshold'))}")
    else:
        lines.append("nfr: []")

    if intake.scale_hints is not None:
        lines.append("scale_hints:")
        hints = intake.scale_hints.model_dump()
        lines.append(f"  frequency: {_yaml_scalar(hints.get('frequency'))}")
        lines.append(f"  concurrent_users: {_yaml_scalar(hints.get('concurrent_users'))}")
        lines.append(f"  data_volume: {_yaml_scalar(hints.get('data_volume'))}")
    else:
        lines.append("scale_hints: null")

    lines.append("---")
    return "\n".join(lines)


def assemble(
    intake: IntakeResult,
    sections: SectionsResult,
    entities: EntitiesResult,
    config: Config,
    duration_ms: int = 0,
) -> str:
    """Render configured template and prepend frontmatter.

    Args:
        intake: Intake model output.
        sections: Sections model output.
        entities: Entities model output.
        config: Runtime config.

    Returns:
        Final markdown document.

    Raises:
        AssemblerError: If template loading or rendering fails.
    """
    template_ref = config.template
    template_path = Path(template_ref)
    if template_path.is_absolute():
        resolved_template = template_path
        template_dir = template_path.parent
        template_name = template_path.name
    else:
        template_dir = Path(__file__).resolve().parent / "templates"
        template_name = f"{template_ref}.md.j2"
        resolved_template = template_dir / template_name
    if not resolved_template.exists():
        raise AssemblerError(message="Template file not found.", template=template_name)

    generated_at = datetime.now(UTC)
    frontmatter = _build_frontmatter(
        intake=intake,
        sections=sections,
        config=config,
        generated_at=generated_at,
        duration_ms=duration_ms,
    )

    try:
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)
        template = env.get_template(template_name)
        body = template.render(
            intake=intake,
            sections=sections,
            entities=entities,
            config=config,
            generated_at=generated_at.isoformat(),
            generator_version=__version__,
        )
    except TemplateError as exc:
        logger.exception("Template rendering failed for %s", template_name)
        raise AssemblerError(message="Template render failed.", template=template_name) from exc
    return f"{frontmatter}\n\n{body.strip()}\n"
