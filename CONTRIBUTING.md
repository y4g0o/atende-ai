# Contributing to atende-AI

🇺🇸 [English](#-english) · 🇧🇷 [Português](#-português)

---

## 🇺🇸 English

Thanks for your interest! atende-AI is small on purpose: the engine is a few Markdown skill files, the domain lives in YAML and the helpers in `lib/` are pure Python. That makes it easy to contribute an example, a preset, a test or a doc fix.

### Setup

```bash
git clone https://github.com/y4g0o/atende-ai.git ~/atende-ai   # engine files reference ~/atende-ai/
cd ~/atende-ai
pip install jsonschema pyyaml        # or: npm install -g ajv-cli
```

You only need an AI CLI and MCPs (Google Chat, Gmail, BigQuery, your operations MCP) if you want to run the engine end to end. Schema, scripts and `lib/` work fully offline.

### Tests and validation

Run these before opening a PR:

```bash
bash scripts/validate.sh                        # every areas/*.yaml against schemas/atende.v1.json
bash scripts/validate.sh path/to/your.yaml      # one specific file (e.g. examples/minimal-area.yaml)
bash scripts/check-no-pii.sh                    # no forbidden tokens / real data in the kit
python3 lib/threshold_cluster.py                # clustering demo still runs
```

There is no automated test suite yet — adding one is a good first issue (see below).

### Style

- **Never commit real data**: no real e-mails, user IDs, space IDs, project IDs, bucket names, internal URLs or people's names. Use the existing placeholders (`REPLACE_*`, `users/100000000000000000001`, `fulano@empresa.com`). `areas/*.local.yaml` is git-ignored for your real configs.
- **Keep the invariants**: changes must not allow YAML to disable Pause 2, Pause 3, the tool allowlist, the audit log, PII redaction or test-channel isolation.
- **Engine stays channel-agnostic**: use `channel.tools.*`, never a hard-coded provider tool in the flow steps ([`docs/00-architecture.md`](docs/00-architecture.md)).
- **YAML**: 2-space indentation, `kebab-case` area names, `schema: atende.v1` at the top, validated by `scripts/validate.sh`.
- **Python** (`lib/`): standard library only, type hints and docstrings like the existing modules.
- **Shell** (`scripts/`): `bash` with `set -euo pipefail`.
- Existing docs and prompts are in Portuguese; contributions in English or Portuguese are both welcome.

### PR flow

1. Open an issue (or comment on an existing one) describing what you want to change.
2. Fork and create a branch: `feat/...`, `fix/...` or `docs/...`.
3. Keep the PR focused; run the validation commands above.
4. Describe what changed and how you checked it. If you touched `engine/`, `schemas/`, `globals.yaml` or `lib/`, explain the impact on the invariants.
5. `CODEOWNERS` requests review automatically.

### 🌱 Good first issues

1. **Fix field-name drift in the docs.** The schema uses `channel.source_production` / `channel.source_test` and `globals.yaml` uses `channel_test.source_test`, but some docs still say `chat.space_production`, `chat.space_test` and `chat_test.space_test`: `GETTING-STARTED.md` (placeholder checklist), `docs/01-yaml-schema.md` (example and required-fields table), `docs/03-creating-a-new-area.md` (minimum checklist) and `docs/08-methodology-area-discovery.md` (pseudocode).
2. **Add unit tests for `lib/`.** Suggested start: a `tests/` folder with tests for `lib/pii_redactor.py` (the docstring example, idempotence on already-redacted text, ordering of patterns) and `_hash_payload` in `lib/audit_logger.py` (`None` → `""` vs `{}` → hash).
3. **Investigate the clustering demo.** `python3 lib/threshold_cluster.py` currently prints `De 12 amostras → 12 clusters` at `threshold=0.35`, so no similar tickets are grouped. Tune the demo threshold or the tokenization in `lib/threshold_cluster.py` and add a test that locks the expected grouping.
4. **New example area.** Add a small, fictional area (e.g. `examples/backoffice-area.yaml` or an e-mail-based area using `examples/channels/email-gmail.yaml`) that passes `bash scripts/validate.sh <file>`.
5. **CI workflow.** Add `.github/workflows/validate.yml` that installs `jsonschema` + `pyyaml` and runs `scripts/validate.sh`, `scripts/validate.sh examples/minimal-area.yaml` and `scripts/check-no-pii.sh`.
6. **English docs.** Translate `docs/06-glossary.md` (short) or `GETTING-STARTED.md` to English as `*.en.md` and link them from the README.

---

## 🇧🇷 Português

Obrigado pelo interesse! O atende-AI é pequeno de propósito: o engine são alguns arquivos de skill em Markdown, o domínio fica em YAML e os utilitários de `lib/` são Python puro. Isso facilita contribuir com um exemplo, um preset, um teste ou uma correção de doc.

### Setup

```bash
git clone https://github.com/y4g0o/atende-ai.git ~/atende-ai   # os arquivos do engine referenciam ~/atende-ai/
cd ~/atende-ai
pip install jsonschema pyyaml        # ou: npm install -g ajv-cli
```

Você só precisa de um AI CLI e de MCPs (Google Chat, Gmail, BigQuery, o MCP de operações) para rodar o engine de ponta a ponta. Schema, scripts e `lib/` funcionam totalmente offline.

### Testes e validação

Rode antes de abrir um PR:

```bash
bash scripts/validate.sh                        # todos os areas/*.yaml contra schemas/atende.v1.json
bash scripts/validate.sh caminho/do/seu.yaml    # um arquivo específico (ex.: examples/minimal-area.yaml)
bash scripts/check-no-pii.sh                    # nenhum token proibido / dado real no kit
python3 lib/threshold_cluster.py                # a demo de clustering continua rodando
```

Ainda não existe suíte de testes automatizada — criar uma é um good first issue (veja abaixo).

### Estilo

- **Nunca commite dados reais**: nada de e-mails, user IDs, space IDs, project IDs, buckets, URLs internas ou nomes de pessoas reais. Use os placeholders existentes (`REPLACE_*`, `users/100000000000000000001`, `fulano@empresa.com`). `areas/*.local.yaml` é ignorado pelo git para suas configurações reais.
- **Preserve as invariantes**: nenhuma mudança pode permitir que o YAML desligue a Pausa 2, a Pausa 3, a whitelist de tools, o audit log, a redação de PII ou o isolamento do canal de teste.
- **O engine continua agnóstico de canal**: use `channel.tools.*`, nunca uma tool de provedor fixa nos passos do fluxo ([`docs/00-architecture.md`](docs/00-architecture.md)).
- **YAML**: indentação de 2 espaços, nomes de área em `kebab-case`, `schema: atende.v1` no topo, validado por `scripts/validate.sh`.
- **Python** (`lib/`): só biblioteca padrão, type hints e docstrings como nos módulos existentes.
- **Shell** (`scripts/`): `bash` com `set -euo pipefail`.
- Docs e prompts atuais estão em português; contribuições em inglês ou português são bem-vindas.

### Fluxo de PR

1. Abra uma issue (ou comente numa existente) descrevendo o que quer mudar.
2. Faça fork e crie uma branch: `feat/...`, `fix/...` ou `docs/...`.
3. Mantenha o PR focado; rode os comandos de validação acima.
4. Descreva o que mudou e como você verificou. Se mexeu em `engine/`, `schemas/`, `globals.yaml` ou `lib/`, explique o impacto nas invariantes.
5. O `CODEOWNERS` pede a revisão automaticamente.

### 🌱 Good first issues

1. **Corrigir nomes de campo desatualizados nas docs.** O schema usa `channel.source_production` / `channel.source_test` e o `globals.yaml` usa `channel_test.source_test`, mas algumas docs ainda dizem `chat.space_production`, `chat.space_test` e `chat_test.space_test`: `GETTING-STARTED.md` (checklist de placeholders), `docs/01-yaml-schema.md` (exemplo e tabela de campos obrigatórios), `docs/03-creating-a-new-area.md` (checklist mínimo) e `docs/08-methodology-area-discovery.md` (pseudocódigo).
2. **Testes unitários para `lib/`.** Sugestão de início: uma pasta `tests/` com testes de `lib/pii_redactor.py` (o exemplo da docstring, idempotência em texto já redigido, ordem dos padrões) e de `_hash_payload` em `lib/audit_logger.py` (`None` → `""` vs `{}` → hash).
3. **Investigar a demo de clustering.** `python3 lib/threshold_cluster.py` hoje imprime `De 12 amostras → 12 clusters` com `threshold=0.35`, ou seja, nenhum chamado parecido é agrupado. Ajuste o threshold da demo ou a tokenização em `lib/threshold_cluster.py` e adicione um teste que fixe o agrupamento esperado.
4. **Nova área de exemplo.** Adicione uma área pequena e fictícia (ex.: `examples/backoffice-area.yaml` ou uma área por e-mail usando `examples/channels/email-gmail.yaml`) que passe em `bash scripts/validate.sh <arquivo>`.
5. **Workflow de CI.** Adicione `.github/workflows/validate.yml` que instale `jsonschema` + `pyyaml` e rode `scripts/validate.sh`, `scripts/validate.sh examples/minimal-area.yaml` e `scripts/check-no-pii.sh`.
6. **Docs em inglês.** Traduza `docs/06-glossary.md` (curto) ou o `GETTING-STARTED.md` para inglês como `*.en.md` e linke no README.
