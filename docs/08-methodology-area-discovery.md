# Metodologia — Aprender uma area nova

> **Como ensinar uma skill nova a partir de um canal Google Chat com historico.**
> Esse documento captura o **framework** para refinar areas de atendimento que pode ser aplicado
> a qualquer canal: suporte, backoffice, comercial, financeiro, etc.

---

## Problema

Quando uma area quer uma skill no `atende-AI`:
- A pessoa nao sabe descrever todos os tipos de chamado que recebe
- Padroes e regras de negocio estao implicitos (na cabeca do operador)
- O historico do canal tem muitos casos, mas e muito grande para ler tudo
- Entrevistas longas cansam; perguntas abstratas nao destravam respostas concretas

**Como extrair conhecimento operacional sem 2h de workshop?**

---

## Framework -- 4 fases

```
+-------------------------------------------------------------+
|  FASE 1 -- Mapping (a partir do conhecimento atual)         |
|  Catalogar tipos conhecidos no YAML inicial (best guess)    |
+-------------------------------------------------------------+
                            |
                            v
+-------------------------------------------------------------+
|  FASE 2 -- Search-based regression                          |
|  Buscar chamados reais no historico via search_messages.    |
|  Para cada tipo, achar 1-3 casos e simular o classifier.   |
|  Identificar gaps (regra implicita, ambiguidade, batch).    |
+-------------------------------------------------------------+
                            |
                            v
+-------------------------------------------------------------+
|  FASE 3 -- Discovery interviews                             |
|  Perguntas direcionadas para humanos, baseadas em gaps      |
|  CONCRETOS (nao abstratos). Mensagens curtas, 2-3 perguntas |
|  por pessoa, com referencia ao caso real.                   |
+-------------------------------------------------------------+
                            |
                            v
+-------------------------------------------------------------+
|  FASE 4 -- Continuous refinement                            |
|  Cada execucao nova e dado pra refinar. /atende-refinar     |
|  detecta padroes novos e propoe atualizacoes.               |
+-------------------------------------------------------------+
```

### Por que essa ordem importa

- **Fase 1 sem Fase 2** → YAML cheio de tipos que ninguem usa (overengineering)
- **Fase 2 sem Fase 1** → analise sem norte; gasta tokens a toa
- **Fase 3 sem Fase 2** → perguntas abstratas geram respostas vagas ("ah, depende")
- **Fase 4 sem feedback loop** → drift; YAML envelhece

---

## Fase 1 -- Mapping inicial

### Inputs necessarios
- Acesso ao canal Google Chat
- Acesso ao MCP/API que executa as operacoes da area
- 1 entrevista curta (15 min) com o dono da area para listar tipos conhecidos

### Como conduzir
1. Use `/atende-criar` (fluxo formal) **OU**, se nao der, faca manualmente:
   - Liste os 5-10 tipos que o dono lembra de cabeca
   - Para cada um: `keywords[]`, `operation.tool` (se houver), `response_template`
2. Salve como `areas/<area>.yaml` valido contra `schemas/atende.v1.json`
3. Marque tipos com pouca confianca como `risk_level: safe` ou `manual:escalate`

### Heuristicas

- Comece com **3-5 tipos** (nao 20). Refinar > mapear tudo upfront
- Se o dono diz "ah, isso quase nunca acontece" → nao vire tipo agora; vai pra `refinement_backlog`
- Tipos com `risk_level: destructive` SEMPRE exigem confirmacao literal — nao otimizar

### Output da Fase 1

`areas/<area>.yaml` minimo viavel, valido pelo schema.

---

## Fase 2 -- Search-based regression (a parte mais valiosa)

### O insight critico

**Nao pergunte ao humano o que ele faz. Procure o que ele ja fez.**

O canal Google Chat tem **anos de chamados resolvidos**. Cada um e um caso de teste real. Validar a skill contra eles e mais barato que entrevistar 10 pessoas.

### Como conduzir

#### Passo 2.1 -- Identificar palavras-chave por tipo

Para cada `type` do YAML, liste 3-5 palavras-chave que apareceriam no chamado:

```
#1 Reset senha   → ["nao consigo entrar", "senha errada", "bloqueado"]
#3 Reativar conta → ["conta suspensa", "acesso bloqueado", "conta inativa"]
#5 Bug billing   → ["cobranca errada", "fatura duplicada", "valor incorreto"]
```

#### Passo 2.2 -- Buscar em paralelo

Use `mcp__claude_ai_Google_Chat__search_messages` para cada tipo:

```python
# Pseudocodigo
for tipo in YAML.types:
    results = search_messages(
        conversationId=area.channel.source_production,
        keywords=tipo.keywords,
        orderBy="CREATE_TIME_DESC",
        pageSize=5
    )
    if not results: tipo.search_status = "no_recent_cases"
```

