"""Typer CLI entrypoint for ucgen."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from ucgen import __version__
from ucgen.config import Config, load
from ucgen.exporter import to_json, to_yaml
from ucgen.generator import generate as run_generate
from ucgen.project_runner import get_project_status, load_project
from ucgen.providers import ProviderFactory
from ucgen.validator import validate_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()
app = typer.Typer(
    name="ucgen",
    help="Generate structured use case documents from natural language.",
    no_args_is_help=True,
)


def _slug_from_text(actor: str, goal: str) -> str:
    combined = goal.lower()
    actor_lower = actor.lower()
    if combined.startswith(actor_lower):
        combined = combined[len(actor_lower) :].strip()
    words = [word for word in combined.split() if word.isalnum()][:5]
    return "-".join(words)[:40]


def _write_output(content: str, output_path: Path, append: bool = False) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if append and output_path.exists():
        output_path.write_text(
            output_path.read_text(encoding="utf-8") + "\n---\n\n" + content, encoding="utf-8"
        )
    else:
        output_path.write_text(content, encoding="utf-8")


def _write_document(content: str, output_path: Path, append_path: Path | None = None) -> Path:
    """Write a generated document to disk and return destination path."""
    destination = append_path or output_path
    _write_output(content, destination, append=append_path is not None)
    return destination


def _run_hook(command: str, context: dict[str, str]) -> None:
    """Run a configured shell hook command with context substitutions."""
    resolved = command.format(**context)
    completed = subprocess.run(resolved, shell=True, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        logger.warning("Hook failed command=%s code=%d", resolved, completed.returncode)


def _build_progress(include_mofn: bool = False) -> Progress:
    """Build a Windows-safe progress renderer."""
    if sys.platform == "win32":
        return Progress(
            TextColumn("[green]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        )
    if include_mofn:
        return Progress(
            SpinnerColumn(spinner_name="dots", style="green"),
            TextColumn("{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        )
    return Progress(
        SpinnerColumn(spinner_name="dots", style="green"),
        TextColumn("{task.description}"),
        BarColumn(bar_width=30),
        TimeElapsedColumn(),
        console=console,
    )


def _run_with_stage_progress(idea: str, config: Config, provider_instance) -> object:
    """Run generation with live stage progress and return document."""
    with _build_progress() as progress:
        tasks = [
            progress.add_task("Stage 1/3  Analysing idea...", total=1, start=False),
            progress.add_task("Stage 2/3  Writing use case...", total=1, start=False),
            progress.add_task("Stage 3/3  Extracting entities...", total=1, start=False),
        ]
        progress.start_task(tasks[0])

        def on_stage_complete(stage: int) -> None:
            progress.advance(tasks[stage - 1])
            if stage < len(tasks):
                progress.start_task(tasks[stage])

        return asyncio.run(
            run_generate(
                idea,
                config,
                provider_instance,
                on_stage_complete=on_stage_complete,
            )
        )


@app.command()
def generate(
    idea: str = typer.Argument(...),
    actor: str | None = typer.Option(None),
    output: Path | None = typer.Option(None, "-o"),
    provider: str | None = typer.Option(None),
    model: str | None = typer.Option(None),
    format: str = typer.Option("markdown"),
    stdin: bool = typer.Option(False, "--stdin"),
    append: Path | None = typer.Option(None),
) -> None:
    """Generate a use case document from natural language."""
    input_idea = sys.stdin.read().strip() if stdin else idea
    config = load()
    overrides = config.model_dump()
    if provider:
        overrides["provider"] = provider
    if model:
        overrides["model"] = model
    config = Config(**overrides)
    provider_instance = ProviderFactory.create(config)
    document = _run_with_stage_progress(input_idea, config, provider_instance)
    slug = _slug_from_text(actor or document.metadata.actor, document.metadata.goal)
    output_path = output or (config.output_dir / f"{document.metadata.uc_id}-{slug}.md")
    rendered: str
    if format == "json":
        rendered = to_json(document)
    elif format == "yaml":
        rendered = to_yaml(document)
    else:
        rendered = document.raw_markdown
    written_path = _write_document(rendered, output_path, append_path=append)
    if config.hooks_on_generate:
        _run_hook(
            config.hooks_on_generate,
            {"uc_id": document.metadata.uc_id, "file": str(written_path)},
        )
    console.print(
        Panel(
            f"Generated {document.metadata.uc_id} -> {written_path}\n"
            f"Provider: {document.provider}\n"
            f"Model: {document.model}\n"
            f"Duration: {document.duration_ms}ms",
            title="ucgen",
        )
    )


@app.command()
def run(
    id: str | None = typer.Option(None, "--id"),
    tag: str | None = typer.Option(None, "--tag"),
    file: Path = typer.Option(Path("ucgen.yaml"), "--file"),
) -> None:
    """Read ucgen.yaml and generate defined use cases."""
    project = load_project(file)
    config = load()
    selected_use_cases = []
    for use_case in project.use_cases:
        if use_case.status != "pending":
            continue
        if id and use_case.id != id:
            continue
        if tag and tag not in use_case.tags:
            continue
        selected_use_cases.append(use_case)
    provider = ProviderFactory.create(config)
    generated_count = 0
    failed_count = 0
    with _build_progress(include_mofn=True) as progress:
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
                document = asyncio.run(run_generate(use_case.goal, config, provider))
                slug = _slug_from_text(use_case.actor, use_case.goal)
                output_path = config.output_dir / f"{document.metadata.uc_id}-{slug}.md"
                _write_document(document.raw_markdown, output_path)
                generated_count += 1
            except Exception as exc:
                logger.exception("Project use case failed id=%s error=%s", use_case.id, exc)
                failed_count += 1
            finally:
                progress.advance(task)
    if config.hooks_on_batch_complete:
        _run_hook(
            config.hooks_on_batch_complete,
            {"count": str(generated_count), "project": str(file)},
        )
    console.print(
        Panel(
            f"Generated {generated_count} use cases.\nFailed: {failed_count}",
            title="run complete",
        )
    )


@app.command()
def status(file: Path = typer.Option(Path("ucgen.yaml"), "--file")) -> None:
    """Show generation status of all use cases in ucgen.yaml."""
    project = load_project(file)
    config = load()
    rows = get_project_status(project, config.output_dir)
    table = Table("UC-ID", "Title", "Status", "Generated At", "File")
    for row in rows:
        table.add_row(
            row["id"],
            row["title"],
            row["status"],
            str(row["generated_at"] or ""),
            str(row["file_path"] or ""),
        )
    console.print(table)


@app.command()
def batch(
    input_file: Path = typer.Argument(...),
    output: Path | None = typer.Option(None, "-o"),
    provider: str | None = typer.Option(None),
    model: str | None = typer.Option(None),
) -> None:
    """Generate use cases from txt or yaml input files."""
    ideas: list[str] = []
    if input_file.suffix == ".txt":
        for line in input_file.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                ideas.append(cleaned)
    elif input_file.suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            console.print(
                "YAML batch requires PyYAML. Run: pip install ucgen[project]",
                style="red",
            )
            raise typer.Exit(code=1) from exc
        data = yaml.safe_load(input_file.read_text(encoding="utf-8")) or []
        ideas = [item.get("title", "") for item in data if isinstance(item, dict)]
    else:
        raise typer.BadParameter("Input must be .txt or .yaml/.yml")
    config = load()
    overrides = config.model_dump()
    if provider:
        overrides["provider"] = provider
    if model:
        overrides["model"] = model
    config = Config(**overrides)
    provider_instance = ProviderFactory.create(config)
    successes = 0
    failures = 0
    with _build_progress(include_mofn=True) as progress:
        task = progress.add_task("Generating 0 of 0", total=len(ideas))
        for index, item_idea in enumerate(ideas, start=1):
            idea_slug = _slug_from_text("", item_idea)
            progress.update(
                task,
                description=f"Generating {index} of {len(ideas)}: {idea_slug}",
            )
            try:
                document = asyncio.run(run_generate(item_idea, config, provider_instance))
                slug = _slug_from_text(document.metadata.actor, document.metadata.goal)
                output_path = output or (config.output_dir / f"{document.metadata.uc_id}-{slug}.md")
                _write_document(document.raw_markdown, output_path)
                successes += 1
            except Exception as exc:
                logger.exception("Batch item failed: %s", exc)
                failures += 1
            finally:
                progress.advance(task)
    console.print(Panel(f"Succeeded: {successes}\nFailed: {failures}", title="batch"))


@app.command()
def validate(path: Path = typer.Argument(...)) -> None:
    """Validate one markdown file or all markdown files in a directory."""
    files = [path] if path.is_file() else list(path.glob("*.md"))
    table = Table("File", "Passed", "Errors")
    any_failed = False
    for item in files:
        result = validate_file(item)
        if not result.passed:
            any_failed = True
        table.add_row(str(item), "PASS" if result.passed else "FAIL", "; ".join(result.errors))
    console.print(table)
    if any_failed:
        raise typer.Exit(code=1)


@app.command()
def init() -> None:
    """Create .ucgenrc.toml with defaults in current directory."""
    config_path = Path.cwd() / ".ucgenrc.toml"
    if config_path.exists() and not typer.confirm("Overwrite existing .ucgenrc.toml?"):
        raise typer.Exit(code=0)
    config_path.write_text(
        "\n".join(
            [
                'provider = "ollama"',
                'model = "mistral"',
                'output_dir = "./use-cases"',
                'template = "default"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    console.print(f"Created {config_path}")


@app.command(name="init-project")
def init_project(name: str = typer.Argument(...), domain: str | None = typer.Option(None)) -> None:
    """Scaffold a ucgen.yaml file for a new project."""
    path = Path.cwd() / "ucgen.yaml"
    if path.exists() and not typer.confirm("Overwrite existing ucgen.yaml?"):
        raise typer.Exit(code=0)
    content = (
        "project:\n"
        f"  name: {name}\n"
        f"  domain: {domain or 'general'}\n"
        "defaults:\n"
        "  provider: ollama\n"
        "  model: mistral\n"
        "  template: default\n"
        "  output_dir: ./use-cases\n"
        "actors: []\n"
        "use_cases: []\n"
    )
    path.write_text(content, encoding="utf-8")
    (Path.cwd() / "use-cases").mkdir(exist_ok=True)
    console.print(f"Created {path}")


@app.command()
def log(quick: str | None = typer.Option(None, "--quick")) -> None:
    """Placeholder memory logging command."""
    console.print(f"Logged: {quick or 'interactive mode not implemented'}")


@app.command()
def gc(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """Placeholder memory garbage collection command."""
    console.print(f"gc dry-run={dry_run}")


@app.command()
def version() -> None:
    """Print version and provider availability status."""
    config = load()
    table = Table("Provider", "Available")
    providers = ["ollama", "anthropic", "openai", "groq", "custom"]
    for name in providers:
        probe = Config(**{**config.model_dump(), "provider": name})
        available = ProviderFactory.create(probe).is_available()
        table.add_row(name, "yes" if available else "no")
    console.print(f"ucgen {__version__}")
    console.print(table)
