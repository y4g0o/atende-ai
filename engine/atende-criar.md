---
description: Wizard de 4 fases para criar uma área nova no atende-AI — produz YAML válido em ≤ 30 min
allowed-tools:
  # Google Chat
  - mcp__claude_ai_Google_Chat__list_messages
  - mcp__claude_ai_Google_Chat__search_messages
  # Email (Gmail MCP)
  - mcp__claude_ai_Gmail__search_threads
  - mcp__claude_ai_Gmail__get_thread
  # WhatsApp — substitua pelo MCP do seu provedor
  - mcp__YOUR_WHATSAPP_MCP__read_thread
  - mcp__YOUR_WHATSAPP_MCP__search
  # Operações
  - mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly
  - Bash
  - Read
  - Write
---

# `/atende-criar` — Wizard de criação de área

Você cria uma nova área no `atende-AI`. Conduz o dono da área (não necessariamente técnico) por 4 fases até produzir um `areas/<name>.yaml` válido.

**Princípios:**
1. Capturar o **e-mail do operador** logo no início — vira variável runtime, NÃO entra no YAML
2. **PII redaction obrigatória** se for analisar histórico do canal (Fase 2)
3. **Bootstrap híbrido** — apenas bloqueadores entram na entrevista; refinamentos vão pro backlog
4. **Validação contra schema** antes de salvar — engine nunca aceita YAML inválido

---

## FASE 1 — Setup técnico (~5 min)

Pergunte sequencialmente. NÃO siga sem cada resposta. Aceite respostas curtas.

**1.1** "Qual seu e-mail corporativo? (será usado em runtime para registrar operações no seu nome — não vai ser salvo no YAML)"

Validar que é um e-mail válido. Se inválido, pedir de novo.

**1.2** "Qual o **nome da área**? (kebab-case — ex: `helpdesk-saas`, `comercial`, `backoffice`)"

Validar regex `^[a-z0-9]+(-[a-z0-9]+)*$`. Verificar que `~/atende-ai/areas/<name>.yaml` ainda NÃO existe.

**1.3** "Qual o **time responsável** (owner_team)? (ex: 'Tecnologia', 'Comercial', 'Backoffice')"

**1.4** "Qual é o **canal de comunicação** dessa área?"
```
1) Google Chat  — canal Space no Google Chat (MCP disponível)
2) E-mail       — caixa Gmail / inbox de suporte (MCP disponível)
3) WhatsApp     — grupo ou número WhatsApp (requer MCP do provedor configurado)
```

Com base na resposta, preencher o preset de `channel`:

**Google Chat:**
- Perguntar: "Cole o link do canal (space) de produção."
- Extrair `spaces/...` da URL.
- Preset `channel`:
  ```yaml
  channel:
    type: google_chat
    tools:
      read: mcp__claude_ai_Google_Chat__list_messages
      search: mcp__claude_ai_Google_Chat__search_messages
      send: mcp__claude_ai_Google_Chat__send_message
    source_production: "spaces/<EXTRAÍDO>"
    address_format: mention
  ```

**Email:**
- Perguntar: "Qual a query/label Gmail de produção? (ex: `label:suporte-prod` ou `to:suporte@empresa.com`)"
- Preset `channel`:
  ```yaml
  channel:
    type: email
    tools:
      read: mcp__claude_ai_Gmail__get_thread
      search: mcp__claude_ai_Gmail__search_threads
      send: mcp__claude_ai_Gmail__create_draft
    source_production: "<LABEL_OU_QUERY>"
    address_format: email
  ```
  > Aviso ao usuário: "Envio por email funciona como **rascunho** para você revisar e enviar — reforça a aprovação (Pausa 3)."

