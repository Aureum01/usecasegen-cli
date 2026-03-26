"""Tests for Claude Code integration (mocked subprocess / prompts)."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from ucgen import claude_integration


def test_is_claude_installed_respects_which(monkeypatch: pytest.MonkeyPatch) -> None:
    """PATH lookup uses claude or claude.cmd depending on platform."""
    seen: list[str] = []

    def fake_which(cmd: str) -> str | None:
        seen.append(cmd)
        return "/fake/claude" if cmd in ("claude", "claude.cmd") else None

    monkeypatch.setattr(claude_integration.shutil, "which", fake_which)
    assert claude_integration.is_claude_installed() is True
    assert seen


def test_run_claude_flow_runs_docx_when_installed_and_authed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When CLI exists and auth probe passes, docx step invokes subprocess.run."""
    md = tmp_path / "uc.md"
    md.write_text("# Title\n", encoding="utf-8")
    console = Console(file=StringIO())

    monkeypatch.setattr(claude_integration, "is_claude_installed", lambda: True)
    monkeypatch.setattr(claude_integration, "is_claude_authenticated", lambda: True)

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
        calls.append(cmd)
        return MagicMock(returncode=0)

    monkeypatch.setattr(claude_integration.subprocess, "run", fake_run)

    claude_integration.run_claude_flow(md, console)

    assert len(calls) >= 1
    assert any("claude" in c[0].lower() or c[0].endswith("claude.cmd") for c in calls)


def test_run_claude_flow_stops_when_install_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If install is declined, flow returns without calling docx."""
    md = tmp_path / "uc.md"
    md.write_text("# x", encoding="utf-8")
    console = Console(file=StringIO())

    monkeypatch.setattr(claude_integration, "is_claude_installed", lambda: False)
    monkeypatch.setattr(claude_integration, "is_npm_installed", lambda: True)

    with patch.object(claude_integration.Confirm, "ask", return_value=False):
        monkeypatch.setattr(claude_integration.subprocess, "run", MagicMock())

        claude_integration.run_claude_flow(md, console)

    claude_integration.subprocess.run.assert_not_called()


def test_run_claude_flow_auth_prompt_declined(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unauthenticated user declining auth does not run docx subprocess."""
    md = tmp_path / "uc.md"
    md.write_text("# x", encoding="utf-8")
    console = Console(file=StringIO())

    monkeypatch.setattr(claude_integration, "is_claude_installed", lambda: True)
    monkeypatch.setattr(claude_integration, "is_claude_authenticated", lambda: False)

    with patch.object(claude_integration.Confirm, "ask", return_value=False):
        mock_run = MagicMock()
        monkeypatch.setattr(claude_integration.subprocess, "run", mock_run)

        claude_integration.run_claude_flow(md, console)

    mock_run.assert_not_called()
