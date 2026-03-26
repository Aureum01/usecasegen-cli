> Type your feature idea in plain English. Get a professional use case document back.

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![License](https://img.shields.io/badge/license-MIT-0a0a0a?labelColor=0a0a0a)
[![PyPI](https://img.shields.io/pypi/v/ucgen)](https://pypi.org/project/ucgen/)

`ucgen` is a Python CLI that generates Cockburn-style use case documents from natural language using Ollama or hosted providers.

## Install

```bash
pip install ucgen
```

## Quick Start

### Local (Ollama)

```bash
ollama pull qwen3:8b
ucgen generate "warehouse picker scans barcode before adding item to shipment"
```

### Cloud (Anthropic)

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Windows: $env:ANTHROPIC_API_KEY=...
ucgen generate "warehouse picker scans barcode before adding item to shipment" --provider anthropic --model claude-sonnet-4-6
```

## Core Concepts

- **One idea -> one use case** by default (`ucgen generate`).
- **`--expand`** asks AI to discover multiple use cases first, then generates them sequentially.
- Output is always grounded in a fixed 4-stage generation pipeline.

## What ucgen Writes

A successful run creates a standalone folder per use case:

```text
use-cases/
  standalone/
    UC-2026-0049-warehouse-picker-scans-barcode/
      UC-2026-0049-warehouse-picker-scans-barcode.md
      UC-2026-0049-warehouse-picker-scans-barcode.json
      report.html                # optional: with --report
      UC-2026-0049-... .docx     # optional: with --docx / --claude
```

- `.md`: human-readable use case document
- `.json`: structured `UseCaseDocument` output
- `.docx`: optional Word output
- `report.html`: optional HTML report

## Word Document Generation

You can generate Word documents in two ways after markdown is written:

### Native `python-docx` export

```bash
ucgen generate "register a new patient at reception" --docx
```

### Claude Code terminal flow

```bash
ucgen generate "register a new patient at reception" --claude
```

This launches Claude Code to generate a `.docx` from the produced markdown.

Requirements:

```bash
npm install -g @anthropic-ai/claude-code
```

Both flags can be combined. `--docx` runs first, then `--claude`:

```bash
ucgen generate "register a new patient at reception" --docx --claude
```

## Multi-Use-Case Discovery (`--expand`)

Use this when your idea describes a whole product/workflow, not just one use case:

```bash
ucgen generate "A CCTV desktop app monitor for a farm" --expand
```

Flow:

1. AI proposes all relevant use cases in a table
2. You confirm generation
3. ucgen runs the full 4-stage pipeline for each discovered use case
4. Final panel summarizes generated IDs/titles

## Useful Flags

- `--report`: write a single-use-case HTML report in the output folder
- `--quiet`: print only generated markdown path(s), ideal for CI/pipes
- `--no-color`: disable ANSI color output
- `--provider`, `--model`: override provider/model per run
- `--stdin`: read idea from stdin instead of CLI argument

## Example Output Excerpt

<details>
<summary>Register New Patient (UC-2026-0049)</summary>

```markdown
---
uc_id: UC-2026-0049
title: Register New Patient
actor: Receptionist
goal_level: user_goal
---

## Preconditions
- Patient identification documents are available
- Registration desk is staffed

## Normal Course
| Step | Actor | Action | System Response |
|------|-------|--------|-----------------|
| 1 | Receptionist | Capture demographics | Validate required fields |
| 2 | Receptionist | Submit registration | Create patient record and assign MRN |

## Success Guarantee
The patient has an active record and can be scheduled for care.
```

</details>

## Configuration

Create local config:

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

## Command Reference

### `ucgen generate`

Generate one use case from a plain-English idea.

```bash
ucgen generate "<idea>"
```

Common options:

- `--expand`: discover and generate multiple use cases
- `--report`: generate single-use-case HTML report
- `--docx`: export native Word file via python-docx
- `--claude`: run Claude Code Word generation flow
- `--quiet`: output path(s) only
- `--provider`, `--model`: provider/model override
- `--stdin`: read idea from stdin
- `--debug`: persist debug artifacts on parse failures

### `ucgen batch`

Generate multiple use cases from a `.txt` file (one idea per line) or `.yaml` list.

```bash
ucgen batch ideas.txt
ucgen batch ideas.yaml --report
```

### `ucgen run`

Generate pending use cases from a `ucgen.yaml` project file.

```bash
ucgen run
ucgen run --id UC-001
ucgen run --tag booking
```

### `ucgen status`

Show generation status for use cases in a `ucgen.yaml` project.

```bash
ucgen status
```

### `ucgen report`

Build a portfolio HTML report from all generated JSON files.

```bash
ucgen report
ucgen report --output ./use-cases/report.html --open
```

### `ucgen validate`

Validate generated markdown files against expected structure.

```bash
ucgen validate ./use-cases/standalone
```

### `ucgen init`

Create a `.ucgenrc.toml` config in the current directory.

```bash
ucgen init
```

### `ucgen init-project`

Scaffold a new `ucgen.yaml` project definition.

```bash
ucgen init-project "Farm CCTV"
```

### `ucgen log`

Log a mistake/correction entry to ucgen memory.

```bash
ucgen log --quick "Used wrong provider default in CLI output"
```

### `ucgen gc`

Archive or graduate memory entries based on recurrence/staleness rules.

```bash
ucgen gc
ucgen gc --dry-run
```

### `ucgen version`

Print version and provider availability checks.

```bash
ucgen version
```

## Troubleshooting

**Ollama not reachable**  
Run `ollama serve`, then verify with `ollama list`.

**Claude Code not found**  
Install with `npm install -g @anthropic-ai/claude-code`.

**python-docx missing**  
Install with `pip install python-docx`.

**Stage 2 retry message**  
Expected with some models (for example Mistral). Retry auto-corrects structure.

**Slow generation**  
Try `--provider groq` for faster cloud inference.

## License

MIT — see [LICENSE](LICENSE).
