# Fluxo do engine

## `/atende` — Resolver um chamado

```
Operador                       Engine                              MCPs / BQ
   │                              │                                   │
   │ /atende helpdesk-saas <URL>  │                                   │
   ├─────────────────────────────►│ load areas/helpdesk-saas.yaml     │
   │                              │ validate vs schema                │
   │                              │ inject operator_email (runtime)   │
   │                              │ resolve requester_address_template│
   │                              │   (mention/email/name por canal)  │
   │                              │                                   │
   │                              │ parse source_id from URL          │
   │                              │ delegate to atende-classifier ───►│ channel.tools.read (Haiku)
   │                              │ ◄─ {types, entities, source_id, requester} ─
   │                              │                                   │
   │                              │ for each entity needing UUID:     │
   │                              ├──────────────────────────────────►│ execute_sql (entity_lookups)
   │                              │ ◄──── rows ───────────────────────│
   │                              │                                   │
   │                              │ run blockers (per type):          │
   │                              │  state_is_disabled / email_in_use / ...
   │                              │  validate state coherence         │
   │                              │                                   │
   │ ⚠️ Pausa 1 (se houver dúvidas)│                                   │
   │ ◄────── "buscar histórico?" ─│                                   │
   │ → sim/não                    │ se sim → channel.tools.search     │
   │                              │                                   │
   │ ⚠️ Pausa 2 (sempre)           │                                   │
   │ ◄────── plano de execução ───│                                   │
   │ → "sim"                      │                                   │
   │                              │ render payload com Jinja2         │
   │                              ├──────────────────────────────────►│ operation.tool (MCP)
   │                              │ ◄── result ───────────────────────│
   │                              │                                   │
   │                              │ audit log ───────────────────────►│ BQ atende_audit.executions
   │                              │   (area, type, operator_email, tool, payload_hash, result)
   │                              │                                   │
   │                              │ render response_template[lang]    │
   │                              │   {{ requester_address }} por     │
   │                              │   channel.address_format          │
   │                              │                                   │
   │ ⚠️ Pausa 3 (sempre)           │                                   │
   │ ◄────── mensagem completa ───│                                   │
   │ → "sim"                      │                                   │
   │                              ├──────────────────────────────────►│ channel.tools.send
   │                              │   (google_chat=send_message,      │
   │                              │    email=create_draft,            │
   │                              │    whatsapp=send via provedor)    │
   │                              │ ◄── confirmação ──────────────────│
   │                              │                                   │
   │                              │ (opcional) propor refinamento se padrão novo detectado
```

## `/atende-varredura` — Pipeline scan → identify → question → queue

```
Operador                    /atende-varredura                  MCPs / Libs
   │                              │                                  │
   │ /atende-varredura <area>     │                                  │
   ├─────────────────────────────►│ load YAML + validate             │
   │                              │                                  │
   │ confirmar janela?            │                                  │
   │ ◄─── "30 dias, ajustar?" ───│                                  │
   │ → ok                         │                                  │
   │                              │ PASSO 1 — Varredura:             │
   │                              ├─────────────────────────────────►│ channel.tools.read/search
   │                              │ ◄── threads (janela configurada) │
   │                              │ filtrar: abertos vs fechados     │
   │                              │                                  │
   │ ◄── relatório de coleta ────│                                  │
   │                              │                                  │
   │                              │ PASSO 2 — Identificar:           │
   │                              │ pii_redactor.redact_batch()      │
   │                              │ threshold_cluster.sample_repr.() │
   │                              │ classificar por tipos do YAML    │
   │                              │                                  │
   │ ◄── mapa de problemas ──────│                                  │
   │ → continuar?                 │                                  │
   │                              │                                  │
   │ ⚠️ Pausa de discovery         │                                  │
   │   (se houver gaps)           │                                  │
   │ ◄── "gerar perguntas?" ─────│                                  │
   │ → sim                        │                                  │
   │                              │ PASSO 3 — Montar perguntas:      │
   │                              │ detectar gaps → mapear gap→pessoa│
   │                              │ rascunhar 2-3 perguntas/pessoa   │
   │                              │ (PII redigida, caso concreto)    │
   │                              │                                  │
   │ ◄── rascunhos para aprovar ─│                                  │
   │ → sim / editar               │                                  │
   │                              ├─────────────────────────────────►│ channel.tools.send
   │                              │   (ou create_draft para email)   │
   │                              │                                  │
   │                              │ PASSO 4 — Entregar a fila:       │
   │                              │ priorizar por urgência + severity│
   │                              │ audit log da varredura           │
   │                              │                                  │
   │ ◄── fila priorizada ────────│                                  │
   │   /atende <area> <url> ×N    │                                  │
```

## Invariantes hardcoded

1. **Pausa 2 e Pausa 3 sempre acontecem.** YAML não desliga.
2. **Whitelist de tools validada no carregamento.** Tool fora rejeitada com erro.
3. **E-mail do operador injetado em runtime.** YAML usa `{{ operator_email }}`.
4. **Canal via `channel.tools.*`.** Engine nunca hardcoda provedor. Anti-spoof: valida `source == channel.source_production`.
5. **Audit obrigatório.** Toda execução e varredura grava em BQ (ou jsonl fallback). Sem audit, falha cedo.
6. **PII redaction obrigatória** em qualquer chamada LLM externa que processe mensagens do canal.
7. **Varredura não resolve.** `/atende-varredura` entrega a fila; `/atende` resolve um chamado por vez.

## Fallback de erros

- **MCP 4xx**: revisar parâmetros, re-buscar UUID, tentar 1x mais.
- **MCP 5xx ou timeout**: tentar 1x mais; se persistir → gerar `cmd.sh` fallback e Pausa 2 de novo.
- **MCP sucesso mas sistema não reflete**: NÃO re-executar — sistemas distribuídos têm delay de propagação.
- **Tool fora da whitelist**: erro fatal no carregamento; engine não inicia.
- **Schema inválido**: erro fatal; mostra mensagem clara com path do erro.
