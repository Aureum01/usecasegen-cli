"""Typer CLI entrypoint for ucgen."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import sys
import webbrowser
from datetime import UTC, datetime, timedelta
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
from ucgen.exporter import export_report, load_documents_from_json, to_json
from ucgen.generator import generate as run_generate
from ucgen.project_runner import (
    get_project_status,
    load_project,
    merge_project_config,
    run_project,
)
from ucgen.providers import ProviderFactory
from ucgen.schema import UseCaseDocument
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


def _memory_paths() -> dict[str, Path]:
    root = Path.cwd() / "memory"
    return {
        "root": root,
        "idx": root / "mistakes.idx",
        "mistakes": root / "mistakes",
        "archive": root / "mistakes" / "archive",
        "head": root / "HEAD",
        "conventions": root / "CONVENTIONS",
    }


def _safe_git_output(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _next_mistake_id(idx_path: Path) -> str:
    if not idx_path.exists():
        return "M-001"
    current = 0
    for line in idx_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        token = line.split("\t", maxsplit=1)[0].strip()
        if token.startswith("M-"):
            number = token.removeprefix("M-")
            if number.isdigit():
                current = max(current, int(number))
    return f"M-{current + 1:03d}"


def _detect_changed_file() -> str:
    output = _safe_git_output(["git", "diff", "--name-only", "HEAD"])
    if not output:
        return "unknown"
    first = output.splitlines()[0].strip()
    return first or "unknown"


def _active_mistake_ids(idx_path: Path) -> list[str]:
    if not idx_path.exists():
        return []
    active: list[str] = []
    for line in idx_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 5 and parts[4].strip() == "active":
            active.append(parts[0].strip())
    return active


def _active_decision_ids() -> list[str]:
    decision_path = Path.cwd() / "memory" / "decisions.idx"
    if not decision_path.exists():
        return []
    ids: list[str] = []
    for line in decision_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("D-"):
            ids.append(stripped.split()[0])
    return ids


def _write_memory_head(paths: dict[str, Path]) -> None:
    paths["root"].mkdir(parents=True, exist_ok=True)
    active_mistakes = ", ".join(_active_mistake_ids(paths["idx"])) or "none"
    active_decisions = ", ".join(_active_decision_ids()) or "none"
    based_on = _safe_git_output(["git", "diff", "--name-only", "HEAD"]) or "not a git repository"
    timestamp = datetime.now(UTC).isoformat()
    content = (
        f"Active mistakes: {active_mistakes}\n"
        f"Active decisions: {active_decisions}\n"
        f"Last updated: {timestamp}\n"
        f"Based on: {based_on}\n"
    )
    paths["head"].write_text(content, encoding="utf-8")


def _safe_project_dir_name(name: str) -> str:
    lowered = name.strip().lower().replace(" ", "-")
    cleaned = "".join(ch for ch in lowered if ch.isalnum() or ch == "-")
    compact = "-".join(part for part in cleaned.split("-") if part)
    return compact or "project"


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


def _run_with_stage_progress(
    idea: str,
    config: Config,
    provider_instance,
    debug: bool = False,
) -> UseCaseDocument:
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
                debug=debug,
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
    debug: bool = typer.Option(False, "--debug"),
    report: bool = typer.Option(
        False,
        "--report",
        help="After generating, open HTML report of all use cases",
    ),
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
    document = _run_with_stage_progress(input_idea, config, provider_instance, debug=debug)
    slug = _slug_from_text(actor or document.metadata.actor, document.metadata.goal)
    uc_folder = config.output_dir / "standalone" / f"{document.metadata.uc_id}-{slug}"
    uc_folder.mkdir(parents=True, exist_ok=True)
    md_path = uc_folder / f"{document.metadata.uc_id}-{slug}.md"
    json_path = uc_folder / f"{document.metadata.uc_id}-{slug}.json"
    written_path = _write_document(document.raw_markdown, md_path, append_path=append)
    json_path.write_text(to_json(document), encoding="utf-8")
    if config.hooks_on_generate:
        _run_hook(
            config.hooks_on_generate,
            {"uc_id": document.metadata.uc_id, "file": str(written_path)},
        )
    if report:
        report_path = uc_folder / "report.html"
        export_report([document], report_path, mode="single")
        console.print(f"Report written to {report_path}")
    console.print(
        Panel(
            f"Generated {document.metadata.uc_id} -> {uc_folder}\n"
            f"Provider: {document.provider}\n"
            f"Model: {document.model}\n"
            f"Duration: {document.duration_ms}ms",
            title="ucgen",
        )
    )


@app.command()
def run(
    id: str | None = typer.Option(None, "--id", help="Generate only this UC ID"),
    tag: str | None = typer.Option(None, "--tag", help="Generate only use cases with this tag"),
    file: Path = typer.Option(Path("ucgen.yaml"), "--file", "-f", help="Path to ucgen.yaml"),
    provider: str | None = typer.Option(None, "--provider", help="Override provider"),
    model: str | None = typer.Option(None, "--model", help="Override model"),
) -> None:
    """Generate use cases from ucgen.yaml project file."""
    try:
        project = load_project(file)
    except FileNotFoundError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc
    except ImportError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc

    base_config = load()
    config = merge_project_config(base_config, project)
    overrides = config.model_dump()
    if provider:
        overrides["provider"] = provider
    if model:
        overrides["model"] = model
    config = Config(**overrides)
    provider_instance = ProviderFactory.create(config)
    project_output_dir = config.output_dir / _safe_project_dir_name(project.project.name)
    console.print(f"Generating into {project_output_dir}/")
    generated_docs = asyncio.run(
        run_project(
            project,
            config,
            provider_instance,
            filter_id=id,
            filter_tag=tag,
            filter_status="pending",
        )
    )

    rows_by_id = {row["id"]: row for row in get_project_status(project, config.output_dir)}
    table = Table("UC ID", "Title", "Status", "File", "Duration")
    for doc in generated_docs:
        row = rows_by_id.get(doc.metadata.uc_id, {})
        file_path = row.get("file")
        relative_file = ""
        if isinstance(file_path, Path):
            try:
                relative_file = str(file_path.relative_to(config.output_dir))
            except ValueError:
                relative_file = str(file_path)
        table.add_row(
            doc.metadata.uc_id,
            doc.metadata.title,
            "generated",
            relative_file,
            f"{doc.duration_ms}ms",
        )
    console.print(table)
    console.print(Panel(f"Generated {len(generated_docs)} use cases", title="run complete"))


@app.command()
def status(file: Path = typer.Option(Path("ucgen.yaml"), "--file", "-f")) -> None:
    """Show generation status of all use cases in ucgen.yaml."""
    try:
        project = load_project(file)
    except FileNotFoundError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc
    except ImportError as exc:
        console.print(str(exc), style="red")
        raise typer.Exit(code=1) from exc
    base_config = load()
    config = merge_project_config(base_config, project)
    rows = get_project_status(project, config.output_dir)
    table = Table(
        "UC ID",
        "Title",
        "Actor",
        "Priority",
        "Tags",
        "Status",
        "Generated At",
        "Model",
        "File",
    )
    generated = 0
    pending = 0
    reviewed = 0
    for row in rows:
        status_value = str(row["status"])
        style = "yellow"
        if status_value == "generated":
            style = "green"
            generated += 1
        elif status_value == "reviewed":
            style = "blue"
            reviewed += 1
        elif status_value == "pending":
            pending += 1
        file_path = row.get("file")
        relative_file = "—"
        if isinstance(file_path, Path):
            try:
                relative_file = str(file_path.relative_to(config.output_dir))
            except ValueError:
                relative_file = str(file_path)
        table.add_row(
            row["id"],
            row["title"],
            row["actor"],
            row["priority"],
            ", ".join(row["tags"]),
            status_value,
            str(row["generated_at"] or ""),
            str(row["model"] or ""),
            relative_file,
            style=style,
        )
    console.print(table)
    console.print(f"{generated} generated, {pending} pending, {reviewed} reviewed")


@app.command()
def batch(
    input_file: Path = typer.Argument(...),
    output: Path | None = typer.Option(None, "-o"),
    provider: str | None = typer.Option(None),
    model: str | None = typer.Option(None),
    report: bool = typer.Option(False, "--report"),
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
    batch_ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    batch_folder = config.output_dir / "batch" / batch_ts
    batch_folder.mkdir(parents=True, exist_ok=True)
    console.print(f"Batch output -> {batch_folder}/")
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
                md_path = output or (batch_folder / f"{document.metadata.uc_id}-{slug}.md")
                json_path = batch_folder / f"{document.metadata.uc_id}-{slug}.json"
                _write_document(document.raw_markdown, md_path)
                json_path.write_text(to_json(document), encoding="utf-8")
                successes += 1
            except Exception as exc:
                logger.exception("Batch item failed: %s", exc)
                failures += 1
            finally:
                progress.advance(task)
    if report:
        report_path = batch_folder / "report.html"
        batch_docs = load_documents_from_json(batch_folder)
        export_report(batch_docs, report_path, mode="portfolio")
        console.print(f"Report written to {report_path}")
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
def init_project(
    name: str = typer.Argument(..., help="Project name"),
    domain: str | None = typer.Option(None, "--domain", help="Business domain"),
    output: Path = typer.Option(Path("ucgen.yaml"), "--output", "-o"),
) -> None:
    """Scaffold a ucgen.yaml file for a new project."""
    path = output
    if path.exists() and not typer.confirm(f"Overwrite existing {path.name}?"):
        raise typer.Exit(code=0)
    content = f"""# ucgen.yaml — Project use case definition
