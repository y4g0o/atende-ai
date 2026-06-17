# Glossario — atende-AI

Termos do framework e do dominio de suporte que aparecem nos YAMLs e na configuracao do atende-AI.

## Sistemas (adapte para sua infraestrutura)

| Termo | Definicao |
|---|---|
| **Admin console / painel admin** | Interface web administrativa da sua organizacao. Referenciada em tipos que exigem acao manual no backoffice. Preencha a URL real nos YAMLs de area. |
| **Data warehouse / lakehouse** | Banco ou espelho BigQuery com os dados principais da plataforma. Substitua `REPLACE_PROJECT.REPLACE_DATASET` pelo projeto e dataset reais. |
| **Legado** | Dados historicos/arquivados de periodos anteriores. Substitua `REPLACE_LEGACY_PROJECT` pelo projeto BigQuery legado (se aplicavel). |
| **Storage / bucket** | Armazenamento de arquivos (PDFs, imagens, exports). Substitua `REPLACE_BUCKET` pelo bucket real do Cloud Storage. |
| **MCP de operacoes** | MCP server interno com as tools de operacao da sua org. Substitua `mcp__YOUR_HELPDESK_MCP__*` pelo namespace real. |
| **Audit log** | Destino de auditoria de execucoes. Substitua `REPLACE_AUDIT_PROJECT` pelo projeto BigQuery. |

## Conceitos do framework

| Termo | Definicao |
|---|---|
| **area** | Unidade de configuracao do atende-AI: um arquivo YAML por canal ou dominio de suporte. |
| **type / tipo** | Um padrao recorrente de chamado, com keywords, bloqueadores, operacao e template de resposta. |
| **entity / entidade** | Qualquer objeto com UUID no banco da sua plataforma: usuario, conta, workspace, assinatura, pedido, etc. |
| **entity_uuid** | UUID da entidade. Usado em quase todas as operacoes como identificador primario. |
| **entity_lookup** | Query SQL parametrizada que o engine usa para buscar o UUID de uma entidade a partir de nome, e-mail ou codigo. |
| **blocker** | Condicao que impede a execucao de um tipo: estado incoerente, autorizacao ausente, situacao de risco. |
| **risk_level** | Grau de risco do tipo: `safe` (sem efeito grave), `sensitive` (altera dados visiveis), `destructive` (irreversivel). |
| **refinement_backlog** | Lista de perguntas pendentes sobre a area — preenchidas pelo wizard e resolvidas via `/atende-refinar`. |
| **operator_email** | E-mail de quem executa a operacao. Capturado em runtime, nunca fixado no YAML. |
| **Pausa 2** | Aprovacao obrigatoria antes de qualquer execucao. YAML nao pode desligar. |
| **Pausa 3** | Aprovacao obrigatoria antes de enviar a mensagem de resposta. YAML nao pode desligar. |
| **PII redaction** | Remocao de dados pessoais (e-mails, UUIDs, codigos, nomes) antes de enviar texto a um LLM externo. |

## Papeis (preencha com sua equipe)

Configure em `people[]` do YAML com os User IDs reais do Google Chat.

| Papel | Responsabilidade tipica |
|---|---|
| **Operador principal** | Executa operacoes via `/atende` |
| **Relay de chamados** | Repassa e formata chamados do canal |
| **Tech lead** | Escalacao tecnica, operacoes exclusivas |
| **Billing lead** | Operacoes de plano, quota e cobranca |
| **Compliance officer** | Operacoes sensiveis (LGPD, exclusao de dados, fraude) |
| **Backoffice** | Operacoes manuais que nao tem automacao MCP |

## Convencoes do canal Google Chat

| Sinal | Significado | Acao |
|---|---|---|
| 👀 | "Estou analisando este chamado" | Nao sobrepor |
| ✅ | "Chamado resolvido" | Thread fechada |
| PSC | "Pode ser confirmado" | Aguardar confirmacao do solicitante |
