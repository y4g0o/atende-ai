# atende-AI

> **Turn operational knowledge into auditable AI skills.**
>
> Every time you solve a problem the same way twice, that's a skill waiting to be written.

---

## What it does

`atende-AI` is a generic engine that reads a YAML file describing how your team handles requests, then orchestrates an AI assistant to execute those resolutions safely — with mandatory human approval at every critical step.

**Core principle: domain content is YAML, flow is code.**

The engine implements a fixed, tamper-proof flow:

```
read thread → classify → lookup IDs → validate blockers
    → ⚠️ PAUSE 2 (approval) → execute → audit log
    → ⚠️ PAUSE 3 (message approval) → reply
```

Each **area** (support channel, backoffice, finance, etc.) defines only its domain content in YAML: ticket types, lookup queries, allowed tools, response templates. The engine remains unchanged.

---

## Invariants — YAML cannot disable these

| Guard | Effect |
|---|---|
| **Pause 2** (execution approval) | Always shown before any operation |
| **Pause 3** (message approval) | Exact message shown for approval before sending |
| **Tool whitelist** | `tools_allowed[]` in YAML; engine rejects unlisted tools at load time |
| **Audit log** | Every execution writes to BigQuery; engine fails early if audit is unavailable |
| **PII redaction** | Mandatory before any external LLM call that processes channel history |
| **Test space isolation** | Engine blocks `send_message` to production space during tests |
| **Runtime operator email** | Never persisted in YAML; captured per session as `{{ operator_email }}` |

---

## Quick start

```bash
git clone https://github.com/y4g0o/atende-ai.git ~/atende-ai
cd ~/atende-ai

# Install engine skills into AI CLI (~/.claude/commands/)
bash scripts/install.sh

# Option A — guided wizard (recommended)
/atende-criar

# Option B — copy the example area and fill it in
cp areas/helpdesk-saas.yaml areas/my-area.yaml
# edit my-area.yaml following the "=== FILL THESE VALUES ===" header
bash scripts/validate.sh areas/my-area.yaml
```

Read `GETTING-STARTED.md` for the complete guide.

---

## Structure

```
atende-ai/
├── engine/             # AI CLI skills (atende, atende-criar, atende-refinar, ...)
├── areas/              # Area YAMLs (helpdesk-saas.yaml to get started)
├── schemas/            # JSON Schema (atende.v1.json)
├── lib/                # Pure Python: pii_redactor, threshold_cluster, audit_logger
├── scripts/            # install.sh, validate.sh, check-no-pii.sh
├── docs/               # Architecture, schema reference, governance, lessons learned
└── examples/           # minimal-area.yaml (bare minimum reference)
```

---

## How a skill is born

1. **Map** — list the 3-5 most common request types (guessed or from channel history)
2. **Search** — validate against real past cases via `search_messages` (cheaper than interviews)
3. **Interview** — ask targeted questions only where the search reveals gaps
4. **Refine** — each real execution feeds back into the YAML via `/atende-refinar`

See `docs/08-methodology-area-discovery.md` for the full playbook.

---

## License

MIT — see `LICENSE`.
