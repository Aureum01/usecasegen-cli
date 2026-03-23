"""Project file loading and multi-use-case runs."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from ucgen.config import Config
from ucgen.generator import generate
from ucgen.providers.base import BaseProvider
from ucgen.schema import ProjectDefinition, UseCaseDocument


def load_project(path: Path = Path("ucgen.yaml")) -> ProjectDefinition:
    """Load and validate a ucgen project file.

    Args:
        path: Project file path.

    Returns:
        Validated project definition.

    Raises:
        ImportError: If PyYAML is unavailable.
        FileNotFoundError: If file does not exist.
        ValidationError: If schema validation fails.
    """
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("Project files require PyYAML. Run: pip install ucgen[project]") from exc
    if not path.exists():
        raise FileNotFoundError(f"No ucgen.yaml found at: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        return ProjectDefinition.model_validate(data)
    except ValidationError:
        raise


async def run_project(
    project: ProjectDefinition,
    config: Config,
    provider: BaseProvider,
    filter_id: str | None = None,
    filter_tag: str | None = None,
) -> list[UseCaseDocument]:
    """Generate all matching pending use cases from a project.

    Args:
        project: Project definition.
        config: Runtime config.
        provider: Model provider.
        filter_id: Optional case ID filter.
        filter_tag: Optional tag filter.

    Returns:
        Generated documents list.
    """
    results: list[UseCaseDocument] = []
    for use_case in project.use_cases:
        if use_case.status != "pending":
            continue
        if filter_id and use_case.id != filter_id:
            continue
        if filter_tag and filter_tag not in use_case.tags:
            continue
        document = await generate(use_case.goal, config, provider)
        results.append(document)
    return results


def get_project_status(project: ProjectDefinition, output_dir: Path) -> list[dict]:
    """Return status rows for project use cases.

    Args:
        project: Project definition.
        output_dir: Output directory to inspect.

    Returns:
        List of status dictionaries.
    """
    status_rows: list[dict] = []
    for use_case in project.use_cases:
        prefix = f"{use_case.id}-"
        matches = list(output_dir.glob(f"{prefix}*.md"))
        file_path = matches[0] if matches else None
        status_rows.append(
            {
                "id": use_case.id,
                "title": use_case.title,
                "status": "generated" if file_path else use_case.status,
                "generated_at": None,
                "file_path": str(file_path) if file_path else None,
            }
        )
    return status_rows
