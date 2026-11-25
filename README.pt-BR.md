[🇺🇸 English](README.md) · 🇧🇷 Português

# atende-AI

> **Transforme conhecimento operacional em skills de IA auditáveis.**
>
> Toda vez que você resolve um problema do mesmo jeito duas vezes, existe uma skill esperando para ser escrita.

![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Python 3](https://img.shields.io/badge/python-3-blue.svg)
![Shell: Bash](https://img.shields.io/badge/shell-bash-lightgrey.svg)

O `atende-AI` é um engine genérico de atendimento para AI CLIs: os procedimentos de suporte do seu time ficam em **arquivos YAML**, e o engine os executa com **aprovação humana obrigatória**, **whitelist de tools**, **audit log** e **redação de PII**.

**Princípio central: conteúdo de domínio é YAML, fluxo é código.**

---

## 💡 Por quê

Times de suporte resolvem os mesmos pedidos várias vezes, e esse conhecimento costuma ficar na cabeça das pessoas ou no histórico do chat. Deixar uma IA agir sobre isso é arriscado, a não ser que cada passo seja explícito, revisável e registrado.

O `atende-AI` faz do procedimento o artefato: um YAML que você lê, compara em diff, revisa via `CODEOWNERS` e valida contra um JSON Schema. O engine nunca deixa esse YAML desligar as proteções.

## ✨ Principais recursos

- **Procedimentos como "áreas" em YAML** — tipos de chamado, palavras-chave, queries de busca, bloqueadores, tools permitidas e templates de resposta por área, validados por [`schemas/atende.v1.json`](schemas/atende.v1.json).
- **Humano no circuito por design** — o engine sempre pausa para aprovação antes de executar uma operação (Pausa 2) e antes de enviar uma resposta (Pausa 3).
- **Whitelist estrita de tools** — `tools_allowed[]` é checado no carregamento; qualquer outra tool é rejeitada.
- **Audit log** — toda execução é registrada com hash do payload, operador, área, tipo e resultado ([`lib/audit_logger.py`](lib/audit_logger.py)).
- **Redação de PII** — e-mails, IDs, URLs, CPF, telefones e nomes são substituídos antes que o histórico do canal chegue a um LLM externo ([`lib/pii_redactor.py`](lib/pii_redactor.py)).
- **Agnóstico de canal** — Google Chat, Gmail (só rascunho) e WhatsApp (via MCP do seu provedor) por meio de `channel.tools.*` ([`docs/05-channels.md`](docs/05-channels.md)).
- **Criação guiada e aprendizado contínuo** — wizard `/atende-criar`, varredura de canal `/atende-varredura`, refinamento a partir do audit log `/atende-refinar`.
- **Operações destrutivas exigem frase de confirmação literal**, não basta "sim" ([`docs/04-governance.md`](docs/04-governance.md)).

---

## 🚀 Início rápido

**Pré-requisitos:** um AI CLI que carregue comandos de `~/.claude/commands/` (é onde `scripts/install.sh` liga o engine), MCPs do Google Chat / BigQuery configurados (veja [`GETTING-STARTED.md`](GETTING-STARTED.md)) e, para validar, `ajv-cli` ou `python3` com `jsonschema` + `pyyaml`.

```bash
# Os arquivos do engine referenciam ~/atende-ai/, então clone nessa pasta
git clone https://github.com/y4g0o/atende-ai.git ~/atende-ai
cd ~/atende-ai

# Dependências de validação (escolha uma)
pip install jsonschema pyyaml      # ou: npm install -g ajv-cli

# Instale os skills do engine no AI CLI (~/.claude/commands/ e ~/.claude/agents/)
bash scripts/install.sh

# Caminho A — wizard guiado (recomendado), dentro do AI CLI
/atende-criar

# Caminho B — copie a área de exemplo e preencha
cp areas/helpdesk-saas.yaml areas/minha-area.yaml
# edite minha-area.yaml seguindo o cabeçalho "=== PREENCHA ESTES VALORES ==="
bash scripts/validate.sh areas/minha-area.yaml

# Resolva um chamado real, dentro do AI CLI
/atende minha-area https://chat.google.com/room/SEU_SPACE/THREAD_ID/...
```

Experimente sem nenhuma credencial (checagens puramente locais):

```bash
bash scripts/validate.sh                       # valida todos os areas/*.yaml contra o schema
bash scripts/validate.sh examples/minimal-area.yaml
bash scripts/check-no-pii.sh                   # lint de tokens proibidos (padrões reais em .pii-patterns.local, gitignored)
python3 -m unittest discover -s tests          # suíte de testes (requer pyyaml + jsonschema)
python3 lib/threshold_cluster.py               # demo do clustering Jaccard usado na análise de histórico
```

Leia o [`GETTING-STARTED.md`](GETTING-STARTED.md) para o guia completo, incluindo o checklist de placeholders.

---

## ⚙️ Como funciona

O engine implementa um fluxo fixo, à prova de adulteração:

```
ler thread → classificar → buscar IDs → validar bloqueadores
    → ⚠️ PAUSA 2 (aprovação) → executar → audit log
    → ⚠️ PAUSA 3 (aprovação da mensagem) → responder
```

Cada **área** (canal de suporte, backoffice, financeiro etc.) define em YAML só o conteúdo de domínio: tipos de chamado, queries de busca, tools permitidas, templates de resposta. O engine não muda. Um subagent classificador barato ([`engine/atende-classifier.md`](engine/atende-classifier.md)) lê o thread e devolve JSON, então o engine principal não gasta contexto com a leitura. Uma Pausa 1 opcional pergunta se deve buscar histórico do canal quando há dúvidas.

### Invariantes — o YAML não pode desligar

| Guarda | Efeito |
|---|---|
| **Pausa 2** (aprovação de execução) | Sempre mostrada antes de qualquer operação |
| **Pausa 3** (aprovação da mensagem) | Mensagem exata mostrada para aprovação antes do envio |
| **Whitelist de tools** | `tools_allowed[]` no YAML; o engine rejeita tools não listadas no carregamento |
| **Audit log** | Toda execução grava no BigQuery (fallback JSONL local em `lib/audit_logger.py`); o engine falha cedo se a auditoria estiver indisponível |
| **Redação de PII** | Obrigatória antes de qualquer chamada a LLM externo que processe histórico do canal |
| **Isolamento do espaço de teste** | O engine bloqueia `send_message` para o espaço de produção durante testes |
| **E-mail do operador em runtime** | Nunca persistido no YAML; capturado por sessão como `{{ operator_email }}` |

Mais detalhes: [arquitetura](docs/00-architecture.md) · [fluxo do engine](docs/02-engine-flow.md) · [governança](docs/04-governance.md).

### Como nasce uma skill

1. **Mapear** — listar os 3-5 tipos de pedido mais comuns (no chute ou a partir do histórico do canal)
2. **Buscar** — validar contra casos reais passados via `search_messages` (mais barato que entrevistas)
3. **Entrevistar** — fazer perguntas pontuais só onde a busca revela lacunas
4. **Refinar** — cada execução real realimenta o YAML via `/atende-refinar`

Veja [`docs/08-methodology-area-discovery.md`](docs/08-methodology-area-discovery.md) para o playbook completo.

### Estrutura

```
atende-ai/
├── engine/             # Skills do AI CLI (atende, atende-criar, atende-refinar, atende-varredura, atende-sync, atende-classifier)
├── areas/              # YAMLs de área (helpdesk-saas.yaml para começar — domínio SaaS fictício, 8 tipos)
├── schemas/            # JSON Schema (atende.v1.json)
├── lib/                # Python puro: pii_redactor, threshold_cluster, audit_logger
├── scripts/            # install.sh, validate.sh, check-no-pii.sh
├── tests/              # unittest: libs, scripts e invariantes engine↔schema↔docs
├── docs/               # Arquitetura, referência do schema, governança, canais, glossário, lições aprendidas
├── examples/           # minimal-area.yaml (referência mínima) + presets em channels/ (Google Chat, Gmail, WhatsApp)
└── globals.yaml        # Regras compartilhadas por todas as áreas (canal de teste, convenções, regras absolutas)
```

---

## 🚧 Status e limitações

- **Versão inicial** — versão pública e sanitizada de uma ferramenta usada em canais de suporte reais (veja as [lições aprendidas](docs/07-licoes.md)).
- **O engine é um conjunto de arquivos de prompt/skill** (`engine/*.md`) executados por um AI CLI, não um serviço independente. `lib/` é Python puro, sem dependências externas.
- **Traga seus próprios MCPs** — as operações passam pelo MCP da sua organização (`mcp__YOUR_ORG_MCP__*`); WhatsApp precisa do MCP do seu provedor. O destino de auditoria precisa ser uma URI `bigquery://` (regra do schema).
- **Idiomas:** templates de resposta suportam `pt-BR` e `es` (enum do schema).
- **RBAC em nível MVP** (`authorizations[]` no YAML) e **sem rollback automático** de operações executadas ([`docs/04-governance.md`](docs/04-governance.md)).
- **Os padrões de PII são ajustados a formatos brasileiros** (CPF, CEP, telefones `+55`) e usam heurística para nomes — adapte aos seus dados.
- **Suíte de testes incluída (`tests/`), ainda sem CI.**
- **A maior parte da documentação, dos prompts do engine e dos comentários está em português**; este README e o `CONTRIBUTING.md` também existem em inglês.

## 🗺️ Roadmap

- [ ] RBAC num `permissions.yaml` separado, herdado de `globals` ([`docs/04-governance.md`](docs/04-governance.md))
- [ ] Rollback automatizado, modelando uma "operação inversa" por tipo ([`docs/04-governance.md`](docs/04-governance.md))
- [ ] Novos adapters de canal (Slack, Teams, Telegram) seguindo o checklist de [`docs/05-channels.md`](docs/05-channels.md)
- [x] Suíte de testes para `lib/`, scripts e invariantes do engine/schema (`tests/`)
- [ ] CI rodando os testes + `validate.sh` + `check-no-pii.sh`
- [ ] Versões em inglês de `docs/` e do `GETTING-STARTED.md`

## 🤝 Contribuindo

Contribuições são bem-vindas — novas áreas de exemplo, presets de canal, testes e docs são as portas de entrada mais fáceis. Leia o [`CONTRIBUTING.md`](CONTRIBUTING.md) para setup, validação, estilo, fluxo de PR e uma lista de **good first issues**.

## 📄 Licença

MIT — veja [`LICENSE`](LICENSE). Criado por **Yago Macambira** ([@y4g0o](https://github.com/y4g0o)).