**Otimizacao**: rode todas as buscas no **mesmo turno** (paralelo via N tool_calls em uma mensagem).

#### Passo 2.3 -- Para cada thread encontrado

1. `list_messages(threadId)` para ler thread completo
2. **Simular o classifier** (mesmo prompt do `atende-classifier.md`):
   - Extrair `requester`, `entities`, `lang`, `urgent`, `reopen_suspected`
   - Identificar `missing_info`
3. **Comparar** com o que aconteceu no thread real:
   - Quem resolveu?
   - Que operacao foi feita?
   - Que regras implicitas apareceram?
4. **Classificar** o veredito:
   - PASS -- skill teria feito o mesmo
   - PASS com observacao -- funciona mas revela regra/edge case
   - GAP -- operacao nao tem MCP / regra desconhecida

#### Passo 2.4 -- Documentar achados

`tests/regression-results-YYYY-MM-DD.md` com:
- 1 secao por caso (URL do thread, output simulado do classifier, veredito, observacoes)
- Sumario final com tabela e aprendizados acionaveis

### Padroes que aparecem em quase toda area (anti-padroes/edge cases)

Documente esses como `conventions` em `globals.yaml` para reuso:

| Padrao | Como detectar | Implicacao |
|---|---|---|
| **Relay vazio** | Mensagem do triador e so uma @mencao sem texto | Engine precisa marcar `missing_info` e Pausa 1 |
| **Chamado misto** | Mais de 1 tipo num thread (#1 + #3, #2 + #6) | `types: [1, 3]`, executar em ordem de dependencia |
| **Ambiguidade de identidade** | 2 cadastros / 2 entidades com nomes parecidos | Pausa 1 obrigatoria -- listar opcoes |
| **Operacao em batch** | Lista de IDs em vez de 1 entidade | YAML precisa permitir `entities[]` array |
| **Tipo como correcao** | "Reverter isso que foi feito por engano" | Diferente de operacao proativa -- perguntar antes |
| **Queixa ≠ operacao** | "Sistema ficou lento" -- pode nao ter operacao a fazer | Engine deveria classificar como investigacao |
| **`reopen_suspected`** | Mensagem com checkmark ou "obrigada" no fim | Engine deve perguntar se e reabertura antes de re-executar |
| **Sender = Deleted User** | Pessoa saiu da organizacao | Lookup falha graciosamente, sem recriar |

### Output da Fase 2

Documento `regression-results-YYYY-MM-DD.md` com PASS/FAIL/observacoes + lista de **gaps concretos** que viram perguntas na Fase 3.

---

## Fase 3 -- Discovery interviews

> **Esta fase e executavel automaticamente via `/atende-varredura <area>` (PASSO 3).**
> O script implementa o template e o mapeamento gap→pessoa descritos abaixo.
> Rodando `/atende-varredura` voce nao precisa fazer a Fase 3 manualmente.

### O insight critico

**Pergunta abstrata gera resposta vaga. Pergunta com caso real gera resposta acionavel.**

Errado: "Como voce lida com chamado de reset de senha?"
Correto: "No caso da conta [REDACTED], voce foi acionado diretamente sem texto. E porque conversaram em outro canal antes?"

### Como rodar de forma executavel

```bash
# Roda varredura completa: scan → identify → montar perguntas → entregar fila
/atende-varredura <area>
```

O PASSO 3 do `/atende-varredura`:
1. Detecta gaps (tipos sem operation/blocker/escalation, tipos desconhecidos, backlog em aberto)
2. Mapeia cada gap para a pessoa correta (tabela abaixo)
3. Rascunha 2-3 perguntas ancoradas em caso real (com PII redigida)
4. Mostra rascunhos para aprovacao antes de qualquer envio
5. Envia via `channel.tools.send` (email = rascunho; chat = mensagem direta)
6. Registra as perguntas no `refinement_backlog` do YAML

### Estrutura da mensagem (template — usado pelo /atende-varredura)

```
Oi <NOME>! To refinando o runbook do <AREA> (atende-AI). Posso te perguntar <N=2-3> coisas?

1. **<TOPICO CONCRETO 1>**: <caso de referencia ou observacao>. <pergunta direta>?
2. **<TOPICO CONCRETO 2>**: <pergunta direta>?
3. <Opcional, mais aberto>

Obrigado!
```

### Principios

- **Maximo 3 perguntas por pessoa** -- qualquer mais e checklist, nao conversa
- **Cada pergunta cita um caso real ou um trecho do YAML** -- ancorada em algo concreto
- **Tom direto** mas amigavel
- **Sempre de opcao de "manda mais"** -- se a pessoa estiver disposta, ela elabora
- **Nao pergunte coisas que da pra responder com BigQuery/audit_log** -- economize tempo deles

### Mapeamento gap → pessoa (implementado no /atende-varredura PASSO 3.1)

Para cada gap da Fase 2, decida quem destrava:

| Tipo de gap | Pessoa tipica |
|---|---|
| Regra tecnica (lookup, conversao) | Tech lead da area |
| Whitelist desatualizada | Owner da operacao |
| Padrao do relay | Pessoa que faz triagem (relay) |
| Operacao sem MCP | Quem executa manualmente |
| Escalation desatualizada | Quem aparece no caso especifico |
| Edge case raro | Quem aparece no caso especifico |

### Output da Fase 3

Mensagens prontas para enviar. Conforme respostas chegam, atualizar YAML + `refinement_backlog` + glossario.

### Variacao -- area totalmente desconhecida (sem regression nem nomes ainda)

Quando voce esta comecando do zero numa area sem historico analisado e sem pessoas mapeadas,
Fase 1 e Fase 3 se MISTURAM. As perguntas precisam:

- Ser mais **abertas** (mapping + discovery juntos)
- Segmentar por **papel** (dono, atendente, solicitante, apoio tecnico), nao por pessoa
- Pedir os "5 tipos mais comuns" abertamente, em vez de validar uma lista pre-feita
- Reservar perguntas sobre edge cases / regras implicitas para uma v2 *depois* da primeira rodada de respostas

**Anti-padrao**: tentar fazer perguntas cirurgicas sem ter feito regression -- gera friccao e respostas vagas.

**Padrao correto** (sequencia iterativa):
1. **v1 perguntas abertas** (mapping) → operador envia para 1-2 pessoas-ancora da area
2. **Recebe respostas** → rodar regression com keywords novas
3. **v2 perguntas cirurgicas** (discovery) → operador envia para mais gente, com casos reais

---

## Fase 4 -- Continuous refinement

### Mecanismo

`/atende-refinar <area>` (implementado em `engine/atende-refinar.md`):
- Le audit_log dos ultimos N dias
- Identifica padroes: tipos com falha alta, p50 aprovacao alto, tipos nunca usados, `confidence: low` recorrente
- Propoe mudancas com diff visivel
- Sempre exige aprovacao antes de comitar

### Sinais que disparam refinamento

1. **Failures > 20% num tipo** → blocker faltando OU keyword classifica errado
2. **p50 aprovacao > 60s** → template nao tem variaveis suficientes (operador edita muito)
3. **Tipo nunca executado em 30d** → candidato a remover ou consolidar
4. **`confidence: low` recorrente** → keywords precisam ajuste
5. **`reopen_suspected: true` recorrente** → solicitante nao esta confirmando fechamento
6. **Padrao novo identificado pelo LLM** → adicionar como tipo novo (mediante aprovacao)

### Cadencia sugerida

- **Semanal** (primeiras 4 semanas apos go-live de uma area): rodar `/atende-refinar`
- **Mensal** (regime estavel): rodar `/atende-refinar` + olhar dashboard de audit

---

## Principios universais (aplicam-se a qualquer area futura)

1. **Comece pequeno, refine com uso real.** YAML inicial de 3-5 tipos > YAML de 20 tipos nao-validados.

2. **Historico e ouro.** Anos de chamados resolvidos sao o melhor dataset de validacao. Use `search_messages` antes de entrevistar humanos.

3. **PII redaction e nao-negociavel.** Qualquer analise automatizada do historico passa por `lib/pii_redactor.py` antes de chegar a um LLM externo.

4. **Cada gap concreto vira uma pergunta.** Nao pergunte abstrato; cite o caso.

5. **Pessoas certas sao as que aparecem nos casos.** O grafo de "quem foi acionado nos threads" e melhor que organograma formal.

6. **Mensagens curtas sao respondidas.** 3 perguntas em 80 palavras > 1 questionario de 20.

7. **Comportamento defensivo > comportamento inteligente.** Engine prefere bloquear/perguntar do que adivinhar.

8. **Refinement_backlog e normal.** Skill madura nao significa "perfeita" -- significa "sabe o que ainda nao sabe".

---

## Metricas que indicam que uma area esta "pronta"

Use para decidir se vale promover uma area de stub para producao:

- >= 70% dos tipos catalogados tem caso real no historico
- >= 80% de PASS na regression (sem GAPs criticos)
- Pessoas-chave de escalacao responderam discovery
- Workshop com dono ocorreu OU dono editou o YAML diretamente
- Templates de resposta passaram por revisao da area
- `risk_level: destructive` confirmados com `authorizations[]`

---

## Anti-padroes a evitar

- Mapear 20 tipos baseado em "achismo" -- gera YAML inflado que ninguem valida
- Entrevistar antes de buscar -- perde a chance de fazer perguntas concretas
- Marcar tudo como `risk_level: safe` para simplificar -- primeiro erro destrutivo apaga confianca
- Copiar templates de outra area sem revisar tom/idioma
- Esperar 100% antes de liberar -- bloqueia adocao
- Ignorar gaps "raros" -- eles voltam na hora errada
