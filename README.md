# Secretária Telegram — v2

# Secretária — Telegram + Notion

Aplicação pessoal executável: Django Admin, SQLite e worker único com agenda durável. Suporta tarefas, objetivos/metas (alvo e progresso registrados), mensagens com data/hora, repetição insistente e recorrência a cada N dias. Sem chamadas a modelos de IA durante a operação.

## Entrega e limites

O código não cria nem altera bases pessoais durante instalação. Configure uma base dedicada **Notificações da Secretária** seguindo [docs/NOTION.md](docs/NOTION.md). Somente os registros dessa base recebem edições de configuração e a propriedade **Última confirmação**. Tarefas relacionadas são consultadas para evitar avisos de tarefas concluídas, canceladas ou adiadas. Não altera prazo, execução, prioridade, status de tarefa, ativação de projeto nem eventos do Calendar.

**Confirmar aviso** registra reconhecimento do lembrete, não conclusão da tarefa/meta. A conclusão real continua no Notion. Objetivos exibem progresso cadastrado; não calculam métricas nem ativam projetos. Mensagens não são escritas por IA automaticamente: o texto é cadastrado pela Secretária quando solicitado.

Horário silencioso inicial: 22h–07h, configurável; é um padrão do software, não uma regra atribuída ao manual. O worker consulta a base a cada 60 segundos e verifica os vencimentos a cada ~5 segundos (rede pode ampliar esse tempo). Não é um serviço de alarmes em tempo real. Após queda, entrega um aviso vencido, sem recuperar todas as repetições perdidas. Recorrência usa intervalos de N dias de 24h, não regras mensais nem calendário de dias úteis.

## Arquivos locais necessários após clonar

`conversation/sources.py` é essencial para a aplicação, mas está no `.gitignore` porque a versão local contém IDs pessoais do Notion. O repositório inclui `conversation/sources.example.py`, com a mesma implementação e sem esses IDs. Em uma instalação nova, execute na raiz do projeto, antes dos comandos Django ou da construção das imagens Docker:

```sh
cp -n conversation/sources.example.py conversation/sources.py
cp -n .env.example .env
chmod 600 .env
```

Os comandos de cópia preservam arquivos existentes. Em uma instalação ativa, mantenha seu `conversation/sources.py` e seu `.env` atuais.

Preencha no `.env` privado as credenciais e as configurações indicadas pelo modelo. Para as fontes do Notion, configure:

- `NOTION_MANUAL_ID`: ID da página do manual operacional.
- `NOTION_MEMORY_ID`: ID da página de memória da Secretária.
- `NOTION_HOURS_ID`: ID da página de horários e disponibilidade.
- `NOTION_TASKS_ID`: ID da fonte de dados de tarefas.
- `NOTION_PROJECTS_ID`: ID da fonte de dados de projetos.
- `NOTION_WEEKS_ID`: ID da fonte de dados de semanas.
- `NOTION_DATA_SOURCE_ID`: ID da fonte de dados de notificações.

A integração configurada em `NOTION_TOKEN` precisa ter acesso às páginas e fontes de dados correspondentes. Não publique os IDs pessoais nem os tokens nos arquivos de exemplo. `conversation/sources.py` e `.env` continuam ignorados pelo Git e devem ser recriados ou transferidos de forma privada em cada instalação.

O Docker Compose carrega o `.env` automaticamente. Ao executar os comandos Django diretamente, disponibilize suas variáveis no ambiente do processo; o projeto não carrega o `.env` sozinho.

`docs/UPGRADE-V2.md` também é documentação local ignorada por conter referências pessoais e não acompanha um clone. As instruções acima cobrem a restauração do arquivo essencial; para uma atualização sobre instalação ativa, preserve também esse guia local.

## Implantação

Siga [docs/DEPLOY.md](docs/DEPLOY.md). Não precisa reaproveitar ou modificar um container existente: este Compose cria dois serviços e um volume próprio, em paralelo com os demais projetos. Porta 8097 somente no localhost da VPS.

## Operação

- `/admin/`: autenticação Django; configurações importadas do Notion podem ser editadas e são publicadas/verificadas na base dedicada. Somente superusuários devem receber acesso de edição. Relações e criação de registros são feitas no Notion.
- `paused`: suspensão local de emergência, mantida durante a sincronização. Retomar desmarcando no painel. `active`: configuração oficial no Notion.
- Botões: confirmar aviso, adiar 30 min e pausar. Botões de outra ocorrência e de usuários/chats não autorizados são recusados.
- `Delivery`: histórico de envios. `unknown` significa resposta ambígua; o sistema não reenvia automaticamente. Compare com o Telegram; se necessário use a ação **Reenviar entregas incertas**, aceitando possível duplicação. Se já recebeu, confirme no Notion preenchendo Última confirmação ou mantenha pausado. Um botão de envio incerto pode ser recusado pois o ID da mensagem não foi persistido.
- `Writeback`: confirmação local é gravada em uma transação e enviada ao Notion com novas tentativas, até sucesso. Confirmação mais nova nunca é substituída por uma antiga. Falha não reabre o aviso.
- `Event`: erros sanitizados e operações. `Runtime`: horário de última sincronização/atividade e offset Telegram; não editar manualmente.
- Ao atingir o máximo de avisos, a ocorrência deixa de insistir. Recorrentes avançam para a próxima data futura. Para insistência mais longa configure até 100 avisos, mínimo 5 min. Não há repetição infinita.
- Alterar **Enviar em** cria nova ocorrência, reinicia contagem e invalida botões antigos. Para reenviar algo já confirmado, escolha uma nova data/hora.

## Confiabilidade

A agenda, limites e offset são persistidos. Lock de arquivo impede dois workers no mesmo volume/host. Não escalar worker ou usar o volume SQLite em NFS/múltiplos hosts. Sincronização só aplica o conjunto após paginação completa; registros removidos são desativados, registros inválidos bloqueados. Falha global de sincronização bloqueia novos envios; confirmações recebidas continuam locais. Cada envio consulta novamente o registro e a tarefa relacionada; falha de acesso bloqueia aquele envio.

A API Telegram não oferece uma chave de idempotência para `sendMessage`. Há uma janela inevitável entre envio e gravação da resposta. Entregas nessa janela ficam incertas após reinício, em vez de duplicação automática. Não é garantia de exatamente uma entrega. SQLite + worker único é adequado a este uso pessoal; para múltiplos usuários/escala migre para PostgreSQL e fila.

O painel publica somente campos alterados e preserva relações/conteúdo. Se uma edição falhar na rede, pode aparecer erro de servidor; confira o Notion e recarregue o painel antes de repetir. Pode haver concorrência entre edição externa e sincronização; a verificação anterior ao envio evita mandar uma configuração local divergente. Não editar a mesma notificação em dois lugares simultaneamente.

## Desenvolvimento e verificações

Python 3.12+:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export DJANGO_SECRET_KEY="segredo-apenas-para-testes"
.venv/bin/python manage.py test
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py check
```

Testes usam APIs simuladas, sem mandar mensagens ou modificar o Notion. A aceitação real exige o teste no guia de deploy.

Referências técnicas: [Notion data sources](https://developers.notion.com/reference/query-a-data-source), [Telegram Bot API](https://core.telegram.org/bots/api), [segurança de deploy Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
