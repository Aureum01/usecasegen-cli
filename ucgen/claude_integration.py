"""Claude Code CLI integration for optional --docx via Claude (lazy-import only)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from ucgen.theme import ERROR, MUTED, PRIMARY, SUCCESS, WARNING

_PERMISSION_FLAGS_CACHE: list[str] | None = None


def _strip_frontmatter(md_content: str) -> str:
    """
    Remove leading YAML frontmatter block (--- ... ---) from markdown content.

    Claude Code CLI interprets a leading '---' as an unknown option flag, so the
    body passed to Claude must not start with frontmatter delimiters.
    """
    pattern = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
    return pattern.sub("", md_content, count=1).lstrip()


def _claude_supports_allowed_tools(cmd: str) -> bool:
    """Return True if this Claude Code version supports --allowedTools."""
    try:
        result = subprocess.run(
            [cmd, "--help"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return "--allowedTools" in (result.stdout + result.stderr)
    except Exception:
        return False


def _get_permission_flags(cmd: str) -> list[str]:
    """
    Return the correct permission flags for this Claude Code version.

    Newer versions use --allowedTools.
    Older versions use --dangerously-skip-permissions.
    Result is cached so the probe only runs once per session.
    """
    global _PERMISSION_FLAGS_CACHE
    if _PERMISSION_FLAGS_CACHE is not None:
        return _PERMISSION_FLAGS_CACHE

    if _claude_supports_allowed_tools(cmd):
        _PERMISSION_FLAGS_CACHE = [
            "--print",
            "--allowedTools",
            "Bash",
            "--allowedTools",
            "Write",
            "--allowedTools",
            "Edit",
        ]
    else:
        _PERMISSION_FLAGS_CACHE = [
            "--print",
            "--dangerously-skip-permissions",
        ]

    return _PERMISSION_FLAGS_CACHE


def _run_claude_with_message(
    cmd: str,
    message: str,
    cwd: Path | None = None,
) -> None:
    """
    Pass a message to Claude Code with file-write permissions pre-approved.

    Uses --print for non-interactive streaming output.
    Uses --allowedTools or --dangerously-skip-permissions depending on version.
    Falls back to a named temp file if stdin piping is not supported.
    """
    base_flags = _get_permission_flags(cmd)
    run_cwd = str(cwd) if cwd else None

    # Attempt 1 — stdin pipe
    try:
        result = subprocess.run(
            [cmd] + base_flags + ["-p", "-"],
            input=message,
            text=True,
            cwd=run_cwd,
            capture_output=True,
            check=False,
        )
        stderr_text = (result.stderr or "").lower()
        if "unknown option" not in stderr_text and "unknown flag" not in stderr_text:
            if result.stdout:
                print(result.stdout)
            return
    except Exception:
        pass

    # Attempt 2 — named temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(message)
        tmp_path = tmp.name

    try:
        subprocess.run(
            [
                cmd,
                *base_flags,
                f"Read this file and follow the instructions at the end: {tmp_path}",
            ],
            text=True,
            cwd=run_cwd,
            check=False,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def is_claude_installed() -> bool:
    """Return True if the Claude Code CLI binary is on PATH."""
    cmd = "claude.cmd" if sys.platform == "win32" else "claude"
    return shutil.which(cmd) is not None


def is_npm_installed() -> bool:
    """Return True if npm is available."""
    return shutil.which("npm") is not None


def install_claude_code(console: Console) -> bool:
    """Prompt user, then run npm install -g @anthropic-ai/claude-code."""
    console.print(f"\n[{WARNING}]Claude Code CLI is not installed.[/]")
    console.print(f"[{MUTED}]ucgen can install it now using npm.[/]\n")

    if not is_npm_installed():
        console.print(
            f"[{ERROR}]✗  npm is not installed.[/]\n"
            f"[{MUTED}]Install Node.js from https://nodejs.org then re-run this command.[/]"
        )
        return False

    confirmed = Confirm.ask(
        f"[{PRIMARY}]Install Claude Code CLI now?[/]",
        default=True,
    )
    if not confirmed:
        console.print(f"[{MUTED}]Skipped. You can install manually:[/]")
        console.print("[bold]  npm install -g @anthropic-ai/claude-code[/bold]\n")
        return False

    console.print(f"\n[{PRIMARY}]Installing Claude Code CLI...[/]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"[{PRIMARY}]Running npm install -g @anthropic-ai/claude-code",
            total=None,
        )
        result = subprocess.run(
            ["npm", "install", "-g", "@anthropic-ai/claude-code"],
            capture_output=True,
            text=True,
            check=False,
        )
        progress.update(task, completed=1)

    if result.returncode != 0:
        console.print(f"[{ERROR}]✗  Installation failed.[/]")
        console.print(f"[{MUTED}]{result.stderr.strip()}[/]")
        console.print(f"[{MUTED}]Run: npm install -g @anthropic-ai/claude-code[/]")
        return False

    console.print(f"[{SUCCESS}]✓  Claude Code installed successfully.[/]\n")
    return True


def is_claude_authenticated() -> bool:
    """Probe whether Claude Code is reachable and not asking for auth."""
    cmd = "claude.cmd" if sys.platform == "win32" else "claude"
    try:
        result = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        combined = (result.stdout + result.stderr).lower()
        auth_phrases = ["login", "authenticate", "sign in", "api key", "unauthorized", "not logged"]
        if any(phrase in combined for phrase in auth_phrases):
            return False
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def run_auth_flow(console: Console) -> bool:
    """Launch interactive Claude auth so the user can sign in."""
    console.print(f"\n[{WARNING}]Claude Code needs authentication.[/]")
    console.print(f"[{MUTED}]We'll launch the Claude Code auth flow in your terminal.[/]")
    console.print(
        f"[{MUTED}]A browser link may appear — open it, sign in, then return here.[/]\n"
    )

    confirmed = Confirm.ask(
        f"[{PRIMARY}]Launch Claude Code authentication now?[/]",
        default=True,
    )
    if not confirmed:
        console.print(
            f"[{MUTED}]Skipped. Run `claude` manually to authenticate, then re-run ucgen.[/]\n"
        )
        return False

    cmd = "claude.cmd" if sys.platform == "win32" else "claude"
    console.print(f"\n[{PRIMARY}]Launching Claude Code...[/]")
    console.print(f"[{MUTED}](Complete authentication in your browser, then return here)[/]\n")

    subprocess.run([cmd], text=True, check=False)

    console.print(f"\n[{PRIMARY}]Checking authentication status...[/]")
    time.sleep(1)

    if is_claude_authenticated():
        console.print(f"[{SUCCESS}]✓  Authentication successful.[/]\n")
        return True
    console.print(
        f"[{ERROR}]✗  Could not confirm authentication.[/]\n"
        f"[{MUTED}]Run `claude` manually to complete sign-in, then re-run ucgen with --claude.[/]\n"
        f"[{MUTED}]Or install the CLI: npm install -g @anthropic-ai/claude-code[/]\n"
    )
    return False


def run_claude_docx(
    md_path: Path,
    console: Console,
    skip_exists_check: bool = False,
) -> None:
    """
    Open Claude Code with markdown + instructions to produce a .docx.

    If ``skip_exists_check`` is True, the post-run existence check is skipped
    so that callers (e.g. ``--docx`` followed by ``--claude``) do not emit a
    duplicate success message for the same file.
    """
    md_content = md_path.read_text(encoding="utf-8")
    docx_target = md_path.with_suffix(".docx")

    body = _strip_frontmatter(md_content)

    instruction = (
        "\n\n---\n"
        "Using the use case document above, generate a professionally formatted "
        "Word document (.docx) that matches the ucgen template:\n"
        "- Title page with UC ID, title, actor, domain, priority, and generation timestamp\n"
        "- Table of contents\n"
        "- 8 labelled sections: Overview, Conditions, Normal Course, Alternative Courses, "
        "Non-Functional Requirements, Information Requirements, Domain Entities, Open Issues\n"
        "- All tables with alternating row shading (#E8F0FE / white)\n"
        "- Header row shading: #0F3460 background, white bold text\n"
        "- Per-page header: 'ucgen · Use Case Document' on dark navy left / version on blue right\n"
        "- Per-page footer: '{UC-ID} — {Title} | Page N' with a blue top border\n"
        "- Branded colour palette: dark navy #1A1A2E, accent blue #4A90D9, mid navy #0F3460\n"
        "- All body text in Arial 9pt, section headings in Arial 12pt bold #0F3460\n"
        f"Save the completed file to: {docx_target}\n\n"
        "IMPORTANT: You have pre-approved permission to write files and execute "
        "Python scripts in this session. Do not ask for approval — execute immediately.\n"
        "Use python-docx. Write the script and run it without prompting the user."
    )

    message = body + instruction
    # Structure: <root>/use-cases/standalone/UC-XXXX/<file>.md
    cwd = md_path.parent.parent.parent
    cmd = "claude.cmd" if sys.platform == "win32" else "claude"

    console.print(f"\n[{PRIMARY}]Opening Claude Code to generate Word document...[/]")
    console.print(f"[{MUTED}]Target: {docx_target}[/]\n")

    _run_claude_with_message(cmd, message, cwd=cwd)

    if skip_exists_check:
        return

    if docx_target.exists():
        console.print(f"\n[{SUCCESS}]✓  Word document written (Claude):[/] {docx_target}\n")
    else:
        console.print(
            f"\n[{WARNING}]⚠  .docx not detected at expected path.[/]\n"
            f"[{MUTED}]Check Claude Code output above — the file may have been saved "
            f"elsewhere.[/]\n"
        )


def run_claude_flow(
    md_path: Path,
    console: Console,
    docx_already_written: bool = False,
) -> None:
    """Install check → auth check → run docx generation."""
    if not is_claude_installed():
        success = install_claude_code(console)
        if not success:
            return
        time.sleep(1)
        if not is_claude_installed():
            console.print(
                f"[{ERROR}]✗  Claude CLI still not found on PATH after install.[/] "
                f"[{MUTED}]Open a new terminal and re-run. Or run: "
                f"npm install -g @anthropic-ai/claude-code[/]\n"
            )
            return

    if not is_claude_authenticated():
        success = run_auth_flow(console)
        if not success:
            return

    run_claude_docx(md_path, console, skip_exists_check=docx_already_written)
