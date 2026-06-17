# Criar uma area nova

Duas opcoes: **manual** (voce edita o YAML) ou **wizard** (`/atende-criar`).

## Opcao 1 -- Manual (a partir do template)

```bash
cd ~/atende-ai

# Para area de suporte completa (8 tipos com blockers, entity_lookups e escalacao):
cp areas/helpdesk-saas.yaml areas/minha-area.yaml

# Para area minima (1 tipo, ponto de partida rapido):
cp examples/minimal-area.yaml areas/minha-area.yaml

$EDITOR areas/minha-area.yaml
# Siga o cabecalho "=== PREENCHA ESTES VALORES ===" no template

bash scripts/validate.sh areas/minha-area.yaml
```

## Opcao 2 -- Wizard guiado

```bash
/atende-criar
```

Wizard em 4 fases:

### Fase 1 -- Setup tecnico (~5 min)

Engine pergunta:
- E-mail do operador (runtime -- nao persistido)
- Nome da area (kebab-case)
- Owner team / descricao
- Link do espaco Google Chat (producao)
- Idioma padrao
- MCPs disponiveis (engine lista os ativos; voce marca relevantes)

### Fase 2 -- Analise de historico (opcional)

Engine pergunta: "Achei N threads no canal nos ultimos 6 meses. Analisar? (~{T} tokens, ~{S} segundos)"

Se sim:
1. **PII redaction** (`lib/pii_redactor.py`) -- remove e-mails, CPFs, codigos, UUIDs, nomes
2. **Cluster** (`lib/threshold_cluster.py`) -- dedup por similaridade Jaccard (opcional, modo `amostra`)
3. **LLM** extrai tipos candidatos + palavras-chave
4. **Voce valida** cada tipo (descarta/edita/aceita) com evidencia (5 threads exemplo redacted)

### Fase 3 -- Entrevista de bloqueadores (~15 min)

Engine faz apenas perguntas que impedem a skill de funcionar:
- Confirmar palavras-chave, parametros, tool MCP por tipo
- Pessoas autorizadas para operacoes destrutivas
- Matriz de escalacao minima

Perguntas opcionais ("refinamento") viram backlog para depois.

### Fase 4 -- Geracao e ativacao

1. Engine valida YAML contra schema
2. Simulacao seca em fixtures sinteticos
3. Salva `areas/<name>.yaml`
4. Commit automatico (opcional)
5. Skill `/atende <name>` pronta

## Aprendizado continuo (`/atende-refinar`)

Apos cada chamado real, engine pode propor:
> "Vi um padrao que nao esta no YAML: [...]. Adicionar como tipo novo? [s/n]"

Backlog de refinamentos tambem aparece aqui -- resolva quando quiser.

## Checklist minimo para skill funcionar

- [ ] `schema: atende.v1`
- [ ] `area.name`, `area.owner_team`
- [ ] `chat.space_production` (ID real do seu canal)
- [ ] `tools_allowed[]` (minimo: list_messages, send_message do Google Chat)
- [ ] `types[]` (minimo 1, com `keywords[]`, `operation.tool`, `response_template[lang]`)
- [ ] `audit.destination` (projeto BigQuery real)

Tudo acima validado por `schemas/atende.v1.json`. Engine nao inicia sem isso.