**WhatsApp:**
- Perguntar: "Qual o MCP do seu provedor WhatsApp? (ex: `mcp__twilio_whatsapp`) e qual o group_id/número de produção?"
- Preset `channel`:
  ```yaml
  channel:
    type: whatsapp
    tools:
      read: mcp__<PROVEDOR>__read_thread
      search: mcp__<PROVEDOR>__search
      send: mcp__<PROVEDOR>__send_message
    source_production: "<GROUP_ID_OU_NUMERO>"
    address_format: name
  ```

**1.5** "Idioma padrão de resposta? `pt-BR` (Brasil) ou `es` (México)?" — default `pt-BR`.

**1.6** Listar MCPs disponíveis no AI CLI atual (use Bash `claude --version` e busca em `~/.claude/`). Mostrar lista numerada e pedir: "Quais MCPs essa área vai usar? (responda os números separados por vírgula, ou 'todos')"

Incluir automaticamente as tools de `channel.tools` (read/search/send) na whitelist.

Comuns a sugerir além das do canal:
- `mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly`
- MCPs de operação específicos da área

Vira `tools_allowed[]` do YAML.

**1.7** Construir esqueleto inicial em memória:
```yaml
schema: atende.v1
area:
  name: <1.2>
  owner_team: <1.3>
  language_default: <1.5>
channel:
  <preset de 1.4>
people: []
tools_allowed: <1.6>
entity_lookups: []
types: []
audit:
  destination: "bigquery://REPLACE_AUDIT_PROJECT.atende_audit.executions"
refinement_backlog: []
```

Mostrar o esqueleto e perguntar "Está certo até aqui? [s/n]".

---

## FASE 2 — Análise de histórico (opcional)

**2.1** Ler o canal usando `channel.tools.read` (e `channel.tools.search` se disponível) com janela de 6 meses / 500 mensagens. Contar threads únicos.

**2.2** Mostrar estimativa:
```
📊 Histórico do canal:
   • {N} threads únicos nos últimos {M} dias
   • Estimativa de tokens para análise: ~{T} (após PII redaction)
   • Tempo estimado: ~{S} segundos

Analisar para sugerir tipos automaticamente?
  s = sim, analisa tudo
  amostra = amostra inteligente (cluster por similaridade, ~50 representantes)
  n = pular, eu descrevo os tipos manualmente
```

**2.3a** Se `n` → pular para Fase 3 com `types: []` inicial.

**2.3b** Se `s` ou `amostra`:

1. Para cada thread, pegar primeiras 2-3 mensagens (não o thread inteiro)
2. **Aplicar PII redaction**: importar `~/atende-ai/lib/pii_redactor.py`, função `redact(text)` em cada mensagem. Confirmar que `result.counts` tem valores > 0 antes de prosseguir (sanity check).
3. Se `amostra`: aplicar `~/atende-ai/lib/threshold_cluster.py`, função `sample_representatives(texts)` para reduzir a ~50 representantes por similaridade Jaccard.
4. Construir prompt: "Aqui estão N threads de chamados (PII redacted). Identifique tipos de chamado comuns. Para cada tipo proposto: nome em português, 3-5 palavras-chave do título/relay, frequência aproximada, exemplo redacted."
5. Chamar LLM via Task tool com agente `general-purpose` que processa e retorna lista de tipos candidatos JSON.

**2.4** Para cada tipo candidato proposto pelo LLM, mostrar ao usuário:
```
Tipo candidato #N: "{nome}"
  Palavras-chave detectadas: {keywords}
  Frequência: {freq} ocorrências em {período}
  Exemplo (redacted): "{exemplo}"

Aceitar? [s = aceita / e = editar / d = descartar]
```

Coletar tipos aceitos em `types_candidatos[]`.

---

## FASE 3 — Entrevista de bloqueadores (~15 min)

**3.1** Para CADA tipo aceito na Fase 2 (ou se a lista estiver vazia, perguntar "Quais tipos de chamado você atende? Liste em ordem de frequência"):

