"""Allow running the CLI as ``python -m ucgen``."""

from __future__ import annotations

from ucgen.cli import app


def main() -> None:
    """Invoke the Typer application."""
    app()


if __name__ == "__main__":
    main()
