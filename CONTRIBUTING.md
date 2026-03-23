## Setup

Requires Python 3.11+ and uv.

pip install uv
uv sync --extra dev
uv run pytest tests/ -v

## Linting and type checking

python -m ruff check ucgen/
python -m ruff format --check ucgen/
python -m mypy ucgen/ --ignore-missing-imports

## Local models (Ollama)

Recommended models:
- qwen3:8b   — better structured JSON output, recommended
- mistral     — lighter, faster, occasional type mismatches

ollama pull qwen3:8b
ollama pull mistral
