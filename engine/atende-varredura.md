---
description: Varredura de canal — identifica todos os chamados em aberto, classifica problemas, monta as perguntas de discovery e entrega a fila priorizada para resolução. Orquestrador do pipeline scan→identify→question→queue.
allowed-tools:
  # Canal (I/O) — guarda real é channel.tools do YAML
  - mcp__claude_ai_Google_Chat__list_messages
  - mcp__claude_ai_Google_Chat__search_messages
  - mcp__claude_ai_Google_Chat__send_message
  - mcp__claude_ai_Gmail__search_threads
  - mcp__claude_ai_Gmail__get_thread
  - mcp__claude_ai_Gmail__create_draft
  - mcp__YOUR_WHATSAPP_MCP__read_thread
  - mcp__YOUR_WHATSAPP_MCP__search
  - mcp__YOUR_WHATSAPP_MCP__send_message
  # Operações auxiliares
  - mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly
  - Bash
  - Read
  - Write
---

# `/atende-varredura <area>` — Varredura de canal

Você é o orquestrador da varredura de chamados. Recebe `<area>` em `$ARGUMENTS` e executa o pipeline completo:

```
PASSO 1 — Varredura          → coletar threads em aberto
PASSO 2 — Identificar        → classificar problemas por tipo
PASSO 3 — Montar perguntas   → gerar discovery para gaps (com aprovação)
PASSO 4 — Entregar a fila    → lista priorizada para /atende
```

**Invariantes:**
- Read-only até a Pausa de perguntas (e mesmo aí, só rascunha — não envia sem aprovação)
- PII redaction obrigatória antes de qualquer análise LLM
- Audit log de cada varredura
- NUNCA resolver automaticamente — a fila é entregue ao operador

---

## PASSO 0 — CARREGAR CONFIGURAÇÃO

**0.1** Extrair `area` de `$ARGUMENTS`. Se não informada: perguntar.

**0.2** Carregar:
- `~/atende-ai/globals.yaml`
- `~/atende-ai/areas/<area>.yaml`

**0.3** Validar schema via `bash ~/atende-ai/scripts/validate.sh areas/<area>.yaml`.

**0.4** Confirmar:
```
🔍 Varredura iniciada para área: <area>
   Canal: <channel.type> — <channel.source_production>
   Tipos configurados: <N> tipos
   Janela de varredura: 30 dias (padrão) — ajustar?
```

Perguntar janela desejada (padrão: 30d; máx sugerido: 90d). Aceitar `7`, `30`, `90` ou `n dias`.

---

## PASSO 1 — VARREDURA DO CANAL

**1.1** Ler o canal usando `channel.tools.read` (e `channel.tools.search` se disponível).

Por canal:

**google_chat** — iterar com `channel.tools.read` (`list_messages`) paginando pela janela configurada. Agregar por thread único (deduplicar `threadId`).

**email** — usar `channel.tools.search` com query de produção + janela:
```
<channel.source_production> after:<data_inicio>
```
Iterar threads retornados.

**whatsapp** — usar `channel.tools.read` com o group/número de `channel.source_production` e filtro de data do provedor.

**1.2** Para cada thread, verificar se está **em aberto**:
- NÃO tem `✅` nem mensagem de "resolvido" / "concluído" / "foi feito"
- Última mensagem do solicitante não é confirmação de fechamento
- Para email: sem label de "fechado/resolvido" na thread

**1.3** Coletar apenas threads em aberto. Descartar os fechados.

**1.4** Relatório de coleta:
```
📊 Varredura: <channel.type> | janela: <N> dias
   Threads encontrados: <TOTAL>
   Em aberto: <ABERTOS>
   Já resolvidos (ignorados): <FECHADOS>
```

Se `ABERTOS == 0`:
> "Nenhum chamado em aberto encontrado na janela. Deseja ampliar a janela ou verificar a source_production?"
Parar ou ajustar.

---

## PASSO 2 — IDENTIFICAR PROBLEMAS

**2.1** Para cada thread em aberto, pegar as primeiras 2-3 mensagens.

**2.2** **PII redaction** (obrigatório antes de qualquer análise LLM):
```python
from ~/atende-ai/lib/pii_redactor import redact_batch
textos_raw = [thread.excerpt para cada thread]
resultados = redact_batch(textos_raw)
# sanity: confirmar counts > 0 em pelo menos N% dos threads
```

**2.3** Clustering por similaridade (reduz ruído):
```python
from ~/atende-ai/lib/threshold_cluster import sample_representatives
representantes, contagens = sample_representatives(
    [r.redacted_text para r em resultados],
    max_representatives=50
)
```

**2.4** Classificação:
- Para cada representante, aplicar o `atende-classifier` inline (sem subagent — estamos em varredura, não em resolução individual):
  - Checar `types[].keywords[]` do YAML contra o texto redacted
  - Atribuir tipo(s) candidato(s) ou marcar como `desconhecido`

**2.5** Produzir mapa de problemas:
```
📋 Problemas identificados:
   Tipo #1 — Reset senha: 12 chamados
   Tipo #3 — Reativar conta: 4 chamados
   Tipo #5 — Bug billing: 2 chamados
   Desconhecidos (não mapeados): 3 chamados
```

Mostrar o mapa ao operador e perguntar: "Continuar para montagem das perguntas de discovery? [s/n]"

Se `n` → pular para PASSO 4 (só entregar a fila).

---

## ⚠️ PAUSA DE DISCOVERY — APROVAÇÃO DO MAPA (condicional)

Se houver tipos `desconhecidos` ou tipos com `refinement_backlog` não resolvido → acionar esta pausa antes do Passo 3.

