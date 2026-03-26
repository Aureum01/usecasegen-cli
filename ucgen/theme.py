"""Shared Rich colour tokens and console factory for terminal output."""

from __future__ import annotations

import os

from rich.console import Console

# Blue — main accent, spinners, progress
PRIMARY = "#4A90D9"
# Deep navy — panel borders, headers
DARK = "#1A1A2E"
# Mid navy — secondary accent
MID = "#0F3460"
# Green — success states
SUCCESS = "#22C55E"
# Amber — warnings, retries
WARNING = "#F59E0B"
# Red — errors, failures
ERROR = "#EF4444"
# Grey — metadata, timestamps, hints
MUTED = "#6B7280"
WHITE = "#FFFFFF"


def make_console(*, force_no_color: bool = False) -> Console:
    """Build a Rich console that respects NO_COLOR and dumb terminals."""
    no_color = bool(os.getenv("NO_COLOR")) or force_no_color
    dumb = os.getenv("TERM") == "dumb"
    disabled = no_color or dumb
    return Console(no_color=disabled, highlight=not disabled)
