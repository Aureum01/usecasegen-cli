"""Startup banner for ucgen CLI."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ucgen import __version__
from ucgen.theme import DARK, MUTED, PRIMARY

BANNER_ART = """\
 ██╗   ██╗ ██████╗ ██████╗ ███████╗███╗   ██╗
 ██║   ██║██╔════╝██╔════╝ ██╔════╝████╗  ██║
 ██║   ██║██║     ██║  ███╗█████╗  ██╔██╗ ██║
 ██║   ██║██║     ██║   ██║██╔══╝  ██║╚██╗██║
 ╚██████╔╝╚██████╗╚██████╔╝███████╗██║ ╚████║
  ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝"""


def print_banner(console: Console) -> None:
    """Print the branded ucgen banner."""
    art = Text(BANNER_ART, style=f"bold {PRIMARY}")
    subtitle = Text(
        f"Use Case Generator  ·  v{__version__}  ·  Cockburn-style docs from natural language",
        style=MUTED,
    )
    panel = Panel(
        art + Text("\n") + subtitle,
        border_style=DARK,
        padding=(0, 2),
        expand=False,
    )
    console.print(panel)
    console.print()
