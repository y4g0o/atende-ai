🇺🇸 English · [🇧🇷 Português](README.pt-BR.md)

# atende-AI

> **Turn operational knowledge into auditable AI skills.**
>
> Every time you solve a problem the same way twice, that's a skill waiting to be written.

![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Python 3](https://img.shields.io/badge/python-3-blue.svg)
![Shell: Bash](https://img.shields.io/badge/shell-bash-lightgrey.svg)

`atende-AI` is a generic helpdesk engine for AI CLIs: your team's support procedures live in **YAML files**, and the engine executes them with **mandatory human approval**, a **tool allowlist**, an **audit log** and **PII redaction**.

**Core principle: domain content is YAML, flow is code.**

---

## 💡 Why

Support teams solve the same requests over and over, and that knowledge usually lives in people's heads or in chat history. Letting an AI act on it is risky unless every step is explicit, reviewable and logged.

`atende-AI` makes the procedure the artifact: a YAML file you can read, diff, review via `CODEOWNERS` and validate against a JSON Schema. The engine never lets that YAML switch off the safety guards.

## ✨ Key features

- **Procedures as YAML "areas"** — ticket types, keywords, lookup queries, blockers, allowed tools and response templates per area, validated by [`schemas/atende.v1.json`](schemas/atende.v1.json).
- **Human in the loop by design** — the engine always pauses for approval before executing an operation (Pause 2) and before sending a reply (Pause 3).
- **Strict tool allowlist** — `tools_allowed[]` is checked at load time; any other tool is rejected.
- **Audit log** — every execution is recorded with a payload hash, operator, area, type and result ([`lib/audit_logger.py`](lib/audit_logger.py)).
- **PII redaction** — e-mails, IDs, URLs, CPF, phones and names are replaced before channel history reaches an external LLM ([`lib/pii_redactor.py`](lib/pii_redactor.py)).
- **Channel-agnostic** — Google Chat, Gmail (draft-only) and WhatsApp (via your provider's MCP) through `channel.tools.*` ([`docs/05-channels.md`](docs/05-channels.md)).
- **Guided creation and continuous learning** — `/atende-criar` wizard, `/atende-varredura` channel scan, `/atende-refinar` refinement from the audit log.
- **Destructive operations need a literal confirmation phrase**, not just "yes" ([`docs/04-governance.md`](docs/04-governance.md)).

---

## 🚀 Quickstart

**Prerequisites:** an AI CLI that loads commands from `~/.claude/commands/` (that is where `scripts/install.sh` links the engine), Google Chat / BigQuery MCPs configured (see [`GETTING-STARTED.md`](GETTING-STARTED.md)), and for validation either `ajv-cli` or `python3` with `jsonschema` + `pyyaml`.

```bash
# The engine files reference ~/atende-ai/, so clone into that folder
git clone https://github.com/y4g0o/atende-ai.git ~/atende-ai
cd ~/atende-ai

# Validation dependencies (pick one)
pip install jsonschema pyyaml      # or: npm install -g ajv-cli

# Install engine skills into the AI CLI (~/.claude/commands/ and ~/.claude/agents/)
bash scripts/install.sh

# Option A — guided wizard (recommended), inside the AI CLI
/atende-criar

# Option B — copy the example area and fill it in
cp areas/helpdesk-saas.yaml areas/my-area.yaml
# edit my-area.yaml following the "=== PREENCHA ESTES VALORES ===" header
bash scripts/validate.sh areas/my-area.yaml

# Resolve one real ticket, inside the AI CLI
/atende my-area https://chat.google.com/room/YOUR_SPACE/THREAD_ID/...
```

Try it without any credentials (pure local checks):

```bash
bash scripts/validate.sh                       # validates every areas/*.yaml against the schema
bash scripts/validate.sh examples/minimal-area.yaml
bash scripts/check-no-pii.sh                   # lint for forbidden tokens (your real patterns go in .pii-patterns.local, gitignored)
python3 -m unittest discover -s tests          # test suite (needs pyyaml + jsonschema)
python3 lib/threshold_cluster.py               # demo of the Jaccard clustering used in history analysis
```

Read [`GETTING-STARTED.md`](GETTING-STARTED.md) for the complete guide (in Portuguese), including the placeholder checklist.

---

## ⚙️ How it works

The engine implements a fixed, tamper-proof flow:

```
read thread → classify → lookup IDs → validate blockers
    → ⚠️ PAUSE 2 (approval) → execute → audit log
    → ⚠️ PAUSE 3 (message approval) → reply
```

Each **area** (support channel, backoffice, finance, etc.) defines only its domain content in YAML: ticket types, lookup queries, allowed tools, response templates. The engine remains unchanged. A cheap classifier subagent ([`engine/atende-classifier.md`](engine/atende-classifier.md)) reads the thread and returns JSON, so the main engine doesn't spend context on reading. An optional Pause 1 asks whether to search channel history when there are open questions.

### Invariants — YAML cannot disable these

| Guard | Effect |
|---|---|
| **Pause 2** (execution approval) | Always shown before any operation |
| **Pause 3** (message approval) | Exact message shown for approval before sending |
| **Tool whitelist** | `tools_allowed[]` in YAML; engine rejects unlisted tools at load time |
| **Audit log** | Every execution writes to BigQuery (local JSONL fallback in `lib/audit_logger.py`); engine fails early if audit is unavailable |
| **PII redaction** | Mandatory before any external LLM call that processes channel history |
| **Test space isolation** | Engine blocks `send_message` to production space during tests |
| **Runtime operator email** | Never persisted in YAML; captured per session as `{{ operator_email }}` |

More detail: [architecture](docs/00-architecture.md) · [engine flow](docs/02-engine-flow.md) · [governance](docs/04-governance.md).

### How a skill is born

1. **Map** — list the 3-5 most common request types (guessed or from channel history)
2. **Search** — validate against real past cases via `search_messages` (cheaper than interviews)
3. **Interview** — ask targeted questions only where the search reveals gaps
4. **Refine** — each real execution feeds back into the YAML via `/atende-refinar`

See [`docs/08-methodology-area-discovery.md`](docs/08-methodology-area-discovery.md) for the full playbook.

### Structure

```
atende-ai/
├── engine/             # AI CLI skills (atende, atende-criar, atende-refinar, atende-varredura, atende-sync, atende-classifier)
├── areas/              # Area YAMLs (helpdesk-saas.yaml to get started — fictional SaaS domain, 8 types)
├── schemas/            # JSON Schema (atende.v1.json)
├── lib/                # Pure Python: pii_redactor, threshold_cluster, audit_logger
├── scripts/            # install.sh, validate.sh, check-no-pii.sh
├── tests/              # unittest: libs, scripts and engine↔schema↔docs invariants
├── docs/               # Architecture, schema reference, governance, channels, glossary, lessons learned
├── examples/           # minimal-area.yaml (bare minimum reference) + channels/ presets (Google Chat, Gmail, WhatsApp)
└── globals.yaml        # Rules shared by every area (test channel, conventions, absolute rules)
```

---

## 🚧 Status & limitations

- **Early release** — a sanitized public version of a tool used on real support channels (see [lessons learned](docs/07-licoes.md)).
- **The engine is a set of prompt/skill files** (`engine/*.md`) run by an AI CLI, not a standalone service. `lib/` is pure Python with no external dependencies.
- **Bring your own MCPs** — operations go through your organization's MCP (`mcp__YOUR_ORG_MCP__*`); WhatsApp needs your provider's MCP. Audit destination must be a `bigquery://` URI (schema rule).
- **Languages:** response templates support `pt-BR` and `es` (schema enum).
- **RBAC is MVP-level** (`authorizations[]` in the YAML) and there is **no automatic rollback** of executed operations ([`docs/04-governance.md`](docs/04-governance.md)).
- **PII patterns are tuned to Brazilian formats** (CPF, CEP, `+55` phones) and use heuristics for names — adapt them to your data.
- **Test suite included (`tests/`), no CI yet.**
- **Most docs, engine prompts and code comments are in Portuguese**; this README and `CONTRIBUTING.md` are the English entry points.

## 🗺️ Roadmap

- [ ] RBAC in a separate `permissions.yaml`, inherited from `globals` ([`docs/04-governance.md`](docs/04-governance.md))
- [ ] Automated rollback by modeling an "inverse operation" per type ([`docs/04-governance.md`](docs/04-governance.md))
- [ ] New channel adapters (Slack, Teams, Telegram) following the checklist in [`docs/05-channels.md`](docs/05-channels.md)
- [x] Test suite for `lib/`, scripts and engine/schema invariants (`tests/`)
- [ ] CI running the tests + `validate.sh` + `check-no-pii.sh`
- [ ] English versions of `docs/` and `GETTING-STARTED.md`

## 🤝 Contributing

Contributions are welcome — new example areas, channel presets, tests and docs are the easiest ways in. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, validation, style, the PR flow and a list of **good first issues**.

## 📄 License

MIT — see [`LICENSE`](LICENSE). Created by **Yago Macambira** ([@y4g0o](https://github.com/y4g0o)).
