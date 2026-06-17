# Governanca

## Principios

1. **Aprovacao humana e nao-negociavel.** Engine sempre pausa antes de executar e antes de enviar.
2. **Whitelist de tools por area.** YAML declara `tools_allowed[]`. Engine recusa qualquer tool fora da lista.
3. **Auditoria imutavel.** Toda execucao grava em BQ com hash do payload.
4. **Espacos de teste isolados.** YAML declara `space_test`. Engine bloqueia `send_message` para outros espacos em modo teste.
5. **E-mail do operador e runtime.** Operacao rastreada por quem executou, nao por configuracao estatica.
6. **PII nunca vaza em LLM externo.** Pipeline obrigatorio de redaction antes de qualquer chamada que processe historico.

## Guard-rails hardcoded

| Guard | Onde |
|---|---|
| Pausa 2 (aprovacao execucao) | `engine/atende.md` Passo 6 |
| Pausa 3 (aprovacao envio) | `engine/atende.md` Passo 10 |
| Whitelist tools | `engine/atende.md` Passo 0 (carregamento) |
| PII redaction | `lib/pii_redactor.py` (chamado sempre antes de LLM) |
| Audit log | `engine/atende.md` Passo 8 (nao condicional) |
| Espaco teste | `engine/atende.md` Passo 10 (valida `threadId` vs `space_production`) |
| E-mail runtime | `engine/atende.md` Passo 0 (`{{ operator_email }}` injetado) |
| Risk level destructive | `engine/atende.md` Passo 6 — exige confirmacao literal |

## Operacoes destrutivas

Tipos marcados `risk_level: destructive` no YAML requerem:
1. Pausa 2 padrao
2. Frase de confirmacao literal — nao basta "sim"
3. Exemplo: `CONFIRMO EXCLUIR [NOME] ([UUID])`

Operador erra a frase → engine recusa e refaz Pausa 2.

## RBAC (Role-Based Access Control)

Versao MVP: simples, baseado em `authorizations[]` no YAML.

```yaml
authorizations:
  - rule: "tipo #8 (excluir-conta)"
    allowed_only: ["Compliance Officer", "Tech Lead"]
```

Engine no Passo 4:
- Le `requester` da classificacao (User ID + nome)
- Cruza com `authorizations[]`
- Se nao autorizado → bloqueia e instrui a escalar

Versao futura: RBAC por arquivo `permissions.yaml` separado, herdado de `globals`.

## CODEOWNERS (Git)

`CODEOWNERS` no repo define quem aprova mudancas por arquivo:

```
# Owners — substitua pelo seu usuario Git
/areas/             @seu-usuario-git
/globals.yaml       @seu-usuario-git
/engine/            @seu-usuario-git
/schemas/           @seu-usuario-git
```

Mudanca em YAML de area so e mergeada com aprovacao do dono.

## Auditoria

Tabela `REPLACE_AUDIT_PROJECT.atende_audit.executions`:

| Coluna | Tipo | Descricao |
|---|---|---|
| `execution_id` | STRING | UUID unico da execucao |
| `timestamp` | TIMESTAMP | Hora UTC |
| `area` | STRING | nome da area YAML |
| `type_id` | INT | ID do tipo no YAML |
| `operator_email` | STRING | Quem executou (runtime) |
| `requester_id` | STRING | User ID do solicitante |
| `tool_name` | STRING | MCP/tool chamada |
| `payload_hash` | STRING | SHA256 do payload (PII redacted) |
| `approved_at` | TIMESTAMP | Quando operador aprovou Pausa 2 |
| `sent_at` | TIMESTAMP | Quando operador aprovou Pausa 3 |
| `result_status` | STRING | success / partial / failed |
| `result_message` | STRING | erro ou ID do retorno (nao dados de negocio) |
| `thread_url` | STRING | Link do chamado |

Query exemplo:
```sql
SELECT operator_email, COUNT(*) AS execs, COUNTIF(result_status='failed') AS fails
FROM `REPLACE_AUDIT_PROJECT.atende_audit.executions`
WHERE area = 'minha-area' AND timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY 1 ORDER BY 2 DESC
```

## Versionamento

- YAML em Git, branch `main`, tag por versao (`v0.1.0`, `v0.2.0`)
- Engine carrega versao declarada no YAML (`schema: atende.v1`)
- Rollback: `git revert <commit>` + `/atende-sync`

## Rollback de operacao executada

**Nao ha auto-rollback** no MVP. Auditoria registra; reversao e manual via:
- MCP inverso (ex: desabilitar para reverter habilitar)
- Admin console web
- Comando CLI direto

Issue para automacao futura: depende de modelagem de "operacao inversa" por tipo.
