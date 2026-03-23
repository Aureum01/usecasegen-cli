"""CLI smoke tests."""

from __future__ import annotations

from typer.testing import CliRunner

from ucgen.cli import app

runner = CliRunner()


def test_version_command_runs() -> None:
    """version command exits successfully."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
