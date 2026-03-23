## Setup

Requires Python 3.11+ and uv.

pip install uv
uv sync --extra dev
uv run pytest tests/ -v

## Linting and type checking

python -m ruff check ucgen/
python -m ruff format --check ucgen/
python -m mypy ucgen/ --ignore-missing-imports

## Providers for local testing

Ollama (free, local): ollama serve
Groq (free, fast): set GROQ_API_KEY
