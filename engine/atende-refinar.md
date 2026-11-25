---
description: Aprendizado contínuo — propõe refinamentos para uma área baseado em audit log e refinement_backlog
allowed-tools:
  - mcp__claude_ai_Google_Cloud_BigQuery__execute_sql_readonly
  - Bash
  - Read
  - Write
---

# `/atende-refinar <area>` — Aprendizado contínuo

Você refina uma área existente do `atende-AI` baseado em (1) audit log de execuções reais e (2) `refinement_backlog` do YAML.

**Princípio:** skill começa simples e melhora com uso real. Cada execução é dado para refinar.

---

## PASSO 0 — CARREGAR

**0.1** Receber `<area>` em `$ARGUMENTS`. Erro se não passou.

**0.2** Carregar `~/atende-ai/areas/<area>.yaml`. Validar contra schema. Se inválido, abortar.

**0.3** Capturar operator_email runtime (mesmo padrão do `/atende`).

---

## PASSO 1 — ANÁLISE DE AUDIT LOG

Consultar últimas 50 execuções da área. Duas fontes possíveis:

**1a. Tabela BigQuery (se já existe):**
```sql
SELECT type_id, tool_name, result_status, COUNT(*) as n,
       COUNTIF(result_status = 'failed') as failures,
       COUNTIF(result_status = 'partial') as partials,
       APPROX_QUANTILES(TIMESTAMP_DIFF(sent_at, approved_at, SECOND), 100)[OFFSET(50)] as median_seconds
FROM `REPLACE_AUDIT_PROJECT.atende_audit.executions`
WHERE area = '<area>' AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3
ORDER BY n DESC
```

**1b. Fallback local (`~/atende-ai/audit-local.jsonl`):**
```bash
grep '"area":"<area>"' ~/atende-ai/audit-local.jsonl | tail -50
```

Agrupar por `type_id` e calcular: total, failures, partials, p50 tempo de aprovação.

---

## PASSO 2 — IDENTIFICAR PADRÕES PARA REFINAR

Mostre um relatório:

```
📊 Relatório de uso — <area> (últimos 30 dias):

Tipo #X — {nome}: {n} execuções, {failures} falhas ({pct}%), p50 aprovação {sec}s
Tipo #Y — {nome}: ...
```

Para cada anomalia (failures > 20% OR p50 aprovação > 60s OR partials > 0):
- Marcar como **candidato a refinar**

Critérios heurísticos de refinamento:
- **Failures > 20%**: provavelmente blocker faltando ou keyword classifica errado
- **p50 aprovação > 60s**: provavelmente template não tem variáveis o suficiente (operador edita muito)
- **Tipo nunca executado em 30d**: candidato a remoção/consolidação
- **Tipo classificado com `confidence: low` recorrente**: keywords precisam ajuste

---

## PASSO 3 — APRESENTAR REFINEMENT_BACKLOG

Mostrar perguntas pendentes do YAML (`refinement_backlog[]`):

```
📋 Backlog de refinamentos:
1. [low] {question} (registrado em {date})
2. [medium] {question}
3. ...

Quer resolver algum agora? (número, ou 'pular')
```

---

## PASSO 4 — PROPOR MUDANÇAS (LOOP)

Para cada item do Passo 2 ou Passo 3 que o operador escolheu:

**4.1** Mostrar o pedaço atual do YAML relevante.

**4.2** Propor mudança específica:
- "Tipo #X tem {failures} falhas em 30 dias. Quer adicionar blocker `state_is_disabled`?"
- "Template do tipo #Y não menciona `{entity_name}`. Quer adicionar?"
- "Backlog item 3: {question}. Posso adicionar {sugestão}?"

**4.3** Aguardar confirmação. Editar YAML em memória.

**4.4** Após cada mudança aceita, mostrar diff:
```diff
- old line
+ new line
```

---

## PASSO 5 — VALIDAR + COMMIT

**5.1** Validar YAML modificado:
```bash
bash ~/atende-ai/scripts/validate.sh ~/atende-ai/areas/<area>.yaml
```

Se falhar, mostrar erro e voltar ao Passo 4 com a mudança problemática.

**5.2** Mostrar diff final:
```bash
cd ~/atende-ai && git diff areas/<area>.yaml
```

Pedir confirmação para comitar.

**5.3** Lint de PII (obrigatório — o clone pode ser de um repo público):
```bash
bash ~/atende-ai/scripts/check-no-pii.sh
```
Saída diferente de 0 → **não commitar**: mostre o trecho acusado e reescreva a lição sem o dado real (ID, nome de cliente, nome de pessoa). Se o script avisar que não há padrões configurados, diga isso ao operador antes de commitar.

**5.4** Commit:
```bash
cd ~/atende-ai && git add areas/<area>.yaml && \
  git commit -m "refine(<area>): {resumo das mudanças}"
```
Lição geral em `docs/07-licoes.md` segue o mesmo caminho (lint → commit). Nunca faça push sem o operador pedir.

---

## REGRAS

1. **Nunca aceitar mudança que falhe na validação do schema**
2. **Nunca remover blocker `destructive`** sem confirmação literal
3. **Nunca propor mudança em `globals.yaml`** — refinar é só para `areas/<name>.yaml`
4. **Nunca alterar `tools_allowed`** removendo tools que tipos existentes usam
5. **Cada execução de refinar gera commit** — rastreabilidade — e só depois do lint de PII passar
