"""Generation pipeline orchestration."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ucgen.assembler import assemble
from ucgen.config import Config
from ucgen.errors import (
    GenerationError,
    IntakeParseError,
    ProviderUnavailableError,
    SectionsParseError,
    UCGenError,
)
from ucgen.providers.base import BaseProvider
from ucgen.schema import (
    DiscoveryResult,
    EntitiesResult,
    IntakeResult,
    SectionsResult,
    UseCaseDocument,
)
from ucgen.utils.id_counter import next_id
from ucgen.utils.json_extract import extract_json
from ucgen.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

_DURATION_LINE_RE = re.compile(r"^duration_ms:\s*\d+\s*$", flags=re.MULTILINE)


def _save_debug(output_dir: Path, filename: str, raw_output: str) -> None:
    """Persist raw stage output for debugging parse failures."""
    debug_dir = output_dir / ".ucgen_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / filename).write_text(raw_output, encoding="utf-8")


def _should_write_debug(debug: bool) -> bool:
    """Return True when debug output should be persisted."""
    if debug:
        return True
    return os.getenv("UCGEN_DEBUG") == "1"


async def _call_with_retry(
    provider: BaseProvider,
    system: str,
    user: str,
    stage_name: str,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    on_retry: Callable[[], None] | None = None,
) -> str:
    """Call provider with one retry on failure."""
    try:
        result = await provider.generate(
            system=system, user=user, temperature=temperature, max_tokens=max_tokens
        )
        return result.content
    except Exception as exc:
        logger.warning("First call failed for stage=%s, retrying: %s", stage_name, exc)
        if on_retry is not None:
            on_retry()
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
    debug: bool = False,
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
        if _should_write_debug(debug):
            _save_debug(config.output_dir, f"{uc_id}-stage1-raw.json", raw)
        raise IntakeParseError(
            message="Failed to parse intake stage output.", stage="intake", raw_output=raw
        ) from exc


async def _run_discovery(
    idea: str,
    config: Config,
    provider: BaseProvider,
) -> DiscoveryResult:
    """
    Stage 0 — AI-driven use case discovery.

    This runs before the existing 4-stage pipeline and proposes a set of use
    cases for the given idea. It retries once with lower temperature if parsing
    fails or the model response is not valid for ``DiscoveryResult``.
    """
    system = load_prompt("system_base", config.custom_prompts_dir)
    prompt_template = load_prompt("stage0_discover", config.custom_prompts_dir)
    user = prompt_template.replace("{idea}", idea)
    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            result = await provider.generate(
                system=system,
                user=user,
                temperature=config.temperature if attempt == 1 else 0.1,
                max_tokens=min(config.max_tokens, 2000),
            )
            payload = extract_json(result.content)
            return DiscoveryResult.model_validate(payload)
        except Exception as exc:
            last_error = exc
            logger.warning("Discovery parse failed attempt=%d: %s", attempt, exc)
            continue
    raise UCGenError(
        message=(
            "Stage 0 discovery failed after 2 attempts. "
            "Try rephrasing your idea or use a different provider."
        )
    ) from last_error


async def _run_sections(
    intake: IntakeResult,
    config: Config,
    provider: BaseProvider,
    debug: bool = False,
    on_provider_retry: Callable[[str, int], None] | None = None,
) -> SectionsResult:
    system = load_prompt("system_base", config.custom_prompts_dir)
    intake_json = json.dumps(intake.model_dump(), ensure_ascii=True)
    user = load_prompt("stage2_sections", config.custom_prompts_dir)
    # Support both whole-object and dotted intake placeholders.
    user = user.replace("{intake_json}", intake_json)
    user = user.replace("{intake_json.domain}", str(intake.domain))
    user = user.replace("{intake_json.actor}", str(intake.actor))
    user = user.replace("{intake_json.goal}", str(intake.goal))

    def _sections_retry_notice() -> None:
        if on_provider_retry is not None:
            on_provider_retry("sections", 2)

    raw = await _call_with_retry(
        provider,
        system,
        user,
        "sections",
        config.temperature,
        config.max_tokens,
        on_retry=_sections_retry_notice if on_provider_retry else None,
    )
    try:
        payload = extract_json(raw)
        return SectionsResult(**payload)
    except Exception as exc:
        if _should_write_debug(debug):
            _save_debug(config.output_dir, f"{intake.uc_id}-stage2-raw.json", raw)
        raise SectionsParseError(
            message="Failed to parse sections stage output.", stage="sections", raw_output=raw
        ) from exc


async def _run_entities(
    intake: IntakeResult,
    sections: SectionsResult,
    config: Config,
    provider: BaseProvider,
    debug: bool = False,
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
        if _should_write_debug(debug):
            _save_debug(config.output_dir, f"{intake.uc_id}-stage3-raw.json", raw)
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


async def generate(
    idea: str,
    config: Config,
    provider: BaseProvider,
    on_stage_complete: Callable[[int, float], None] | None = None,
    on_provider_retry: Callable[[str, int], None] | None = None,
    debug: bool = False,
) -> UseCaseDocument:
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
    stage_t0 = time.perf_counter()
    intake = await _run_intake(idea, uc_id, config, provider, debug=debug)
    if on_stage_complete is not None:
        on_stage_complete(1, time.perf_counter() - stage_t0)
    stage_t0 = time.perf_counter()
    sections = await _run_sections(
        intake,
        config,
        provider,
        debug=debug,
        on_provider_retry=on_provider_retry,
    )
    if on_stage_complete is not None:
        on_stage_complete(2, time.perf_counter() - stage_t0)
    stage_t0 = time.perf_counter()
    entities = await _run_entities(intake, sections, config, provider, debug=debug)
    if on_stage_complete is not None:
        on_stage_complete(3, time.perf_counter() - stage_t0)
    stage_t0 = time.perf_counter()
    raw_markdown = assemble(intake, sections, entities, config, duration_ms=0)
    if on_stage_complete is not None:
        on_stage_complete(4, time.perf_counter() - stage_t0)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    raw_markdown = _DURATION_LINE_RE.sub(
        f"duration_ms: {elapsed_ms}",
        raw_markdown,
        count=1,
    )
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
