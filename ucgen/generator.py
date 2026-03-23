"""Generation pipeline orchestration."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from ucgen.assembler import assemble
from ucgen.config import Config
from ucgen.errors import (
    GenerationError,
    IntakeParseError,
    ProviderUnavailableError,
    SectionsParseError,
)
from ucgen.providers.base import BaseProvider
from ucgen.schema import EntitiesResult, IntakeResult, SectionsResult, UseCaseDocument
from ucgen.utils.id_counter import next_id
from ucgen.utils.json_extract import extract_json
from ucgen.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


def _save_debug(output_dir: Path, filename: str, raw_output: str) -> None:
    """Persist raw stage output for debugging parse failures."""
    debug_dir = output_dir / ".ucgen_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / filename).write_text(raw_output, encoding="utf-8")


async def _call_with_retry(
    provider: BaseProvider,
    system: str,
    user: str,
    stage_name: str,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> str:
    """Call provider with one retry on failure."""
    try:
        result = await provider.generate(
            system=system, user=user, temperature=temperature, max_tokens=max_tokens
        )
        return result.content
    except Exception as exc:
        logger.warning("First call failed for stage=%s, retrying: %s", stage_name, exc)
        try:
            result = await provider.generate(
                system=system,
                user=user,
                temperature=0.1,
                max_tokens=max_tokens,
            )
            return result.content
        except Exception as retry_exc:
            logger.exception("Stage failed after retry: %s", stage_name)
            raise GenerationError(
                message=f"Stage failed after retry: {stage_name}",
                stage=stage_name,
            ) from retry_exc


async def _run_intake(
    idea: str,
    uc_id: str,
    config: Config,
    provider: BaseProvider,
) -> IntakeResult:
    system = load_prompt("system_base", config.custom_prompts_dir)
    user = load_prompt("stage1_intake", config.custom_prompts_dir).replace("{idea}", idea)
    raw = await _call_with_retry(
        provider, system, user, "intake", config.temperature, config.max_tokens
    )
    try:
        payload = extract_json(raw)
        payload["uc_id"] = uc_id
        payload["raw_input"] = idea
        return IntakeResult(**payload)
    except Exception as exc:
        _save_debug(config.output_dir, f"{uc_id}-intake.txt", raw)
        raise IntakeParseError(
            message="Failed to parse intake stage output.", stage="intake", raw_output=raw
        ) from exc


async def _run_sections(
    intake: IntakeResult,
    config: Config,
    provider: BaseProvider,
) -> SectionsResult:
    system = load_prompt("system_base", config.custom_prompts_dir)
    user = load_prompt("stage2_sections", config.custom_prompts_dir).replace(
        "{intake_json}",
        json.dumps(intake.model_dump(), ensure_ascii=True),
    )
    raw = await _call_with_retry(
        provider, system, user, "sections", config.temperature, config.max_tokens
    )
    try:
        payload = extract_json(raw)
        return SectionsResult(**payload)
    except Exception as exc:
        _save_debug(config.output_dir, f"{intake.uc_id}-sections.txt", raw)
        raise SectionsParseError(
            message="Failed to parse sections stage output.", stage="sections", raw_output=raw
        ) from exc


async def _run_entities(
    intake: IntakeResult,
    sections: SectionsResult,
    config: Config,
    provider: BaseProvider,
) -> EntitiesResult:
    system = load_prompt("system_base", config.custom_prompts_dir)
    summary = {
        "normal_course": [item.model_dump() for item in sections.normal_course],
        "information_requirements": [
            item.model_dump() for item in sections.information_requirements
        ],
    }
    user = load_prompt("stage3_entities", config.custom_prompts_dir)
    user = user.replace("{intake_json}", json.dumps(intake.model_dump(), ensure_ascii=True))
    user = user.replace("{sections_summary}", json.dumps(summary, ensure_ascii=True))
    raw = await _call_with_retry(
        provider, system, user, "entities", config.temperature, config.max_tokens
    )
    try:
        return EntitiesResult(**extract_json(raw))
    except Exception as exc:
        logger.warning(
            "Entities stage failed, using fallback entities from intake.related_entities"
        )
        fallback_entities = [
            {"name": name.title().replace(" ", ""), "fields": [], "relationships": []}
            for name in intake.related_entities
        ]
        _save_debug(config.output_dir, f"{intake.uc_id}-entities.txt", raw)
        if not fallback_entities:
            fallback_entities = [
                {"name": "Entity", "fields": [], "relationships": []},
            ]
        logger.warning(
            "Using fallback entities count=%d due to parse error: %s",
            len(fallback_entities),
            exc,
        )
        return EntitiesResult.model_validate({"entities": fallback_entities})


async def generate(idea: str, config: Config, provider: BaseProvider) -> UseCaseDocument:
    """Run full sequential generation pipeline.

    Args:
        idea: Natural language input.
        config: Loaded config.
        provider: Availability-checked provider.

    Returns:
        Fully assembled use-case document.

    Raises:
        ProviderUnavailableError: If provider is not available.
        GenerationError: If a non-fallback stage fails.
    """
    if not provider.is_available():
        hint = "Check provider credentials and connectivity."
        if provider.name == "ollama":
            hint = "Is Ollama running? Try: ollama serve"
        raise ProviderUnavailableError(
            message="Provider unavailable.", provider=provider.name, hint=hint
        )
    started = time.perf_counter()
    uc_id = next_id(config.output_dir, prefix=config.id_prefix)
    intake = await _run_intake(idea, uc_id, config, provider)
    sections = await _run_sections(intake, config, provider)
    entities = await _run_entities(intake, sections, config, provider)
    raw_markdown = assemble(intake, sections, entities, config)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return UseCaseDocument(
        metadata=intake,
        sections=sections,
        entities=entities,
        raw_markdown=raw_markdown,
        generated_at=datetime.now(UTC),
        provider=provider.name,
        model=config.model,
        duration_ms=elapsed_ms,
    )
