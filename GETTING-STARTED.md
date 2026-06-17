# atende-AI — Guia de início rápido

Framework para criar skills de atendimento via Google Chat em AI CLI.
**Conteúdo de domínio é YAML, fluxo é código.**

---

## O que é

O `atende-AI` é um engine genérico que:
1. Lê o thread do Google Chat
2. Classifica o tipo de chamado pelo YAML da sua área
3. Busca IDs no BigQuery
4. Valida bloqueadores declarados no YAML
5. ⚠️ **Pausa 2** — pede aprovação ao operador antes de executar
6. Executa a operação via MCP whitelisted
7. Grava audit log
8. ⚠️ **Pausa 3** — mostra rascunho da mensagem e pede aprovação antes de enviar

**Invariantes que o YAML nunca pode desligar:** aprovação humana (Pausas 2 e 3), whitelist de tools, espaço de teste dedicado, audit log.

---

## Instalação — clone o repositório

> Os engine scripts referenciam `~/atende-ai/` internamente.
> Para que tudo funcione sem ajuste de caminho, clone para essa pasta:

```bash
git clone https://github.com/y4g0o/atende-ai.git ~/atende-ai
cd ~/atende-ai
```

---

## Dois caminhos para criar sua skill de atendimento

### Caminho A — Wizard guiado (recomendado)

```bash
# 1. Instale os skills no AI CLI
bash scripts/install.sh

# 2. No AI CLI, rode o wizard
/atende-criar
```

O wizard conduz por 4 fases (~20 min):
- **Fase 1** — coleta e-mail runtime, nome da área, space do Google Chat, MCPs
- **Fase 2** — analisa histórico do canal (opcional, com PII redaction automático)
- **Fase 3** — entrevista de bloqueadores: keywords, tools, pessoas autorizadas, escalação
- **Fase 4** — gera YAML, valida contra schema, commit

### Caminho B — Manual (a partir do template)

```bash
# 1. Copie o template de exemplo e abra para editar
cp areas/helpdesk-saas.yaml areas/minha-area.yaml
$EDITOR areas/minha-area.yaml
# (siga o cabeçalho "=== PREENCHA ESTES VALORES ===")

# 2. Valide contra o schema
bash scripts/validate.sh areas/minha-area.yaml

# 3. Instale os skills
bash scripts/install.sh
```

---

## Instalar + validar

```bash
# Pré-requisitos: AI CLI instalado + MCPs do Google Chat e BigQuery configurados

# Instalar symlinks dos engine skills em ~/.claude/commands/
bash scripts/install.sh

# Validar todos os YAMLs
bash scripts/validate.sh

# Verificar que o kit não tem PII antes de compartilhar
bash scripts/check-no-pii.sh
```

---

## Rodar

```bash
/atende minha-area https://chat.google.com/room/SEU_SPACE/THREAD_ID/...
```

---

## Checklist de preenchimento (Caminho B)

Antes de rodar, confirme que substituiu TODOS os placeholders em `areas/minha-area.yaml`:

- [ ] `chat.space_production` → space ID real do seu canal Google Chat
- [ ] `chat.space_test` → space ID do seu espaço de teste (nunca o de produção)
- [ ] `people[]` → nomes e User IDs reais do seu canal
- [ ] `authorizations[].allowed_only` → nomes reais das pessoas autorizadas
- [ ] `tools_allowed` → MCPs reais disponíveis na sua instância de AI CLI
- [ ] `entity_lookups[].sql` → project IDs e tabelas do seu BigQuery
- [ ] `types[].operation.tool` → tools MCP reais
- [ ] `types[].operation.payload.operacao` → nomes de operação reais
- [ ] `escalation_matrix[].primary` e `.parallel` → User IDs reais
- [ ] `audit.destination` → projeto BigQuery de auditoria real

E em `globals.yaml`:
- [ ] `chat_test.space_test` → space ID de teste real

---

## Regras absolutas (nunca quebrar)

1. **Nunca enviar mensagem no canal sem aprovação explícita** (Pausa 3)
2. **Nunca executar operação sem aprovação explícita** (Pausa 2)
3. **Nunca testar em `space_production`** — só no `space_test`
4. **Nunca usar `<users/all>`** em resposta — notifica o canal inteiro
5. **Nunca executar tipo `destructive`** sem frase literal de confirmação
6. **Nunca usar tool fora de `tools_allowed[]`**
7. **Nunca fixar e-mail do operador no YAML** — sempre `{{ operator_email }}` (capturado runtime)
8. **Nunca pular audit log**

---

## Estrutura do kit

```
atende-ai/
├── GETTING-STARTED.md         ← este arquivo
├── globals.yaml               ← regras compartilhadas (preencher space_test)
├── engine/
│   ├── atende.md              ← engine principal (/atende <area> <url>)
│   ├── atende-criar.md        ← wizard de criação de área
│   ├── atende-refinar.md      ← aprendizado contínuo via audit log
│   ├── atende-sync.md         ← sync com repositório git
│   └── atende-classifier.md   ← subagent classificador (Haiku)
├── schemas/
│   └── atende.v1.json         ← JSON Schema — valida seus YAMLs
├── scripts/
│   ├── install.sh             ← instala symlinks em ~/.claude/commands/
│   ├── validate.sh            ← valida YAMLs contra schema
│   └── check-no-pii.sh        ← lint anti-vazamento de dados sensíveis
├── lib/
│   ├── pii_redactor.py        ← redação de PII antes de enviar a LLM externo
│   ├── threshold_cluster.py   ← clustering por similaridade Jaccard
│   └── audit_logger.py        ← log de execuções (BQ + local jsonl)
├── areas/
│   └── helpdesk-saas.yaml     ← area de exemplo (domínio fictício SaaS)
└── examples/
    └── minimal-area.yaml      ← exemplo mínimo válido (referência)
```

---

## Próximos passos sugeridos

1. Escolha um caminho (A ou B acima)
2. Resolva 1 chamado real: `/atende minha-area <URL_do_chamado>`
3. Refine: `/atende-refinar minha-area`
4. Configure sync com seu repo: edite `engine/atende-sync.md` com seu remote
5. Leia `docs/07-licoes.md` — armadilhas operacionais reais (economiza round-trips com o operador)
