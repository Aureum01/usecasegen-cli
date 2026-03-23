"""Project-level orchestration — reads ucgen.yaml and runs multi-use-case generation."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from rich.progress import MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ucgen.config import Config
from ucgen.exporter import to_json
from ucgen.generator import generate
from ucgen.providers.base import BaseProvider
from ucgen.schema import IntakeResult, ProjectDefinition, UseCaseDocument

logger = logging.getLogger(__name__)


def load_project(path: Path = Path("ucgen.yaml")) -> ProjectDefinition:
    """Load and validate ucgen.yaml.

    Args:
        path: Project file path.

    Returns:
        Validated project definition.

    Raises:
        ImportError: If PyYAML not installed.
        FileNotFoundError: If file does not exist.
        ValidationError: If schema validation fails.
    """
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("ucgen[project] required — run: pip install ucgen[project]") from exc
    if not path.exists():
        raise FileNotFoundError(f"No ucgen.yaml found at: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ProjectDefinition.model_validate(data)


def merge_project_config(base: Config, project: ProjectDefinition) -> Config:
    """Merge project defaults into base Config.

    Args:
        base: Base config loaded from TOML.
        project: Project definition from ucgen.yaml.

    Returns:
        New config with project defaults applied.
    """
    merged = base.model_dump()
    defaults = project.defaults.model_dump()
    merged.update(defaults)
    return Config(**merged)


def run_hook(command: str, substitutions: dict) -> None:
    """Run a lifecycle hook shell command.

    Args:
        command: Shell command with {key} placeholders.
        substitutions: Dict of placeholder values.
    """
    try:
        resolved = command.format(**substitutions)
    except Exception:
        logger.warning("Hook format failed command=%s substitutions=%s", command, substitutions)
        return
    logger.debug("Running hook command=%s", resolved)
    completed = subprocess.run(resolved, shell=True, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        logger.warning("Hook failed command=%s code=%d", resolved, completed.returncode)


def _slug_from_goal(goal: str) -> str:
    words = [word.lower() for word in goal.split() if word.isalnum()][:5]
    return "-".join(words)[:40] or "use-case"


def _project_dir_name(name: str) -> str:
    """Return filesystem-safe directory name from project title."""
    lowered = name.strip().lower().replace(" ", "-")
    cleaned = re.sub(r"[^a-z0-9-]", "", lowered)
    compact = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return compact or "project"


def _replace_frontmatter_uc_id(markdown: str, uc_id: str) -> str:
    if not markdown.startswith("---"):
        return markdown
    parts = markdown.split("---", maxsplit=2)
    if len(parts) < 3:
        return markdown
    frontmatter = parts[1].strip()
    body = parts[2].lstrip("\r\n")
    if frontmatter.startswith("{") and frontmatter.endswith("}"):
        try:
            payload = json.loads(frontmatter)
        except json.JSONDecodeError:
            return markdown
        if isinstance(payload, dict):
            payload["uc_id"] = uc_id
            payload_text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
            return f"---\n{payload_text}\n---\n\n{body}"
    updated_lines = []
    replaced = False
    for line in frontmatter.splitlines():
        if line.startswith("uc_id:"):
            updated_lines.append(f"uc_id: {uc_id}")
            replaced = True
        else:
            updated_lines.append(line)
    if not replaced:
        updated_lines.insert(0, f"uc_id: {uc_id}")
    updated_frontmatter = "\n".join(updated_lines)
    return f"---\n{updated_frontmatter}\n---\n\n{body}"


def _parse_frontmatter(content: str) -> dict[str, object]:
    """Parse markdown frontmatter as JSON or YAML."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", maxsplit=2)
    if len(parts) < 3:
        return {}
    frontmatter = parts[1].strip()
    if frontmatter.startswith("{") and frontmatter.endswith("}"):
        try:
            parsed = json.loads(frontmatter)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    try:
        import yaml
    except ImportError:
        metadata: dict[str, object] = {}
        for line in frontmatter.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", maxsplit=1)
            metadata[key.strip()] = value.strip().strip('"')
        return metadata
    parsed_yaml = yaml.safe_load(frontmatter)
    return parsed_yaml if isinstance(parsed_yaml, dict) else {}


