# Canais de comunicação — abstração e adapters

O atende-AI é agnóstico de canal. O engine nunca hardcoda um provedor — ele lê `channel.tools.*` do YAML e trabalha com qualquer canal que tenha um MCP configurado.

---

## O bloco `channel`

```yaml
channel:
  type: google_chat          # google_chat | email | whatsapp
  tools:
    read:   mcp__...         # ler/listar mensagens de um thread
    search: mcp__...         # buscar por keyword (opcional)
    send:   mcp__...         # enviar/rascunhar resposta
  source_production: "..."   # identificador do canal de produção
  source_test:       "..."   # canal de TESTE — nunca usar produção para testes
  address_format: mention    # mention | email | name
```

O engine resolve `{{ requester_address }}` nos templates de resposta usando `address_format`:

| `address_format` | Resultado em `{{ requester_address }}` | Uso |
|---|---|---|
| `mention` | `<users/USER_ID>` | Google Chat (menção) |
| `email` | `fulano@empresa.com` | Email |
| `name` | `Fulano Silva` | WhatsApp / canais sem menção |

---

## Adapter 1 — Google Chat

**MCP:** `claude.ai Google Chat` (disponível nativamente no AI CLI com a integração Google)

| Campo | Valor |
|---|---|
| `channel.tools.read` | `mcp__claude_ai_Google_Chat__list_messages` |
| `channel.tools.search` | `mcp__claude_ai_Google_Chat__search_messages` |
| `channel.tools.send` | `mcp__claude_ai_Google_Chat__send_message` |
| `source_production` | `spaces/XXXXXXXXXXXXXXX` (ID do canal — extraído da URL) |
| `address_format` | `mention` |

**Semântica de envio:** `send_message` posta a mensagem diretamente no thread.

**user_id em `people[]`:** campo `senderId` retornado por `list_messages` (formato `users/DIGITS`).

**Preset pronto:** `examples/channels/google-chat.yaml`

---

## Adapter 2 — Email (Gmail MCP)

**MCP:** `claude.ai Gmail` (disponível nativamente no AI CLI com a integração Google)

| Campo | Valor |
|---|---|
| `channel.tools.read` | `mcp__claude_ai_Gmail__get_thread` |
| `channel.tools.search` | `mcp__claude_ai_Gmail__search_threads` |
| `channel.tools.send` | `mcp__claude_ai_Gmail__create_draft` |
| `source_production` | Label ou query Gmail (ex: `label:suporte-prod`, `to:suporte@empresa.com`) |
| `address_format` | `email` |

**Semântica de envio: sempre rascunho.**
O engine chama `create_draft` (não `send`). O operador revisa e envia manualmente — reforça a Pausa 3. Isso é intencional: email tem maior formalidade e nenhuma mensagem deve chegar ao cliente sem revisão final.

**user_id em `people[]`:** endereço de e-mail (`from` do Gmail).

**Varredura:** `/atende-varredura` usa `search_threads` com a query de `source_production` + filtro de janela temporal.

**Preset pronto:** `examples/channels/email-gmail.yaml`

---

## Adapter 3 — WhatsApp (MCP do provedor)

**MCP:** **Não embarcado** — você conecta o MCP do seu provedor WhatsApp.

Provedores compatíveis (qualquer MCP que exponha as tools):
- Twilio WhatsApp Business
- 360Dialog
- Meta Cloud API (WABA)
- Qualquer provedor com MCP próprio

| Campo | Valor |
|---|---|
| `channel.tools.read` | `mcp__SEU_PROVEDOR__read_thread` (nome exato do seu MCP) |
| `channel.tools.search` | `mcp__SEU_PROVEDOR__search` (se disponível) |
| `channel.tools.send` | `mcp__SEU_PROVEDOR__send_message` |
| `source_production` | Número (`+5511...`) ou group_id do grupo de suporte |
| `address_format` | `name` (WhatsApp não suporta menção por ID) |

**Semântica de envio:** depende do MCP do provedor — a Pausa 3 sempre acontece antes do envio.

**user_id em `people[]`:** número de telefone ou ID do participante conforme o provedor.

**Sem sinal ✅ nativo:** o classifier marca `reopen_suspected: true` se detectar "ok", "obrigado", "resolvido", "funcionou" na última mensagem do solicitante.

**Preset pronto:** `examples/channels/whatsapp.yaml`

---

## Invariantes independentes do canal

Estas regras se aplicam a qualquer `channel.type`:

| Invariante | Detalhe |
|---|---|
| **Nunca testar em `source_production`** | `atende-varredura` e `atende` usam `source_test` para envios de teste |
| **Pausa 3 sempre acontece** | Nenhuma mensagem vai para o canal sem aprovação explícita do operador |
| **PII redaction antes de LLM** | `lib/pii_redactor.py` processa textos do canal antes de enviar a qualquer LLM externo |
| **`tools_allowed[]` deve incluir `channel.tools.*`** | As tools de I/O do canal devem estar na whitelist da área |
| **`address_format` controla `{{ requester_address }}`** | O engine nunca hardcoda sintaxe de menção de um canal específico |

---

## Adicionando um canal novo

Para integrar um canal não suportado (ex: Slack, Teams, Telegram):

1. Verifique se existe um MCP para o canal no AI CLI
2. Identifique as tools equivalentes a `read`, `search`, `send`
3. Adicione `"novo-canal"` ao enum de `channel.type` em `schemas/atende.v1.json`
4. Crie o preset em `examples/channels/novo-canal.yaml`
5. Adicione as tools ao front-matter dos engines (atende.md, atende-classifier.md, atende-varredura.md)
6. Documente o `address_format` e o formato de `source_production`

O engine e os libs (`pii_redactor`, `threshold_cluster`, `audit_logger`) não precisam ser alterados.

---

## Comparativo rápido

| | Google Chat | Email | WhatsApp |
|---|---|---|---|
| MCP embarcado | ✅ nativo | ✅ nativo | ❌ (plugar provedor) |
| Menção de usuário | `<users/ID>` | endereço | nome em texto |
| Envio direto | ✅ | ❌ (só rascunho) | ✅ (via MCP) |
| Busca por keyword | ✅ search_messages | ✅ search_threads | depende do provedor |
| Sinal de fechamento | ✅ `✅` ou texto | ✅ resposta do thread | `✅` ou "obrigado" |
| Suporte em varredura | ✅ completo | ✅ completo | ✅ (depende do MCP) |
