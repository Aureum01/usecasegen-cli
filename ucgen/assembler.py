"""Assemble final markdown from pipeline outputs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateError

from ucgen import __version__
from ucgen.config import Config
from ucgen.errors import AssemblerError
from ucgen.schema import EntitiesResult, IntakeResult, SectionsResult

logger = logging.getLogger(__name__)


def _to_frontmatter(data: dict) -> str:
    """Serialize frontmatter deterministically."""
    return json.dumps(data, ensure_ascii=True, separators=(",", ":"))


def assemble(
    intake: IntakeResult,
    sections: SectionsResult,
    entities: EntitiesResult,
    config: Config,
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

    frontmatter = {
        "uc_id": intake.uc_id,
        "title": intake.title,
        "actor": intake.actor,
        "goal_level": intake.goal_level,
        "domain": intake.domain,
        "system_boundary": intake.system_boundary,
        "trigger": intake.trigger,
        "priority": "medium",
        "status": "generated",
        "generator": f"ucgen/{__version__}",
        "provider": config.provider,
        "model": config.model,
        "generated_at": datetime.now(UTC).isoformat(),
        "duration_ms": 0,
        "tags": [],
        "stakeholders": [item.model_dump() for item in intake.stakeholders],
        "nfr": [item.model_dump() for item in sections.nfr] if sections.nfr else [],
        "scale_hints": intake.scale_hints.model_dump() if intake.scale_hints else None,
    }

    try:
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)
        template = env.get_template(template_name)
        body = template.render(
            intake=intake,
            sections=sections,
            entities=entities,
            config=config,
            generated_at=frontmatter["generated_at"],
            generator_version=__version__,
        )
    except TemplateError as exc:
        logger.exception("Template rendering failed for %s", template_name)
        raise AssemblerError(message="Template render failed.", template=template_name) from exc
    return f"---\n{_to_frontmatter(frontmatter)}\n---\n\n{body.strip()}\n"
