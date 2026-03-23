<div align="center">

  <h1>usecasegen-cli</h1>

  <p>
    A new standard for system design use cases.<br/>
    Structured, agent-ready markdown documents generated from natural language.
  </p>

  <p>
    <a href="https://pypi.org/project/ucgen"><img src="https://img.shields.io/pypi/v/ucgen?color=0a0a0a&labelColor=0a0a0a" alt="PyPI"></a>
    <a href="https://pypi.org/project/ucgen"><img src="https://img.shields.io/pypi/pyversions/ucgen?color=0a0a0a&labelColor=0a0a0a" alt="Python"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-0a0a0a?labelColor=0a0a0a" alt="License"></a>
  </p>

  <p>
    <a href="#install">Install</a> ·
    <a href="#providers">Providers</a> ·
    <a href="#templates">Templates</a> ·
    <a href="#team-workflows">Team Workflows</a> ·
    <a href="#extending">Extending</a>
  </p>

</div>

---

## What it produces

Every generated document is a structured markdown file with YAML frontmatter
that any agent, CI pipeline, or documentation tool can parse and act on:
```yaml
---
uc_id: UC-2026-0001
title: Patient Books Appointment
actor: Patient
goal_level: user_goal
domain: healthcare
system_boundary: BookingService
stakeholders:
  - name: Patient
    interest: Reserve a slot without double-booking risk
  - name: Clinic
    interest: Maximize schedule utilization
nfr:
  - type: latency
    requirement: Slot confirmation under 2 seconds
---
```

Followed by a complete use case document: preconditions, normal course,
alternative courses, implied database entities, and open issues.

---

## Install
```bash
pip install ucgen
```

For team project files (`ucgen.yaml`):
```bash
pip install ucgen[project]
```

---

## Quick start
```bash
# Local model — free, private
ucgen "patient books appointment at dental clinic"

# Groq — free cloud, fast
export GROQ_API_KEY=your_key
ucgen "patient books appointment" --provider groq

# Anthropic Claude
export ANTHROPIC_API_KEY=your_key
ucgen "patient books appointment" --provider anthropic --model claude-sonnet-4-6
```

Output file: `./use-cases/UC-2026-0001-patient-books-appointment.md`

---

## Providers

| Provider | Setup | Cost | Quality |
|----------|-------|------|---------|
| **Ollama** | `ollama serve` | Free | Good |
| **Groq** | `GROQ_API_KEY` | Free tier | Excellent |
| **Anthropic** | `ANTHROPIC_API_KEY` | ~$0.003/doc | Best |
| **OpenAI** | `OPENAI_API_KEY` | ~$0.001/doc | Excellent |
| **Custom** | `custom_base_url` in config | Varies | — |

Check what's available:
```bash
ucgen version
```

---

## Configuration

Create a config file in your project root:
```bash
ucgen init
```

This writes `.ucgenrc.toml`:
```toml
[defaults]
provider = "ollama"
model = "mistral"
output_dir = "./use-cases"
template = "default"

[providers]
ollama_base_url = "http://localhost:11434"

[hooks]
on_generate = "git add ."
```

---

## Templates

| Template | Use for |
|----------|---------|
| `default` | Standard use case with all sections |
| `minimal` | Quick capture — actor, trigger, normal course |
| `api` | API-endpoint focused with request/response tables |
| `cockburn-full` | Full Cockburn format with stakeholders and guarantees |
| `enterprise` | NFRs, scale hints, state machine, service boundary |
```bash
ucgen "supplier invoice approval" --template enterprise
```

---

## Generating Multiple Use Cases

There are three ways to generate multiple use cases depending on your
situation.

### Option 1 — Batch file (quickest for ad-hoc generation)

Create a plain text file with one idea per line:
```
# ideas.txt
patient books appointment
patient cancels appointment
receptionist checks in patient
admin views daily schedule
patient receives reminder
```

Run batch generation:
```bash
ucgen batch ideas.txt
```

