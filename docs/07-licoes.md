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

## 6. Identificador que voce nao sabe ler e canal, nao automacao

**Contexto:** investigar "quem alterou" um registro no audit log.

**Armadilha:** o campo de autoria tem formatos diferentes por origem (e-mail para acao interna, UUID para usuario final, nome de canal/integracao para envios de terceiros). Diante de um valor desconhecido, concluir "foi um processo interno da plataforma" ou "nao foi uma pessoa".

**Correto:** se o identificador nao resolve para e-mail ou UUID existente, a resposta e "nao identificado — veio por um canal de envio" e escalar para o dono da integracao. Ao investigar, **nao trunque** os campos de valor/extra (o remetente costuma estar depois do corte). Velocidade ou volume de eventos nao prova automacao.

**Consequencia de ignorar:** a resposta acusa a propria organizacao de alterar dados do cliente e vira incidente falso.

---

## 7. IDs de sistemas diferentes colidem — confira o nome dentro do arquivo

**Contexto:** baixar arquivo de uma pessoa (PDF, export) por um identificador numerico.

**Armadilha:** sistemas legado e atual usam faixas numericas que se sobrepoem. O caminho monta com o ID "errado", o download funciona e entrega o arquivo de **outra pessoa**.

**Correto:** valide o ID na fonte que indexa o armazenamento (o legado, se e ele que nomeia as pastas) e **abra o arquivo e leia o nome** antes de entregar. E o unico passo que pega o erro.

---

## 8. `success: true` nao prova que a operacao fez algo

**Contexto:** qualquer tool de escrita.

**Armadilha:** tools que respondem sucesso com input invalido (ex.: um codigo de acesso no lugar do UUID) e nao alteram nada. O operador comunica "feito" e o solicitante volta 24h depois.

**Correto:** depois da propagacao, confira o efeito no dado (contagem antes x depois, flag do registro). Reporte a cobertura real ("23 de 25 voltaram; 2 tinham sido desativados em outro momento").

---

## 9. Post automatico e pista, nao fato

**Contexto:** canais onde um bot ou outro agente posta roteamento/"investigacao previa" na thread.

**Armadilha:** repetir os numeros do post automatico na resposta. Ninguem revisa esse post antes de ir ao ar; contagens erradas ("todos completos" com 18 de 50 vazios) sao comuns.

**Correto:** use como pista de entidades e remeca todo numero. O pedido real e as aprovacoes estao nas respostas humanas da thread.

---

## 10. Prova negativa fraca — "a query deu zero" nao libera

**Contexto:** blockers do tipo "se a query de risco voltar vazia, pode executar".

**Armadilha:** a combinacao de filtros nunca ocorre na base (ex.: status ativo + pago com entidade desativada da zero em 100% dos casos, com ou sem problema). O blocker passa sempre.

**Correto:** antes de confiar num zero, verifique se o filtro ja retornou linha alguma vez. Procure o sinal que discrimina (outro status, como cancelado+pago) e complemente com evidencia positiva — onde o dado ESTA.

---

## 11. Duplicata x legitima: conte o conteudo antes de perguntar

**Contexto:** a busca devolve dois registros homonimos (dois grupos, duas contas, dois cadastros da mesma pessoa).

**Armadilha:** perguntar ao operador "qual dos dois?" de cara, ou escolher o mais recente.

**Correto:** conte o conteudo/uso de cada lado (itens, compras, membros). A legitima costuma ser a que tem dados; a vazia e a duplicata. Pergunte so se as duas tiverem conteudo. Em duplicata de pessoa, sobrevive o cadastro com historico (compras), nao o mais novo — e a causa costuma ser e-mail quase igual (`@gmail.com` x `@gmail.com.br`).

---

## 12. Espelho atrasado e limite de linhas

**Contexto:** consultas em replica/data lake e tools SQL com teto de linhas.

**Armadilha:** concluir "nao aconteceu" porque o espelho ainda nao recebeu o evento (ja ficou horas parado), ou tirar conclusao de uma lista cortada no limite da tool.

**Correto:** cheque `MAX(updated_at)` da tabela antes de afirmar ausencia; agregue em vez de listar cru. E nao re-execute uma operacao que retornou sucesso so porque o espelho ainda nao reflete.

---

## 13. Texto de ajuda da tool fica defasado

**Contexto:** tools com uma operacao "ajuda"/"help" que descreve os parametros.

**Armadilha:** confiar no texto de ajuda — ele continua citando parametro renomeado e operacao com typo antigo, e o servidor passa a rejeitar.

**Correto:** o schema da tool vale mais que o texto. Divergencia encontrada vira `# ARMADILHA:` no tipo do YAML.

---

## 14. Chamadas paralelas perdem em silencio por cota

**Contexto:** lote via CLI de funcao serverless ou API com cota por minuto.

**Armadilha:** disparar N chamadas em paralelo com stderr descartado. Parte bate na cota (429) e some sem aviso — num caso real, 96 de 121.

**Correto:** prefira a tool que aceita array (uma chamada). Sem isso, sequencial com intervalo e stderr visivel; confira a contagem no fim.

---

## 15. Mencao some em silencio para quem nao e membro direto

**Contexto:** Google Chat via API.

**Armadilha:** `<users/ID>` e removida sem erro se a pessoa entrou no espaco via grupo. O operador acha que notificou.

**Correto:** confira membership direta antes; quando importa, o operador cola a mensagem com `@Nome` manual. Nunca `<users/all>`.

---

## 16. Resposta curta e franca vence resposta burocratica

**Contexto:** rascunho da resposta ao solicitante.

**Armadilha:** apos acumular regras, o rascunho vira checklist: varios topicos, marcacao de terceiros para tarefas, cobranca de aprovacao de lideranca em todo pedido.

**Correto:** responda so o que foi perguntado. Operacao possivel mas de pouco efeito → diga isso e pergunte "quer que alteremos mesmo assim?". Exigencias de alinhamento sao do operador decidir, nao do template.

---

## 17. Pedido de registro de acesso nunca se atende pelo canal

**Contexto:** "qual IP acessou", "historico de login", "localizacao", pedido de advogado ou orgao publico.

**Correto:** nao buscar nem entregar. Encaminhar ao juridico/compliance — esse dado so sai por processo formal. E nao afirme o que desativar ou excluir faz com os dados sem verificar no sistema (ou sem o `response_template` do tipo dizer): muitos sistemas so desativam, outros apagam de fato.

## Como adicionar novas licoes

Ao encontrar um comportamento inesperado em producao:
1. Documente aqui (uma licao = uma secao neste arquivo)
2. Adicione um comentario `# ARMADILHA:` no YAML do tipo correspondente (`areas/<area>.yaml`)
3. Se for recorrente, adicione um blocker no tipo para prevenir automaticamente

Use `/atende-refinar <area>` para incorporar licoes diretamente no YAML da area.
