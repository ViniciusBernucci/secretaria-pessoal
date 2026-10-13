# Base de notificações e contrato da Secretária

Crie manualmente uma base dedicada **Notificações da Secretária**, sob a Central da Vida. Antes, procure uma base equivalente para evitar duplicata. Esta entrega não assume que essa base já existe. Não acrescente os campos à base global Tarefas.

| Propriedade exata | Tipo Notion | Conteúdo |
|---|---|---|
| Nome | Título | 1–200 caracteres |
| Mensagem | Texto | Texto a enviar |
| Tipo | Seleção | Tarefa, Objetivo, Meta, Mensagem |
| Ativo | Checkbox | Somente avisos autorizados |
| Enviar em | Data | Data **com horário e fuso**, obrigatório |
| Insistente | Checkbox | Repetir até confirmação/limite |
| Intervalo (min) | Número | Inteiro 5–1440; vazio = 30 |
| Máximo de avisos | Número | Inteiro 1–100; vazio = 8; sem insistência = 1 |
| Recorrência (dias) | Número | Inteiro 0–365; 0/vazio = uma ocorrência; 1 diário, 7 semanal |
| Link | URL | Tarefa, objetivo ou outra referência; vazio usa a página da notificação |
| Alvo | Número | Valor final da meta, opcional |
| Progresso | Número | Valor factual atual, opcional |
| Última confirmação | Data | Reservado ao reconhecimento do aviso |
| Tarefa | Relação | Relação para a base global Tarefas; no máximo uma tarefa por aviso |

Todos os campos precisam existir, mesmo quando opcionais/vazios. Campo de seleção é `select`, não `status`. Datas sem horário são rejeitadas; o sistema não transforma Prazo real ou Executar em em horários inventados. Recorrência reutiliza o texto; não altera datas da tarefa.

A integração precisa de leitura na base dedicada e nas tarefas relacionadas, além de atualização na base dedicada. Compartilhe as bases pelo menu Conexões do Notion. Conectar o MCP desta conversa não conecta automaticamente a VPS: configure uma integração própria e o token no `.env` privado.

## Encontrar o data source ID

O ID da página/container de uma base pode diferir do data source ID. Com o token configurado, consulte `GET https://api.notion.com/v1/databases/ID_DA_BASE` com os cabeçalhos Authorization Bearer e Notion-Version `2025-09-03`; copie o ID de `data_sources` que representa a base dedicada. Use um cliente HTTP local confiável, sem colar tokens em sites. O ID fica em `NOTION_DATA_SOURCE_ID`; nunca usar aqui o ID da base Tarefas. API/documentação: https://developers.notion.com/reference/retrieve-a-database.

## Como a Secretária registra

Depois que a base existir, forneça o link dela nesta conversa e peça o registro de um aviso. A Secretária deve:

1. Ler o manual atual e o registro de tarefa/objetivo relevante. Confirmar que não foi concluído, cancelado ou descartado; conferir dependências e decisões.
2. Ler a estrutura real da base dedicada e buscar avisos da mesma tarefa/objetivo, texto e horário; reutilizar o registro canônico quando apropriado.
3. Distinguir o pedido de aviso de prazo real e execução. Usar o horário fornecido/validado; pedir a informação indispensável se faltar.
4. Registrar Nome, Mensagem, Tipo, Enviar em, Ativo e política explicitamente autorizada. Preencher Tarefa/Link. Não tornar insistente um aviso apenas por julgar importante.
5. Ler novamente e conferir propriedades/relação. Não afirmar recebimento até existir evidência.

Exemplo de pedido: “Crie um aviso Telegram para a tarefa X em 13/10/2026 às 19h, repetindo a cada 30 min, até eu confirmar, limitado a 8 avisos”. Esse pedido autoriza os avisos desse registro. Registrar `Enviar em = 2026-10-13T19:00:00-03:00`, Insistente marcado, Intervalo 30, Máximo 8, Recorrência 0 e Ativo marcado. Não altera Executar em ou Prazo real.

Exemplo de objetivo: “Toda segunda às 9h, envie esta mensagem sobre meu objetivo Y”. Tipo Objetivo, Recorrência 7, Insistente desmarcado, link do objetivo; progresso/alvo somente quando fornecidos ou registrados. O software não acompanha objetivos por inferência.

Exemplo de mensagem: data/hora específica, Tipo Mensagem, texto autorizado, Recorrência 0. Não cadastrar informações sigilosas que não devam aparecer no Telegram.

## Confirmações

O botão ✅ atualiza apenas Última confirmação no registro do aviso. Marcar a tarefa como Concluída no Notion suprime novos avisos vinculados após verificação. Para declarar conclusão pelo Telegram seria necessário implementar um fluxo separado de confirmação explícita do resultado; esta versão não faz isso. A confirmação de objetivo não comprova progresso.

O Google Calendar continua independente e seus lembretes existentes permanecem. Este projeto não cria automações no ChatGPT, não espelha Calendar e não escolhe prioridades.
