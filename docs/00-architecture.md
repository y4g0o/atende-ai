# Arquitetura

## Principio

**Conteudo de dominio e YAML, fluxo e codigo.** O engine implementa o fluxo invariante (ler thread -> classificar -> buscar -> validar -> executar -> responder) com 3 pausas hardcoded. Cada area define em YAML apenas o conteudo de dominio: tipos de chamado, queries, tools permitidas, templates.

YAML **nao pode** desligar invariantes: aprovacao humana, whitelist de tools, canal de teste, audit log.

O engine e **agnostico de canal** — nunca hardcoda um provedor. O canal e declarado em `channel.tools.*` no YAML e o engine usa essas tools para I/O.

## Componentes

```
+----------------------------------------------------------+
|                      AI CLI (host)                      |
|                                                          |
|  +------------------+   +--------------------+          |
|  | /atende-varredura|   | /atende (resolver) |          |
|  | (scan→identify→  |   | (1 chamado, 3      |          |
|  |  question→queue) |   |  pausas)           |          |
|  +--------+---------+   +--------+-----------+          |
|           |                      |                      |
|           v                      v                      |
|  +--------------------------------------------------+   |
|  | engine/atende-classifier (subagent, Haiku)       |   |
|  |   le thread via channel.tools.read               |   |
|  |   classifica tipos, extrai entidades, urgencia   |   |
|  +--------------------------------------------------+   |
|           |                                             |
|           v                                             |
|  +--------------------------------------------------+   |
|  |  Carrega areas/<name>.yaml + globals.yaml        |   |
|  |  Valida contra schemas/atende.v1.json            |   |
|  |  Resolve channel.address_format → requester_addr |   |
|  +--------+-----------------------------------------+   |
|           |                                             |
|           v                                             |
|  +--------------------------------------------------+   |
|  |  Fluxo /atende:                                  |   |
|  |  1. channel.tools.read (ler thread)              |   |
|  |  2. classifier -> tipos, entidades, urgencia     |   |
|  |  3. entity_lookups (BigQuery MCP)                |   |
|  |  4. blockers + validacao de coerencia            |   |
|  |  5. ⚠️ Pausa 1 (opcional -- duvidas/historico)  |   |
|  |  6. ⚠️ Pausa 2 -- aprovacao de execucao          |   |
|  |  7. operation.tool (MCP whitelisted)             |   |
|  |  8. audit log -> BQ atende_audit.executions      |   |
|  |  9. response_template[idioma] + requester_addr   |   |
|  |  10. ⚠️ Pausa 3 -- aprovacao de envio            |   |
|  |  11. channel.tools.send (Google Chat / Gmail /   |   |
|  |       WhatsApp conforme channel.type)            |   |
|  +--------------------------------------------------+   |
|                                                          |
|  Fluxo /atende-varredura:                               |
|  1. channel.tools.read/search (varrer janela)           |
|  2. pii_redactor + threshold_cluster + LLM              |
|  3. discovery questions (com Pausa de aprovacao)        |
|  4. fila priorizada → operador roda /atende por URL     |
+----------------------------------------------------------+
                           |
                           v
   +-------------------------------------------------+
   | MCPs (whitelist por area em tools_allowed[])    |
   |  Canal I/O (declarado em channel.tools):        |
   |   - Google Chat (list/search/send messages)     |
   |   - Gmail (get_thread/search_threads/create_draft)|
   |   - WhatsApp (via MCP do provedor)              |
   |  Dados:                                         |
   |   - BigQuery (execute_sql_readonly)             |
   |  Operacoes:                                     |
   |   - MCP de operacoes da sua organizacao         |
   +-------------------------------------------------+
```

## Decisoes fundamentais

1. **YAML por area, nao DSL nova**: usamos schema explicito (`atende.v1`) validado por JSON Schema padrao. Nao inventamos linguagem.
2. **Engine unico**: um arquivo `engine/atende.md` para todas as areas. Diferenciacoes por `<area>` argumento.
3. **Canal agnostico**: `channel.type` + `channel.tools.*` permitem trocar Google Chat / Email / WhatsApp sem mudar o engine. O engine usa `channel.tools.read/search/send` — nunca um provedor especifico.
4. **Classifier como subagent**: le thread + classifica em modelo barato (Haiku), retorna JSON. Engine principal nao gasta contexto na leitura.
5. **Whitelist estrita de tools**: cada YAML declara `tools_allowed[]` (inclui as tools de `channel.tools`). Engine rejeita uso de tool fora da lista no carregamento.
6. **E-mail do operador e runtime**: capturado por sessao, nunca fixado no YAML. Vira `{{ operator_email }}` nos payloads.
7. **PII redaction antes de LLM externo**: quando engine analisa historico do canal para extrair padroes, pipeline em `lib/pii_redactor.py` remove e-mails/CPFs/codigos/nomes antes de enviar.
8. **Audit imutavel**: cada execucao grava em `REPLACE_AUDIT_PROJECT.atende_audit.executions` com hash do payload, operator_email, area, tipo, aprovacao, resultado.
9. **Varredura nao resolve**: `/atende-varredura` faz scan → identify → monta perguntas → entrega fila. Resolucao e sempre via `/atende` (1 chamado por invocacao, com 3 pausas).

## Inspiracoes (prior art)

- **Agent Skills** (AI CLI): base -- pasta com SKILL.md + frontmatter
- **StackStorm**: `criteria`/`triggers`, schema de actions tipadas (`required`, `secret`, `enum`)
- **Sublime Security**: `owner_team`, `severity`, `escalation_to`, validacao em CI
- **Rasa**: estrutura intents -> entities -> slots para classificacao
- **CrewAI**: separacao `agents.yaml` + `tasks.yaml`
- **GitHub Actions**: `permissions` cascading-deny, inputs tipados

## Anti-patterns evitados

- **CrewAI**: acopla YAML a codigo Python (nao fazemos)
- **Errbot/Hubot**: tudo em codigo, sem DSL para nao-devs
- **Rasa stories**: DSL de workflow incha rapido -- preferimos YAML descritivo, fluxo em codigo
- **Zendesk/Intercom/ServiceNow**: schema fechado em UI proprietaria
- **Canal hardcoded**: nunca `mcp__claude_ai_Google_Chat__*` diretamente nos passos do fluxo -- sempre via `channel.tools.*`