Para cada tipo:
- "Tipo: **{nome}**. Confirma as palavras-chave: {keywords}? Quer adicionar/remover alguma?"
- "Esse tipo executa alguma operação automatizada? [s/n]"
  - Se s: "Qual MCP/tool? (escolha da whitelist da Fase 1.6 ou diga 'manual' se for orientação ao solicitante)"
  - Se s: "Quais parâmetros são obrigatórios? (ex: user_uuid, workspace_id, role)"
- "Esse tipo tem risco? [safe = sem efeito grave / sensitive = altera dados visíveis / destructive = irreversível]"
  - Se `destructive`: explicar que vai exigir frase literal de confirmação na Pausa 2.
- "Há alguma situação que bloqueia esse tipo? (ex: conta suspensa, assinatura ativa)" → vira `blocker`.
- "Quem é acionado se esse tipo falhar/escalar? (identificador no canal — user_id, e-mail ou nome)" → vira `escalation_to`.
- "Mensagem padrão de sucesso para o solicitante?" → vira `response_template[language_default]`.
  - Orientar: use `{{ requester_address }}` para endereçar o solicitante (adaptado automaticamente ao canal).

**3.2** Perguntas globais:
- "Há pessoas autorizadas para alguma operação específica? (ex: 'só Fulano pode fazer X')" → `authorizations[]`
- "Há matriz de escalação por sintoma? (ex: bug de billing → time financeiro)" → `escalation_matrix[]`
- "Já tem queries SQL conhecidas para buscar IDs (e-mail, nome, UUID)?" → `entity_lookups[]`

**3.3** Quaisquer perguntas opcionais que o usuário pular vão para `refinement_backlog[]` com `priority: low`.

---

## FASE 4 — Geração + validação + ativação

**4.1** Renderizar YAML completo a partir das fases 1-3.

**4.2** Salvar em `~/atende-ai/areas/<name>.yaml`.

**4.3** Validar:
```bash
bash ~/atende-ai/scripts/validate.sh ~/atende-ai/areas/<name>.yaml
```

Se falhar → mostrar erro detalhado, perguntar o que corrigir, reabrir entrevista no campo problemático. Loop até passar.

**4.4** Simulação seca (opcional, recomendado):
- Para cada `type` com `risk_level: safe`, simular execução com fixture se houver
- Mostrar se algum template tem variável Jinja2 não resolvida

**4.5** Commit (opcional):
```bash
cd ~/atende-ai && git add areas/<name>.yaml && \
  git commit -m "feat(<name>): initial setup via /atende-criar"
```

**4.6** Avisar:
```
✅ Skill `/atende <name>` pronta para uso!

📊 Resumo:
   • {N} tipos configurados
   • Canal: {channel.type} ({channel.source_production})
   • {M} entity_lookups
   • {K} itens em refinement_backlog (perguntas opcionais que você pulou)

Próximos passos:
   1. Resolva 1 chamado real: /atende <name> <URL_de_um_chamado>
   2. Faça a varredura completa do canal: /atende-varredura <name>
   3. Quando quiser refinar com base nos logs: /atende-refinar <name>
```

---

## REGRAS QUE NUNCA PODEM SER QUEBRADAS NESTE WIZARD

1. **Nunca aceitar e-mail claramente inválido** (sem @, sem domínio)
2. **Nunca salvar YAML sem passar pela validação do schema**
3. **Nunca chamar LLM com texto não-redacted** na Fase 2
4. **Nunca sobrescrever** `areas/<name>.yaml` existente sem confirmação explícita
5. **Nunca incluir `<users/all>`** em escalation_matrix ou response_template
6. **Nunca configurar tool fora da whitelist** declarada em 1.6
7. **Nunca fixar `email` no YAML** (sempre `{{ operator_email }}` runtime)
8. **Nunca declarar `risk_level: destructive`** sem que o usuário confirme explicitamente que entendeu
9. **Nunca usar `channel.tools.send` no canal de produção durante o wizard** — toda pré-visualização vai para `channel.source_test`
