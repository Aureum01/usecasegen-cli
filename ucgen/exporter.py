"""Export UseCaseDocument into alternate formats."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateError

from ucgen.schema import UseCaseDocument


def to_json(doc: UseCaseDocument) -> str:
    """Serialise UseCaseDocument to pretty-printed JSON string.

    Args:
        doc: Document to export.

    Returns:
        Pretty-printed JSON string.
    """
    return doc.model_dump_json(indent=2)


def to_yaml(doc: UseCaseDocument) -> str:
    """Export a document as YAML.

    Args:
        doc: Document to export.

    Returns:
        YAML string.

    Raises:
        ImportError: If PyYAML is not installed.
    """
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("YAML export requires PyYAML. Run: pip install ucgen[project]") from exc
    return yaml.safe_dump(doc.model_dump(mode="json"), sort_keys=False)


def _badge_class_for_nfr(nfr_type: str) -> str:
    """Map NFR type to report badge class name."""
    key = (nfr_type or "").strip().lower()
    mapping = {
        "latency": "b-blue",
        "throughput": "b-cyan",
        "availability": "b-green",
        "consistency": "b-purple",
        "idempotency": "b-amber",
    }
    return mapping.get(key, "b-blue")


def _field_constraint_badges(constraints: list[str]) -> list[dict[str, str]]:
    """Build styled badges for entity field constraints."""
    badges: list[dict[str, str]] = []
    for raw in constraints:
        item = (raw or "").strip().upper()
        if not item:
            continue
        css_class = "b-blue"
        if item == "PK":
            css_class = "b-amber"
        elif item == "FK":
            css_class = "b-purple"
        elif item == "NOT NULL":
            css_class = "b-green"
        elif item == "UNIQUE":
            css_class = "b-cyan"
        elif item == "INDEX":
            css_class = "b-blue"
        badges.append({"label": item, "class": css_class})
    return badges


def _normalise_docs(docs: list[UseCaseDocument]) -> list[dict[str, Any]]:
    """Prepare report-friendly data for template rendering."""
    prepared: list[dict[str, Any]] = []
    for doc in docs:
        model = doc.model_dump(mode="json")
        metadata = model["metadata"]
        sections = model["sections"]
        entities = model["entities"]["entities"]

        nfr_rows: list[dict[str, Any]] = []
        for row in sections.get("nfr") or []:
            row_copy = dict(row)
            row_copy["badge_class"] = _badge_class_for_nfr(str(row_copy.get("type", "")))
            nfr_rows.append(row_copy)

        entity_cards: list[dict[str, Any]] = []
        for entity in entities:
            fields = []
            for field in entity.get("fields", []):
                field_copy = dict(field)
                field_copy["badges"] = _field_constraint_badges(field_copy.get("constraints", []))
                fields.append(field_copy)
            entity_cards.append(
                {
                    "name": entity.get("name", ""),
                    "fields": fields,
                    "relationships": entity.get("relationships", []),
                }
            )

        prepared.append(
            {
                "uc_id": metadata.get("uc_id", ""),
                "title": metadata.get("title", ""),
                "domain": metadata.get("domain", ""),
                "goal_level": metadata.get("goal_level", ""),
                "actor": metadata.get("actor", ""),
                "system_boundary": metadata.get("system_boundary") or "N/A",
                "frequency": (metadata.get("scale_hints") or {}).get("frequency") or "N/A",
                "trigger": metadata.get("trigger", ""),
                "stakeholders": metadata.get("stakeholders", []),
                "minimal_guarantee": sections.get("minimal_guarantee", ""),
                "success_guarantee": sections.get("success_guarantee", ""),
                "preconditions": sections.get("preconditions", []),
                "normal_course": sections.get("normal_course", []),
                "alternative_courses": sections.get("alternative_courses", []),
                "postconditions": sections.get("postconditions", []),
                "information_requirements": sections.get("information_requirements", []),
                "nfr": nfr_rows,
                "state_machine": sections.get("state_machine"),
                "entities": entity_cards,
                "open_issues": sections.get("open_issues") or [],
            }
        )
    return prepared


def load_documents_from_json(output_dir: Path) -> list[UseCaseDocument]:
    """Load UseCaseDocument entries from output directory JSON files."""
    documents: list[UseCaseDocument] = []
    for file_path in sorted(output_dir.rglob("*.json")):
        if any(part.startswith(".") for part in file_path.parts):
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
            payload = json.loads(text)
            documents.append(UseCaseDocument.model_validate(payload))
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            continue
    return documents


def export_report(
    docs: list[UseCaseDocument],
    output_path: Path,
    mode: str = "portfolio",
) -> Path:
    """Render report HTML for use case docs and write to disk."""
    template_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    context_docs = _normalise_docs(docs)
    title = "Use Case Report"
    try:
        template = env.get_template("report.html.j2")
        html_out = template.render(
            docs=context_docs,
            report_title=title,
            has_docs=bool(context_docs),
            mode=mode,
            html=html,
        )
    except TemplateError as exc:
        raise RuntimeError(f"Failed to render report template: {exc}") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_out, encoding="utf-8")
    return output_path
