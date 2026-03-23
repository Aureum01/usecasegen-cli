"""HTML report generation for ucgen output files."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


def _parse_frontmatter(raw_text: str) -> tuple[dict[str, Any], str]:
    """Parse frontmatter from markdown text."""
    if not raw_text.startswith("---"):
        return {}, raw_text
    parts = raw_text.split("---", maxsplit=2)
    if len(parts) < 3:
        return {}, raw_text
    frontmatter_text = parts[1].strip()
    body = parts[2].lstrip("\r\n")
    if not frontmatter_text:
        return {}, body
    if frontmatter_text.startswith("{") and frontmatter_text.endswith("}"):
        try:
            parsed = json.loads(frontmatter_text)
            if isinstance(parsed, dict):
                return parsed, body
        except json.JSONDecodeError:
            pass
    metadata: dict[str, Any] = {}
    for line in frontmatter_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", maxsplit=1)
        metadata[key.strip()] = value.strip()
    return metadata, body


def _inline(text: str) -> str:
    """Escape and render simple inline markdown."""
    escaped = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _parse_sections(body: str) -> dict[str, list[str]]:
    """Split markdown body by H2 headings."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line.rstrip())
    return sections


def _render_ul(lines: list[str]) -> str:
    items = [line[2:].strip() for line in lines if line.strip().startswith("- ")]
    if not items:
        return "<p>—</p>"
    rendered = "".join(f"<li>{_inline(item)}</li>" for item in items)
    return f"<ul>{rendered}</ul>"


def _render_normal_course(lines: list[str]) -> str:
    entries: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+\.\s", stripped):
            entries.append(re.sub(r"^\d+\.\s*", "", stripped))
    if not entries:
        return "<p>—</p>"
    rendered = "".join(f"<li>{_inline(item)}</li>" for item in entries)
    return f"<ol>{rendered}</ol>"


def _render_nfr_table(lines: list[str]) -> str:
    table_lines = [line.strip() for line in lines if line.strip().startswith("|")]
    if len(table_lines) < 3:
        return "<p>—</p>"
    rows: list[list[str]] = []
    for line in table_lines:
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    headers = rows[0]
    data_rows = rows[2:]
    head_html = "".join(f"<th>{_inline(col)}</th>" for col in headers)
    body_html = ""
    for row in data_rows:
        body_html += "<tr>" + "".join(f"<td>{_inline(col)}</td>" for col in row) + "</tr>"
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


def _render_paragraph(lines: list[str]) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    return f"<p>{_inline(text)}</p>" if text else "<p>—</p>"


def _render_use_case(metadata: dict[str, Any], sections: dict[str, list[str]]) -> str:
    uc_id = str(metadata.get("uc_id", "UC-unknown"))
    title = str(metadata.get("title", uc_id))
    actor = str(metadata.get("actor", "—"))
    model = str(metadata.get("model", "—"))
    duration_ms = str(metadata.get("duration_ms", "—"))

    preconditions = _render_ul(sections.get("Preconditions", []))
    minimal_guarantee = _render_paragraph(sections.get("Minimal Guarantee", []))
    success_guarantee = _render_paragraph(sections.get("Success Guarantee", []))
    normal_course = _render_normal_course(sections.get("Normal Course", []))
    alternative_courses = _render_ul(sections.get("Alternative Courses", []))
    postconditions = _render_ul(sections.get("Postconditions", []))
    info_requirements = _render_ul(sections.get("Information Requirements", []))
    nfr_table = _render_nfr_table(sections.get("Non-Functional Requirements", []))
    open_issues = _render_ul(sections.get("Open Issues", []))

    return f"""
    <div class="use-case" id="{html.escape(uc_id)}">
      <h1>{_inline(uc_id)} — {_inline(title)}</h1>
      <div class="meta">
        <div><strong>Actor:</strong> {_inline(actor)}</div>
        <div><strong>Model:</strong> {_inline(model)}</div>
        <div><strong>Duration:</strong> {_inline(duration_ms)} ms</div>
      </div>

      <h2>Preconditions</h2>
      {preconditions}
      <h2>Minimal Guarantee</h2>
      {minimal_guarantee}
      <h2>Success Guarantee</h2>
      {success_guarantee}
      <h2>Normal Course</h2>
      {normal_course}
      <h2>Alternative Courses</h2>
      {alternative_courses}
      <h2>Postconditions</h2>
      {postconditions}
      <h2>Information Requirements</h2>
      {info_requirements}
      <h2>Non-Functional Requirements</h2>
      {nfr_table}
      <h2>Open Issues</h2>
      {open_issues}
    </div>
    """


def generate_report(use_case_files: list[Path], title: str) -> str:
    """Read markdown use cases and return a standalone HTML report."""
    docs: list[dict[str, Any]] = []
    for file_path in sorted(use_case_files):
        raw = file_path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(raw)
        sections = _parse_sections(body)
        docs.append({"metadata": metadata, "sections": sections})

    safe_title = html.escape(title)
    nav_links = []
    rendered_docs = []
    for doc in docs:
        metadata = doc["metadata"]
        uc_id = str(metadata.get("uc_id", "UC-unknown"))
        uc_title = str(metadata.get("title", uc_id))
        nav_links.append(
            f'<a href="#{html.escape(uc_id)}">{_inline(uc_id)} — {_inline(uc_title)}</a>'
        )
        rendered_docs.append(_render_use_case(metadata, doc["sections"]))

    nav_html = "\n".join(nav_links) if nav_links else "<a href=\"#\">No use cases found</a>"
    body_html = "\n".join(rendered_docs) if rendered_docs else "<p>No use case files found.</p>"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{safe_title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; display: flex; }}
    nav {{
      width: 260px; min-height: 100vh; background: #1f3864; padding: 20px;
      box-sizing: border-box; position: fixed; overflow-y: auto;
    }}
    nav a {{
      display: block; color: #cce0ff; text-decoration: none;
      padding: 6px 0; font-size: 13px;
    }}
    nav a:hover {{ color: #ffffff; }}
    main {{ margin-left: 280px; padding: 40px; max-width: 900px; }}
    .use-case {{ border-bottom: 2px solid #e0e0e0; margin-bottom: 60px; padding-bottom: 40px; }}
    h1 {{ color: #1f3864; }}
    h2 {{ color: #2e75b6; border-bottom: 1px solid #e0e0e0; padding-bottom: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th {{ background: #1f3864; color: white; padding: 8px 12px; text-align: left; }}
    td {{ padding: 8px 12px; border: 1px solid #ddd; }}
    tr:nth-child(even) {{ background: #f5f9ff; }}
    .meta {{
      background: #f0f4ff; border-left: 4px solid #2e75b6;
      padding: 12px 16px; margin-bottom: 24px; font-size: 13px;
    }}
    .meta > div {{ margin: 4px 0; }}
    code {{ background: #f3f3f3; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
  </style>
</head>
<body>
  <nav>
    <div style="color:white;font-weight:bold;margin-bottom:16px;">{safe_title}</div>
    {nav_html}
  </nav>
  <main>
    {body_html}
  </main>
</body>
</html>
"""
