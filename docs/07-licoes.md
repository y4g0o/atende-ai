# Licoes aprendidas em producao

Padroes contra-intuitivos descobertos operando canais reais com o atende-AI.
Cada item e uma armadilha que ja causou execucao errada ou resposta incorreta ao solicitante.

---

## 1. Completude de conteudo -- nao confie em campos de metadata "placeholder"

**Contexto:** tipos que verificam se um registro esta completo antes de executar a operacao principal.

**Armadilha:** verificar completude procurando a palavra `placeholder` (ou similar) em campos de metadata.
Muitos sistemas armazenam um valor de placeholder nos metadados do slot MESMO quando o conteudo real
ja foi preenchido. Registros inteiramente completos aparecem como incompletos -- falso-positivo que
bloqueia a operacao sem motivo.

**Correto:** o conteudo real fica em colunas separadas e especificas:
- Conteudo texto -> coluna de valor textual (ex: `value`, `content`, `text_value`)
- Conteudo midia -> coluna de referencia de arquivo (ex: `media_ref`, `file_url`, `media_target`)

Verifique se ESSAS colunas estao vazias -- nao o metadata.

**Consequencia de ignorar:** engine recusa executar em registros completos, chamado nao e resolvido.

---

## 2. Campos de UUID -- nunca use e-mail onde o sistema espera UUID

**Contexto:** operacoes que alteram responsavel/dono de uma entidade (conta, workspace, grupo, etc.).

**Armadilha:** passar o e-mail do responsavel nos campos que esperam UUID do usuario.
O servidor retorna HTTP 500 sem mensagem de erro util -- dificulta muito o diagnostico.

**Correto:** busque o UUID da pessoa pelo e-mail na tabela de entidades ANTES de montar
o payload. Os campos que esperam UUID geralmente terminam em `_uuid`, `_id`, ou sao nomeados
como `owner`, `user`, `new_owner`, `operator` -- todos esperam UUID, nunca e-mail.

**Consequencia de ignorar:** operacao falha com 500, engine precisa fazer busca adicional,
round-trip desnecessario.

---

## 3. Busca por entidade -- nome amplo primeiro, filtros depois

**Contexto:** encontrar o UUID de um usuario/conta/workspace pelo nome mencionado no chamado.

**Armadilha:** filtrar por tipo/workspace/status logo na primeira query para "restringir o resultado".
O nome no sistema pode ter grafia diferente do chamado (abreviacao, acento, maiuscula).
Filtrar por multiplos criterios ao mesmo tempo e facil de retornar zero resultados mesmo a entidade
existindo.

**Correto:** busque primeiro com nome amplo (substring, sem filtros adicionais).
Use o resultado para confirmar a grafia exata e o UUID. Aplique filtros adicionais apenas
se a query retornar mais de ~10 resultados ambiguos.

**Consequencia de ignorar:** query retorna vazio, engine para desnecessariamente para
perguntar ao operador, atraso no atendimento.

---

## 4. Validacao de estado antes de executar

**Contexto:** qualquer operacao que habilita ou desabilita uma entidade.

**Armadilha:** executar a operacao sem verificar o estado atual da entidade.
- Pedido para reativar + entidade ja esta ativa = provavelmente e a entidade errada
- Pedido para desativar + entidade ja esta inativa = idem

O sistema pode executar sem erro mesmo no estado errado, alterando a entidade incorreta.

**Correto:** sempre consulte o estado atual (ex: `is_active`, `is_enabled`, `status`) ANTES de
executar. Se o estado ja e o esperado, pare e confirme com o operador: pode ser a entidade
errada, um chamado duplicado, ou um caso de borda (ex: a entidade e duplicata intencional).

**Consequencia de ignorar:** operacao executada na entidade errada, sem mensagem de erro,
requer rollback manual.

---

## 5. Chamados antigos vs. reabertura

**Contexto:** threads no canal de suporte que tem historico de resolucao.

**Armadilha:** assumir que todo thread e um chamado novo. Um thread pode ser reabertura
(solicitante voltou com o mesmo problema) ou agradecimento (thread encerrado com confirmacao).
Executar de novo um chamado ja resolvido pode desfazer o trabalho anterior.

**Correto:** antes de classificar o tipo e executar, verifique se ha mensagem de fechamento
no thread (emoji de check, frase de conclusao do operador, confirmacao do solicitante).
Se sim, pergunte ao operador se e reabertura ou se o thread foi aberto por engano.

---

## Como adicionar novas licoes

Ao encontrar um comportamento inesperado em producao:
1. Documente aqui (uma licao = uma secao neste arquivo)
2. Adicione um comentario `# ARMADILHA:` no YAML do tipo correspondente (`areas/<area>.yaml`)
3. Se for recorrente, adicione um blocker no tipo para prevenir automaticamente

Use `/atende-refinar <area>` para incorporar licoes diretamente no YAML da area.