All use cases are generated sequentially and written to your
`output_dir`. Lines starting with `#` and blank lines are skipped.

---

### Option 2 — Project file (recommended for real projects)

Create a `ucgen.yaml` in your project root:
```bash
ucgen init-project "MyProject" --domain healthcare
```

Edit `ucgen.yaml` to define your use cases:
```yaml
project:
  name: DentalClinic
  domain: healthcare

defaults:
  provider: ollama
  model: mistral
  output_dir: ./use-cases

actors:
  - name: Patient
    type: human
  - name: Receptionist
    type: human

use_cases:
  - id: UC-001
    title: Book Appointment
    actor: Patient
    goal: Reserve an available slot with a preferred dentist
    priority: high
    tags: [booking, core]

  - id: UC-002
    title: Cancel Appointment
    actor: Patient
    goal: Cancel an existing confirmed appointment
    priority: high
    tags: [booking, core]
```

Generate all pending use cases:
```bash
ucgen run
```

Generate by ID or tag:
```bash
ucgen run --id UC-001
ucgen run --tag core
```

Check status at any time:
```bash
ucgen status
```

Generated files are organised into a project subfolder:
```
use-cases/
  dentalclinic/
    UC-001-book-appointment.md
    UC-002-cancel-appointment.md
```

---

### Option 3 — Generate a report from all use cases

Once you have multiple use cases generated, build a single HTML report:
```bash
ucgen report --dir use-cases/dentalclinic --output use-cases/dentalclinic/report.html --title "DentalClinic Use Cases"
```

Open `report.html` in any browser. No server required — fully
self-contained single file with navigation, tables, and all sections.

---

## Team workflows

For teams, define all use cases in a single `ucgen.yaml` project file:
```bash
ucgen init-project MySystem --domain healthcare
```

This creates `ucgen.yaml`:
```yaml
project:
  name: MySystem
  domain: healthcare

defaults:
  provider: groq
  template: cockburn-full
  output_dir: ./docs/use-cases

actors:
  - name: Patient
    type: human
  - name: Receptionist
    type: human

use_cases:
  - id: UC-001
    title: Patient Books Appointment
    actor: Patient
    goal: Reserve an available slot
    priority: high
    status: pending
```

Then generate all pending use cases:
```bash
ucgen run          # all pending
ucgen run --id UC-001   # specific use case
ucgen run --tag core    # by tag
ucgen status            # check what's generated
```

### CI integration
```yaml
# .github/workflows/use-cases.yml
name: Validate Use Cases
on:
  pull_request:
    paths: ['docs/use-cases/**', 'ucgen.yaml']
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ucgen
      - run: ucgen validate docs/use-cases/
```

---

## Extending

### Custom provider

Implement `BaseProvider` from `ucgen.providers.base`:
```python
from ucgen.providers.base import BaseProvider, GenerationResult

class MyProvider(BaseProvider):
    async def generate(self, system, user, **kwargs) -> GenerationResult:
        ...
    def is_available(self) -> bool:
        ...
```

### Custom template

Place any `.md.j2` Jinja2 file in a directory and point to it:
```toml
# .ucgenrc.toml
[defaults]
template = "C:/templates/my-template.md.j2"
```

Available template variables: `intake`, `sections`, `entities`,
`config`, `generated_at`, `generator_version`.

---

## Commands

| Command | Description |
|---------|-------------|
| `ucgen generate <idea>` | Generate a single use case |
| `ucgen run` | Generate from `ucgen.yaml` |
| `ucgen status` | Show project generation status |
| `ucgen batch <file>` | Batch generate from file |
| `ucgen validate <path>` | Validate .md files against schema |
| `ucgen init` | Create `.ucgenrc.toml` |
| `ucgen init-project <name>` | Scaffold `ucgen.yaml` |
| `ucgen log` | Log a correction to memory |
| `ucgen version` | Show version and provider status |

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
  <sub>Built by <a href="https://github.com/Aureum01">Aureum01</a></sub>
</div>