# Run: ucgen run       (generate all pending)
# Run: ucgen status    (check generation status)

project:
  name: {name}
  domain: {domain or "general"}
  stack: python-fastapi-postgres
  version: "1.0"

defaults:
  provider: ollama
  model: mistral
  template: default
  output_dir: ./use-cases

actors:
  - name: Patient
    description: Registered patient with an active account
    type: human

  - name: BookingSystem
    description: Internal booking and schedule allocation service
    type: system

use_cases:
  - id: UC-001
    title: Book Appointment
    actor: Patient
    goal: Reserve an available slot with a preferred provider
    priority: high
    tags: [booking, core]
    status: pending

  - id: UC-002
    title: Cancel Appointment
    actor: Patient
    goal: Cancel an existing confirmed appointment with optional reason
    priority: high
    tags: [booking, core]
    status: pending

  - id: UC-003
    title: Check In Patient
    actor: BookingSystem
    goal: Record patient arrival and notify the assigned provider
    priority: medium
    tags: [reception]
    status: pending

# hooks:
#   on_generate: "git add {{file}}"
#   on_batch_complete: "echo 'Generated {{count}} use cases for {{project}}'"
"""
    path.write_text(content, encoding="utf-8")
    console.print(f"Created {path} — edit it then run: ucgen run")


@app.command()
def log(
    quick: str | None = typer.Option(
        None,
        "--quick",
        "-q",
        help="One-liner description — skips interactive mode",
    ),
) -> None:
    """Log a mistake or correction to memory so Cursor never repeats it."""
    paths = _memory_paths()
    paths["mistakes"].mkdir(parents=True, exist_ok=True)
    paths["archive"].mkdir(parents=True, exist_ok=True)
    paths["idx"].parent.mkdir(parents=True, exist_ok=True)
    if not paths["idx"].exists():
        paths["idx"].write_text("", encoding="utf-8")

    if quick:
        file_affected = _detect_changed_file()
        what_happened = quick
        why_wrong = None
        correct_approach = None
    else:
        default_file = _detect_changed_file()
        file_input = typer.prompt(
            "Which file was affected? (Enter to use git diff result)",
            default=default_file,
            show_default=False,
        )
        file_affected = file_input or default_file
        what_happened = typer.prompt("What did the AI do wrong? (one line)")
        why_wrong_input = typer.prompt("Why is that wrong? (Enter to skip)", default="")
        correct_input = typer.prompt("What is the correct approach? (Enter to skip)", default="")
        why_wrong = why_wrong_input or None
        correct_approach = correct_input or None

    mistake_id = _next_mistake_id(paths["idx"])
    git_commit = _safe_git_output(["git", "log", "-1", "--pretty=%h"]) or "unknown"
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    idx_line = f"{mistake_id}\t{file_affected}\t{what_happened}\t0\tactive\n"
    with paths["idx"].open("a", encoding="utf-8") as file:
        file.write(idx_line)

    payload = {
        "id": mistake_id,
        "date": now,
        "logged_by": "ucgen log",
        "git_commit": git_commit,
        "file_affected": file_affected,
        "what_happened": what_happened,
        "why_wrong": why_wrong,
        "correct_approach": correct_approach,
        "recurrence_count": 0,
    }
    json_path = paths["mistakes"] / f"{mistake_id}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    _write_memory_head(paths)
    console.print(f"Logged {mistake_id} -> {json_path}")


@app.command()
def gc(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """Archive old memory entries and graduate high-recurrence mistakes to conventions."""
    paths = _memory_paths()
    if not paths["idx"].exists():
        console.print("No mistakes index found.")
        return
    paths["archive"].mkdir(parents=True, exist_ok=True)
    if not paths["conventions"].exists():
        paths["conventions"].parent.mkdir(parents=True, exist_ok=True)
        paths["conventions"].write_text("", encoding="utf-8")

    now = datetime.now(UTC)
    lines = [line for line in paths["idx"].read_text(encoding="utf-8").splitlines() if line.strip()]
    kept_lines: list[str] = []
    graduated = 0
    archived = 0
    merged = 0
    seen_by_file: dict[str, tuple[str, str, int, str]] = {}

    for line in lines:
        parts = line.split("\t")
        if len(parts) < 5:
            kept_lines.append(line)
            continue
        mistake_id, file_affected, what_happened, rec_str, status = parts[:5]
        recurrence = int(rec_str) if rec_str.isdigit() else 0
        json_path = paths["mistakes"] / f"{mistake_id}.json"
        payload = {}
        if json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
        date_str = str(payload.get("date") or "")
        parsed_date = None
        if date_str:
            try:
                parsed_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                parsed_date = None

        duplicate_key = f"{file_affected}:{what_happened.lower()}"
        duplicate = None
        for key, item in seen_by_file.items():
            if file_affected == item[0] and (what_happened.lower() in key or key in duplicate_key):
                duplicate = item
                break
        if duplicate:
            keep_file, keep_what, keep_recurrence, keep_id = duplicate
            if dry_run:
                console.print(f"Would merge {mistake_id} into {keep_id}")
            else:
                merged += 1
                if typer.confirm(f"Merge {mistake_id} into {keep_id}?", default=True):
                    keep_recurrence = max(keep_recurrence, recurrence)
                    keep_line = (
                        f"{keep_id}\t{keep_file}\t{keep_what}\t"
                        f"{keep_recurrence}\tactive"
                    )
                    kept_lines = [
                        item if not item.startswith(f"{keep_id}\t") else keep_line
                        for item in kept_lines
                    ]
                    if json_path.exists():
                        shutil.move(str(json_path), str(paths["archive"] / json_path.name))
                    continue

        seen_by_file[duplicate_key] = (file_affected, what_happened, recurrence, mistake_id)

        if recurrence >= 3 and status == "active":
            summary = payload.get("correct_approach") or what_happened
            if dry_run:
                console.print(f"Would graduate {mistake_id}: {summary}")
            else:
                if typer.confirm(f"Graduate {mistake_id} to CONVENTIONS?", default=True):
                    stamp = now.date().isoformat()
                    with paths["conventions"].open("a", encoding="utf-8") as file:
                        entry = (
                            f"[{stamp}] Graduated from {mistake_id} "
                            f"(recurrence:{recurrence}): {summary}\n"
                        )
                        file.write(entry)
                    graduated += 1
                    if json_path.exists():
                        shutil.move(str(json_path), str(paths["archive"] / json_path.name))
                    continue
        if (
            recurrence == 0
            and parsed_date is not None
            and (now - parsed_date) > timedelta(days=90)
            and status == "active"
        ):
            if dry_run:
                console.print(f"Would archive stale {mistake_id}")
            else:
                archived += 1
                if json_path.exists():
                    shutil.move(str(json_path), str(paths["archive"] / json_path.name))
                continue
        kept_lines.append(line)

    if not dry_run:
        index_text = ("\n".join(kept_lines) + "\n") if kept_lines else ""
        paths["idx"].write_text(index_text, encoding="utf-8")
        _write_memory_head(paths)
    console.print(f"Graduated: {graduated}, Archived: {archived}, Merged: {merged}")


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


@app.command()
def report(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output HTML path (default: ./use-cases/report.html)",
    ),
    open_browser: bool = typer.Option(
        False,
        "--open",
        help="Open generated report in default browser",
    ),
) -> None:
    """Generate a single HTML report from all use case JSON files."""
    config = load()
    resolved_output = output or (config.output_dir / "report.html")
    with _build_progress() as progress:
        task = progress.add_task("Loading use case JSON files...", total=2)
        docs = load_documents_from_json(config.output_dir)
        progress.advance(task)
        progress.update(task, description="Rendering HTML report...")
        export_report(docs, resolved_output, mode="portfolio")
        progress.advance(task)
    console.print(f"Report written to {resolved_output}")
    if open_browser:
        webbrowser.open(resolved_output.resolve().as_uri())
