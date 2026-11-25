# Schema `atende.v1`

Validacao em `schemas/atende.v1.json` (JSON Schema 2020-12).

## Estrutura completa

```yaml
schema: atende.v1                    # obrigatorio

area:                                # metadados da area
  name: minha-area                   # kebab-case, vira nome do arquivo
  description: "Resolve chamados..."
  owner_team: "Tecnologia"
  severity_default: medium           # low | medium | high | critical
  language_default: pt-BR            # pt-BR | es

channel:                             # canal de I/O (detalhes em docs/05-channels.md)
  type: google_chat                  # google_chat | email | whatsapp
  tools:
    read: mcp__claude_ai_Google_Chat__list_messages
    search: mcp__claude_ai_Google_Chat__search_messages
    send: mcp__claude_ai_Google_Chat__send_message
  source_production: "spaces/REPLACE_PRODUCTION_SPACE_ID"
  source_test: "spaces/REPLACE_TEST_SPACE_ID"  # herda de globals se omitido
  address_format: mention            # mention | email | name

people:                              # identificadores das pessoas no canal
  - name: "Operador Principal"
    user_id: "users/100000000000000000001"
    role: operator                   # opcional: relay | operator | escalation
  - { name: "Pessoa Autorizada 1", user_id: "users/100000000000000000002" }

authorizations:                      # restricoes por tipo
  - rule: "tipo #4 (ajustar-quota)"
    allowed_only: ["Billing Lead", "Support Operator"]

tools_allowed:                       # whitelist estrita de MCPs
  - mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly
  - mcp__claude_ai_Google_Chat__list_messages
  - mcp__claude_ai_Google_Chat__search_messages
  - mcp__claude_ai_Google_Chat__send_message
  - mcp__YOUR_ORG_MCP__*   # wildcard em namespace conhecido

entity_lookups:                      # queries parametrizadas
  - id: by_email
    description: "Buscar usuario por e-mail"
    sql: |
      SELECT user_uuid, email, display_name, is_active
      FROM `REPLACE_PROJECT.REPLACE_DATASET.users`
      WHERE LOWER(email) = LOWER(@email)
    params:
      - { name: email, type: string, required: true }

types:                               # tipos de chamado catalogados
  - id: 1
    name: "Reset senha"
    severity: low
    risk_level: safe                 # safe | sensitive | destructive
    keywords: ["nao consigo entrar", "reset de senha", "bloqueado"]
    requires: [user_uuid]
    blockers:
      - check: state_is_disabled
        else_message: "Conta suspensa — verificar tipo correto antes de resetar."
    operation:
      tool: "mcp__YOUR_ORG_MCP__Reset_Senha"
      payload:
        operacao: "REPLACE_OPERATION_NAME"
        user_uuid: "{{ entity_uuid }}"
        email: "{{ operator_email }}"
    escalation_to: []
    response_template:
      pt-BR: |
        Olá {{ requester_address }}!
        Reset enviado para {{ entity_name }} ✅
        Qualquer dúvida, nos avise!

escalation_matrix:                   # quem acionar por sintoma
  - symptom: "bug de billing"
    primary: "users/100000000000000000003"
    parallel: ["users/100000000000000000004"]
    sla_minutes: 60

audit:
  destination: "bigquery://REPLACE_AUDIT_PROJECT.atende_audit.executions"
  log_redacted: true

refinement_backlog:                  # bootstrap hibrido -- duvidas pendentes
  - { question: "...", priority: low }
```

## Campos obrigatorios

| Campo | Tipo | Obrigatorio |
|---|---|---|
| `schema` | string (`"atende.v1"`) | sim |
| `area.name` | kebab-case | sim |
| `area.owner_team` | string | sim |
| `channel.type` | `google_chat` \| `email` \| `whatsapp` | sim |
| `channel.tools.read` / `.send` | tool MCP | sim |
| `channel.source_production` | string (formato do canal) | sim |
| `tools_allowed` | array de strings | sim |
| `types` | array (minimo 1) | sim |
| `audit.destination` | string (`"bigquery://..."`) | sim |

## Variaveis Jinja2 disponiveis em templates

- `{{ operator_email }}` -- capturado runtime (nunca no YAML)
- `{{ requester_address }}` -- como enderecar o solicitante (resolvido por `channel.address_format`); use este nos templates, nunca `<users/...>` fixo
- `{{ requester_id }}` -- identificador bruto extraido pelo classifier
- `{{ entity_name }}`, `{{ entity_uuid }}` -- da query de busca
- `{{ workspace_id }}`, `{{ account_id }}` -- quando aplicavel
- `{{ year }}` -- ano/periodo de referencia

## Validacao

```bash
bash scripts/validate.sh                # valida todos
bash scripts/validate.sh areas/foo.yaml # valida especifico
```

Engine carrega YAML, valida contra schema, **rejeita** se invalido.
