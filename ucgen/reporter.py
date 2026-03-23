"""HTML report generation for ucgen output files."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


def _parse_frontmatter(raw_text: str) -> tuple[dict[str, Any], str]:
    """Parse frontmatter from markdown text.

    Args:
        raw_text: Full markdown file content.

    Returns:
        Tuple of parsed metadata dictionary and markdown body.
    """
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


def _inline_format(text: str) -> str:
    """Convert inline markdown patterns to HTML."""
    escaped = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _render_table(lines: list[str]) -> str:
    """Render pipe table lines to HTML table."""
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or "|" not in stripped[1:]:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return f"<p>{_inline_format(' '.join(lines))}</p>"
    header = rows[0]
    data_rows = rows[2:] if len(rows) >= 3 else []
    th = "".join(f"<th>{_inline_format(cell)}</th>" for cell in header)
    body = ""
    for row in data_rows:
        tds = "".join(f"<td>{_inline_format(cell)}</td>" for cell in row)
        body += f"<tr>{tds}</tr>"
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _markdown_to_html(markdown_body: str) -> str:
    """Convert a constrained markdown subset into HTML."""
    lines = markdown_body.splitlines()
    chunks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            chunks.append(_render_table(table_lines))
            continue
        if stripped.startswith("## "):
            chunks.append(f"<h2>{_inline_format(stripped[3:].strip())}</h2>")
            index += 1
            continue
        if stripped.startswith("# "):
            chunks.append(f"<h1>{_inline_format(stripped[2:].strip())}</h1>")
            index += 1
            continue
        if stripped.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(lines[index].strip()[2:].strip())
                index += 1
            lis = "".join(f"<li>{_inline_format(item)}</li>" for item in items)
            chunks.append(f"<ul>{lis}</ul>")
            continue
        chunks.append(f"<p>{_inline_format(stripped)}</p>")
        index += 1
    return "\n".join(chunks)


def generate_report(use_case_files: list[Path], title: str) -> str:
    """Read all markdown use cases and return a standalone HTML report.

    Args:
        use_case_files: Markdown files to include in report.
        title: Report title shown in header and browser tab.

    Returns:
        Fully self-contained HTML page string.
    """
    docs: list[dict[str, Any]] = []
    for file_path in sorted(use_case_files):
        text = file_path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(text)
        docs.append(
            {
                "file": file_path.name,
                "metadata": metadata,
                "content_html": _markdown_to_html(body),
            }
        )
    docs_json = json.dumps(docs)
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --card: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --border: #e5e7eb;
      --header: #0f172a;
      --high: #dc2626;
      --medium: #d97706;
      --low: #6b7280;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--text);
      background: var(--bg);
    }}
    header {{
      background: var(--header);
      color: #fff;
      padding: 14px 20px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 260px 1fr;
      min-height: calc(100vh - 52px);
    }}
    aside {{
      border-right: 1px solid var(--border);
      background: #fff;
      overflow-y: auto;
      padding: 12px;
    }}
    .item {{
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 10px;
      cursor: pointer;
      background: var(--card);
    }}
    .item.active {{ border-color: #2563eb; }}
    .ucid {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
    .title {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
    .meta {{ font-size: 12px; color: var(--muted); display: flex; gap: 8px; align-items: center; }}
    .badge {{
      font-size: 11px;
      border-radius: 999px;
      padding: 2px 8px;
      color: #fff;
      text-transform: lowercase;
    }}
    .badge.high {{ background: var(--high); }}
    .badge.medium {{ background: var(--medium); }}
    .badge.low {{ background: var(--low); }}
    main {{ padding: 22px; overflow-y: auto; }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .meta-card {{
      border: 1px solid var(--border);
      background: #fff;
      border-radius: 8px;
      padding: 10px;
    }}
    .meta-label {{ font-size: 12px; color: var(--muted); }}
    .meta-value {{ font-size: 14px; font-weight: 600; }}
    .content {{
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #fff;
      padding: 18px;
    }}
    h1, h2 {{ margin-top: 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid var(--border);
      text-align: left;
      padding: 8px;
      vertical-align: top;
    }}
    ul {{ padding-left: 20px; }}
    @media print {{
      .layout {{ display: block; }}
      aside {{ display: none; }}
      main {{ padding: 0; }}
      .doc {{ page-break-after: always; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>{safe_title}</div>
    <div id="count"></div>
  </header>
  <div class="layout">
    <aside id="sidebar"></aside>
    <main id="main"></main>
  </div>
  <script>
    const docs = {docs_json};
    const sidebar = document.getElementById("sidebar");
    const main = document.getElementById("main");
    document.getElementById("count").textContent = `${{docs.length}} use cases`;

    function priorityClass(priority) {{
      const normalized = (priority || "low").toLowerCase();
      if (normalized === "high") return "high";
      if (normalized === "medium") return "medium";
      return "low";
    }}

    function renderSidebar(selectedIndex) {{
      sidebar.innerHTML = "";
      docs.forEach((doc, index) => {{
        const metadata = doc.metadata || {{}};
        const item = document.createElement("div");
        item.className = `item ${{index === selectedIndex ? "active" : ""}}`;
        item.innerHTML = `
          <div class="ucid">${{metadata.uc_id || "UC-unknown"}}</div>
          <div class="title">${{metadata.title || doc.file}}</div>
          <div class="meta">
            <span>${{metadata.actor || "Unknown actor"}}</span>
            <span class="badge ${{priorityClass(metadata.priority)}}">
              ${{metadata.priority || "low"}}
            </span>
          </div>
        `;
        item.onclick = () => selectDoc(index);
        sidebar.appendChild(item);
      }});
    }}

    function renderDoc(index) {{
      const doc = docs[index];
      const m = doc.metadata || {{}};
      const ucId = m.uc_id || "—";
      const actor = m.actor || "—";
      const goalLevel = m.goal_level || "—";
      const domain = m.domain || "—";
      const provider = m.provider || "—";
      const fileName = doc.file;
      main.innerHTML = `
        <section class="doc">
          <div class="meta-grid">
            <div class="meta-card"><div class="meta-label">UC ID</div><div class="meta-value">${{ucId}}</div></div>
            <div class="meta-card"><div class="meta-label">Actor</div><div class="meta-value">${{actor}}</div></div>
            <div class="meta-card"><div class="meta-label">Goal Level</div><div class="meta-value">${{goalLevel}}</div></div>
            <div class="meta-card"><div class="meta-label">Domain</div><div class="meta-value">${{domain}}</div></div>
            <div class="meta-card"><div class="meta-label">Provider</div><div class="meta-value">${{provider}}</div></div>
            <div class="meta-card"><div class="meta-label">File</div><div class="meta-value">${{fileName}}</div></div>
          </div>
          <article class="content">${{doc.content_html}}</article>
        </section>
      `;
    }}

    function selectDoc(index) {{
      renderSidebar(index);
      renderDoc(index);
    }}

    if (docs.length > 0) {{
      selectDoc(0);
    }} else {{
      main.innerHTML = "<p>No use case files found.</p>";
    }}
  </script>
</body>
</html>
"""
