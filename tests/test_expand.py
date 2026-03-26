"""Tests for Stage 0 discovery and --expand flow."""

from __future__ import annotations

import asyncio
import json

from typer.testing import CliRunner

from ucgen.cli import app
from ucgen.config import Config
from ucgen.errors import UCGenError
from ucgen.generator import _run_discovery
from ucgen.schema import DiscoveredUseCase, DiscoveryResult

runner = CliRunner()


def test_run_discovery_success(temp_config, mock_provider_factory) -> None:
    """Discovery parses model JSON and validates it."""
    payload = json.dumps(
        {
            "system_summary": "Farm CCTV monitoring system.",
            "use_cases": [
                {
                    "title": "Monitor live camera feed",
                    "actor": "Farmer",
                    "goal_level": "user-goal",
                    "priority": "high",
                }
            ],
        }
    )
    provider = mock_provider_factory([payload])
    result = asyncio.run(_run_discovery("farm cctv app", temp_config, provider))
    assert isinstance(result, DiscoveryResult)
    assert result.use_cases
    assert result.use_cases[0].title == "Monitor live camera feed"


def test_run_discovery_raises_after_two_failures(temp_config, mock_provider_factory) -> None:
    """Discovery raises UCGenError after two parse failures."""
    provider = mock_provider_factory(["not json", "still not json"])
    try:
        asyncio.run(_run_discovery("bad idea", temp_config, provider))
    except UCGenError as exc:
        assert "Stage 0 discovery failed after 2 attempts" in str(exc)
    else:
        raise AssertionError("Expected UCGenError")


def test_expand_decline_exits_without_generation(monkeypatch, tmp_path) -> None:
    """Declining expand confirmation exits cleanly with no files."""
    config = Config(output_dir=tmp_path / "out")

    class _Provider:
        @property
        def name(self) -> str:
            return "mock"

        def is_available(self) -> bool:
            return True

    monkeypatch.setattr("ucgen.cli.load", lambda: config)
    monkeypatch.setattr("ucgen.cli.ProviderFactory.create", lambda _: _Provider())
    async def _fake_discovery(*_args, **_kwargs) -> DiscoveryResult:
        return DiscoveryResult(
            system_summary="Farm CCTV",
            use_cases=[
                DiscoveredUseCase(
                    title="Monitor live camera feed",
                    actor="Farmer",
                    goal_level="user-goal",
                    priority="high",
                )
            ],
        )

    monkeypatch.setattr("ucgen.cli.run_discovery", _fake_discovery)
    monkeypatch.setattr("ucgen.cli.Confirm.ask", lambda *_args, **_kwargs: False)

    result = runner.invoke(app, ["generate", "farm cctv app", "--expand"])
    assert result.exit_code == 0
    assert "Cancelled. No files written." in result.stdout