def _document_with_project_id(document: UseCaseDocument, uc_id: str) -> UseCaseDocument:
    metadata = IntakeResult(**{**document.metadata.model_dump(), "uc_id": uc_id})
    raw_markdown = _replace_frontmatter_uc_id(document.raw_markdown, uc_id)
    return UseCaseDocument(
        metadata=metadata,
        sections=document.sections,
        entities=document.entities,
        raw_markdown=raw_markdown,
        generated_at=document.generated_at,
        provider=document.provider,
        model=document.model,
        duration_ms=document.duration_ms,
    )


async def run_project(
    project: ProjectDefinition,
    config: Config,
    provider: BaseProvider,
    filter_id: str | None = None,
    filter_tag: str | None = None,
    filter_status: str = "pending",
) -> list[UseCaseDocument]:
    """Generate use cases from a project definition.

    Args:
        project: Project definition.
        config: Merged runtime config.
        provider: Model provider.
        filter_id: Optional case ID filter.
        filter_tag: Optional tag filter.
        filter_status: Generate only use cases with this status.

    Returns:
        Generated documents list.
    """
    selected_use_cases = []
    for use_case in project.use_cases:
        if filter_status and use_case.status != filter_status:
            continue
        if filter_id and use_case.id != filter_id:
            continue
        if filter_tag and filter_tag not in use_case.tags:
            continue
        selected_use_cases.append(use_case)

    results: list[UseCaseDocument] = []
    project_output_dir = config.output_dir / _project_dir_name(project.project.name)
    project_output_dir.mkdir(parents=True, exist_ok=True)
    with Progress(
        SpinnerColumn(spinner_name="dots", style="green"),
        TextColumn("{task.description}"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task(
            "Generating 0 of 0",
            total=len(selected_use_cases),
        )
        for index, use_case in enumerate(selected_use_cases, start=1):
            progress.update(
                task,
                description=(
                    f"Generating {index} of {len(selected_use_cases)}: "
                    f"{use_case.id} {use_case.title}"
                ),
            )
            try:
                idea = f"{use_case.goal}. Actor: {use_case.actor}. Title: {use_case.title}."
                document = await generate(idea, config, provider)
                document = _document_with_project_id(document, use_case.id)
                slug = _slug_from_goal(use_case.goal)
                output_path = project_output_dir / f"{use_case.id}-{slug}.md"
                output_path.write_text(document.raw_markdown, encoding="utf-8")
                json_path = project_output_dir / f"{use_case.id}-{slug}.json"
                json_path.write_text(to_json(document), encoding="utf-8")
                if project.hooks and project.hooks.on_generate:
                    run_hook(
                        project.hooks.on_generate,
                        {"uc_id": use_case.id, "file": str(output_path)},
                    )
                results.append(document)
            except Exception as exc:
                logger.exception("Project use case failed id=%s error=%s", use_case.id, exc)
            finally:
                progress.advance(task)
    if project.hooks and project.hooks.on_batch_complete:
        run_hook(
            project.hooks.on_batch_complete,
            {
                "count": str(len(results)),
                "project": project.project.name,
            },
        )
    return results


def get_project_status(project: ProjectDefinition, output_dir: Path) -> list[dict]:
    """Check generation status of all use cases in project.

    Args:
        project: Project definition.
        output_dir: Output directory to inspect for markdown outputs.

    Returns:
        List of status dictionaries.
    """
    by_uc_id: dict[str, dict] = {}
    project_output_dir = output_dir / _project_dir_name(project.project.name)
    if not project_output_dir.exists():
        project_output_dir = output_dir / project.project.name
    for file_path in project_output_dir.glob("*.md"):
        content = file_path.read_text(encoding="utf-8")
        metadata = _parse_frontmatter(content)
        if not metadata:
            continue
        uc_id = metadata.get("uc_id")
        if isinstance(uc_id, str):
            by_uc_id[uc_id] = {
                "status": metadata.get("status", "generated"),
                "generated_at": metadata.get("generated_at"),
                "file": file_path,
                "model": metadata.get("model"),
                "title": metadata.get("title"),
            }

    status_rows: list[dict[str, object]] = []
    for use_case in project.use_cases:
        discovered = by_uc_id.get(use_case.id)
        status_rows.append(
            {
                "id": use_case.id,
                "title": str(discovered["title"]) if discovered else use_case.title,
                "actor": use_case.actor,
                "priority": use_case.priority,
                "tags": use_case.tags,
                "status": str(discovered["status"]) if discovered else use_case.status,
                "generated_at": str(discovered["generated_at"]) if discovered else None,
                "file": discovered["file"] if discovered else None,
                "model": str(discovered["model"]) if discovered else None,
            }
        )
    return status_rows
