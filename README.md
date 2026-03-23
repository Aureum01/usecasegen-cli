# ucgen

CLI tool that generates structured Cockburn-style use case documents from natural language using local or cloud LLMs.

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![License](https://img.shields.io/badge/license-MIT-0a0a0a?labelColor=0a0a0a)
![Version](https://img.shields.io/badge/version-0.1.0-2563eb)
![PyPI](https://img.shields.io/badge/PyPI-coming%20soon-6b7280)

## What it does

`ucgen` closes the gap between a rough feature idea and a structured use case specification that developers can review and implement. It runs a staged generation pipeline that produces consistent Cockburn-style sections instead of free-form prose. Output is written as Markdown documents with frontmatter plus self-contained HTML reports for review and sharing.

## Quick start

### With Ollama (free, local)

```bash
pip install ucgen
ollama pull qwen3:8b
ucgen generate "warehouse picker scans barcode to confirm item before adding to shipment"
```

### With Anthropic

```bash
pip install ucgen
export ANTHROPIC_API_KEY=sk-ant-...   # Windows: $env:ANTHROPIC_API_KEY=...
ucgen generate "warehouse picker scans barcode to confirm item before adding to shipment" --provider anthropic --model claude-sonnet-4-6
```

## Troubleshooting

- **Provider unavailable:** run `ucgen version` to check provider status.
- **Anthropic auth errors:** confirm `ANTHROPIC_API_KEY` is set in the same shell session.
- **Ollama connection errors:** start Ollama with `ollama serve` and verify model exists with `ollama list`.
- **No report output:** ensure generation completed and rerun with `--report`, or run `ucgen report`.

## Output

For the warehouse picker example, `ucgen` creates a per-use-case folder with Markdown, JSON, and optional single-report HTML.

```text
use-cases/
  report.html
  standalone/
    UC-2026-0049-warehouse-picker-scans-barcode/
      UC-2026-0049-warehouse-picker-scans-barcode.md
      UC-2026-0049-warehouse-picker-scans-barcode.json
      report.html
```

- `*.md`: human-readable use case document
- `*.json`: full structured `UseCaseDocument`
- `report.html`: self-contained HTML report (single-use-case when generated with `--report`)

## Configuration

Initialize local config:

```bash
ucgen init
```

Example `.ucgenrc.toml`:

```toml
[defaults]
provider = "ollama"
model = "qwen3:8b"
output_dir = "./use-cases"
template = "default"
temperature = 0.3
max_tokens = 4000
```

## Commands

| Command | Description |
|---|---|
| `ucgen generate "<idea>"` | Generate one use case |
| `ucgen generate "<idea>" --report` | Generate one use case and a single report in the UC folder |
| `ucgen batch <ideas.txt>` | Generate from a text/yaml batch file |
| `ucgen report` | Build portfolio report from all JSON docs in `output_dir` |
| `ucgen run` | Generate from `ucgen.yaml` project file |
| `ucgen status` | Show project generation status |
| `ucgen validate <path>` | Validate generated markdown files |
| `ucgen init` | Create `.ucgenrc.toml` |
| `ucgen init-project "<name>"` | Scaffold `ucgen.yaml` |
| `ucgen log` | Record a mistake in memory |
| `ucgen gc` | Archive/graduate memory entries |
| `ucgen version` | Show version and provider availability |

## License

MIT — see [LICENSE](LICENSE).