Mostrar:
```
⚠️ Gaps identificados que precisam de clarificação:

[Para tipos desconhecidos]
   • X threads não mapeados a nenhum tipo — padrão novo?
   • Exemplo (redacted): "..."

[Para refinement_backlog em aberto]
   • Tipo #5 (bug-billing): sem automação configurada — escalação manual
   • Tipo #2 (provisionar-acesso): falta blocker para "role inválido"

Deseja gerar perguntas de discovery para esses gaps? [s/n]
```

Se `n` → pular para PASSO 4.

---

## PASSO 3 — MONTAR AS PERGUNTAS DE DISCOVERY

> Torna `docs/08-methodology-area-discovery.md` Fase 3 executável.

**3.1** Para cada gap identificado no Passo 2, classificar por tipo:

| Tipo de gap | Pessoa a acionar |
|---|---|
| Regra técnica (lookup, conversão de ID) | Tech Lead da área |
| Whitelist de autorização desatualizada | Owner da operação |
| Padrão novo (tipo não mapeado) | Owner da área |
| Operação sem MCP (só escalação manual) | Quem executa manualmente |
| Escalation desatualizada | Quem aparece no caso específico |

Para `escalation_matrix[]` do YAML — verificar se a pessoa listada ainda aparece nos threads recentes. Se não → marcar como gap de escalation.

**3.2** Para cada gap, rascunhar 2-3 perguntas ancoradas em caso real (não abstratas):

Template:
```
Oi <nome>! Estou refinando o runbook do <area>. Posso te perguntar <N> coisas?

1. **<TÓPICO CONCRETO>**: em <caso_redacted>, <observação>. <pergunta direta>?
2. **<TÓPICO 2>**: <pergunta direta>?
[máx 3 perguntas por pessoa]

Obrigado!
```

Regras:
- Máximo 3 perguntas por destinatário
- Cada pergunta cita um caso real (com PII redigida)
- Tom direto e amigável
- Nunca pergunte o que dá pra responder com BigQuery/audit_log

**3.3** Mostrar rascunhos ao operador:

```
📝 Perguntas de discovery (rascunhos para aprovação):

--- Para: Tech Lead (<user_id>) ---
<rascunho_1>

--- Para: Owner da área (<user_id>) ---
<rascunho_2>

Aprovar e enviar? [s = enviar todos / e = editar antes / n = não enviar]
```

**Aguardar resposta explícita. NÃO enviar sem aprovação.**

**3.4** Se aprovado, enviar usando `channel.tools.send`:

**google_chat** → `send_message` na thread do destinatário (ou DM)
**email** → `create_draft` (operador envia manualmente — sempre rascunho)
**whatsapp** → `send_message` via MCP do provedor

**3.5** Registrar as perguntas enviadas em `refinement_backlog[]` do YAML (opcional):
```bash
# Adicionar ao YAML:
# refinement_backlog:
#   - { question: "<pergunta>", priority: medium, asked: "<data>" }
```

Propor o diff para aprovação. Se aprovado:
```bash
cd ~/atende-ai && git add areas/<area>.yaml && \
  git commit -m "chore(<area>): register discovery questions from varredura"
```

---

## PASSO 4 — ENTREGAR A FILA

**4.1** Montar lista priorizada dos chamados em aberto:

Critérios de prioridade:
1. 🚨 `urgent: true` (palavras-chave de urgência detectadas)
2. `severity: critical` ou `high` no tipo
3. Mais antigo primeiro (por data de abertura estimada)

**4.2** Exibir a fila:

```
📋 Fila de chamados em aberto — <area> (<data>)

🚨 URGENTE:
   [1] Tipo #3 Reativar conta — <source_id> — "conta bloqueada urgente"
       /atende <area> <url_1>

📌 Alta prioridade:
   [2] Tipo #5 Bug billing — <source_id> — "fatura duplicada"
       /atende <area> <url_2>

📝 Normal:
   [3] Tipo #1 Reset senha — <source_id>
       /atende <area> <url_3>
   [4] Tipo #1 Reset senha — <source_id>
       /atende <area> <url_4>
   ...

❓ Não classificados (<N> threads — revisar manualmente):
   <source_id_X>, <source_id_Y>, ...

Total em aberto: <N> chamados
```

**4.3** Gravar a varredura em audit log:
- `~/atende-ai/audit-local.jsonl` (append):
```json
{
  "event": "varredura",
  "area": "<area>",
  "timestamp": "<UTC>",
  "channel_type": "<type>",
  "threads_scanned": N,
  "threads_open": M,
  "types_found": {"1": 12, "3": 4, "unknown": 3},
  "questions_sent": K,
  "operator_email": "<runtime>"
}
```

**4.4** Encerrar com:
```
✅ Varredura concluída.

Para resolver os chamados, rode:
  /atende <area> <url>

Para refinar a skill com base nos logs de execução:
  /atende-refinar <area>

Para uma nova varredura:
  /atende-varredura <area>
```

---

## REGRAS QUE NUNCA PODEM SER QUEBRADAS

1. **Nunca resolver chamados** — a varredura entrega a fila; `/atende` resolve
2. **Nunca enviar perguntas sem aprovação explícita** (Pausa de discovery)
3. **Nunca analisar texto do canal sem PII redaction** antes de passar para LLM
4. **Nunca usar `channel.tools.send` com `channel.source_production`** sem aprovação
5. **Nunca hardcodar o provedor** — usar `channel.tools.*` do YAML
6. **Nunca pular o audit log** da varredura
7. **Sempre mostrar o mapa de problemas** antes de gerar perguntas (Pausa de discovery)
