# Implantar na VPS que já possui Docker

Use uma pasta própria, como `/opt/secretaria-telegram`. Não entre na pasta de outro Compose e não use comandos globais de limpeza Docker. Este projeto cria serviços `web`, `worker`, rede e volume próprios. Precisa de Docker Engine e Compose v2 já disponíveis. Não há migração de um container antigo.

## 1. Copiar e configurar

Extraia o ZIP entregue na VPS e entre na pasta do projeto:

```sh
cd /opt/secretaria-telegram
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Cole a saída aleatória em `DJANGO_SECRET_KEY` e edite `.env` com seu editor. Não use o exemplo como segredo real. Não envie o `.env` ao chat ou a um repositório.

No Telegram, crie um bot com o **@BotFather**, guarde o token em `TELEGRAM_BOT_TOKEN`, abra uma conversa privada com o bot e envie `/start`. Use um bot exclusivo: dois consumidores de `getUpdates` ou um webhook existente entram em conflito. Se reaproveitar um bot, remova conscientemente o webhook via `deleteWebhook` antes de iniciar este worker; este projeto não remove configurações de outros serviços automaticamente.

Para obter os IDs, antes de iniciar o worker, configure o token no `.env` e execute:

```sh
docker compose build
docker compose run --rm --no-deps web python -c 'from notifications.api import Telegram; t=Telegram(); print(t.call("getUpdates", timeout=0, allowed_updates=["message"]))'
```

Na resposta de sua mensagem privada, copie `message.chat.id` para `TELEGRAM_CHAT_ID` e `message.from.id` para `TELEGRAM_USER_ID`. Isso imprime sua mensagem/IDs, não o token. Use conversa privada, não grupo. Caso não apareça mensagem, envie outra mensagem ao bot e repita. O bot não pode iniciar a conversa antes de você o acionar.

Crie/valide a base dedicada conforme [NOTION.md](NOTION.md). Crie a integração no Notion, compartilhe a base dedicada e a base Tarefas quando usar relações. Preencha `NOTION_TOKEN` e `NOTION_DATA_SOURCE_ID`. Não reutilize o ID global Tarefas como fonte de notificações.

## 2. Preparar armazenamento e iniciar

```sh
docker compose build
docker compose run --rm --no-deps web python manage.py migrate
docker compose run --rm --no-deps web python manage.py createsuperuser
docker compose up -d
docker compose ps
docker compose logs --tail=100 worker
```

A imagem cria `/data` com proprietário UID 10001; o volume nomeado herda a permissão ao ser criado. Se houver erro de permissão, verifique se você trocou por bind mount; nesse caso prepare o diretório do host para UID 10001. Não altere permissões de volumes de outros serviços.

Se 8097 estiver ocupada, altere somente a porta do host no `compose.yaml`. Não mudar 8000 dentro do container. Rede dedicada permite saída HTTPS para Telegram e Notion, sem publicar o worker.

Acesse pelo túnel SSH no seu computador:

```sh
ssh -N -L 8097:127.0.0.1:8097 SEU_USUARIO@SUA_VPS
```

Abra `http://127.0.0.1:8097/admin/`. O HTTP fica dentro do túnel; mantenha `HTTPS=false` nesse modo e não exponha 8097 publicamente. O painel exibe registros depois da primeira sincronização. Cadastros novos/relações são feitos na base Notion. Pode editar texto, política, horário, tipo, alvo e progresso no painel; salvar publica os campos alterados no Notion.

## 3. Teste real de aceitação

1. No Notion crie “Teste de notificações”, Tipo Mensagem, texto de teste, Enviar em com horário/fuso 2 minutos no futuro, Ativo marcado, Insistente marcado, Intervalo 5, Máximo 3, Recorrência 0. Todos os campos do esquema devem existir.
2. Se estiver no horário silencioso, escolha um horário fora dele ou ajuste temporariamente QUIET_START/QUIET_END para o mesmo horário e recrie o worker com `docker compose up -d --force-recreate worker`. Depois restaure o silêncio.
3. Confira que o painel importou o registro e que a primeira mensagem chegou.
4. Clique +30 min. Confira `next_send` no painel. Para testar a confirmação sem esperar, confirme na mensagem já recebida.
5. Clique ✅ Confirmar aviso. Confira o Writeback como `done`, a data Última confirmação no Notion e a ausência de novos avisos dessa ocorrência.
6. Altere Enviar em para um novo horário futuro; confira nova ocorrência. Clique no botão antigo: deve informar aviso antigo. Pause no Telegram e retome desmarcando `paused` no painel.
7. Pare/inicie apenas o worker; a agenda não pode reabrir um aviso confirmado nem duplicar entrega registrada:

```sh
docker compose restart worker
docker compose ps
docker compose exec worker python manage.py worker_health
```

8. Para testar objetivos, use Tipo Meta, Alvo 10, Progresso 3, Recorrência 7. Confira o texto. A confirmação não modifica o progresso.
9. Para tarefa relacionada, use um registro de teste já autorizado. Marque a tarefa Concluída no Notion e confirme que não há envio; não alterar tarefa pessoal real apenas para teste.

Só depois desse recebimento demonstrado considerar cumprido o critério da tarefa de implementação no Notion. O teste automatizado local não substitui essa evidência.

## 4. Segurança opcional com domínio

O túnel é o caminho inicial. Para domínio público, use o proxy HTTPS já operado por você, com certificado válido, autenticação adicional/restrição de IP ou VPN e limitação de tentativas de login. Django Admin não inclui bloqueio automático de força bruta nesta versão. Não publicar o painel na internet sem essa proteção.

Configure em `.env`:

```dotenv
ALLOWED_HOSTS=notificacoes.seudominio.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://notificacoes.seudominio.com
HTTPS=true
TRUST_PROXY=true
```

Só use TRUST_PROXY quando o proxy confiável substituir `X-Forwarded-Proto` e o acesso direto ficar restrito. Se proxy já roda no host, encaminhe para `127.0.0.1:8097`. Se roda em outro container, localhost se refere ao próprio container: conecte apenas `web` à rede compartilhada do proxy via override Compose, usando upstream `web:8000`; não conecte/publicar worker. A rede do proxy varia na sua VPS, por isso não foi inventado um nome de rede.

Exemplo de trecho Nginx no servidor HTTPS existente (a diretiva `limit_req_zone` pertence ao contexto `http`):

```nginx
limit_req_zone $binary_remote_addr zone=secretaria_login:10m rate=5r/m;
# Dentro do server HTTPS:
location /admin/login/ {
    limit_req zone=secretaria_login burst=5 nodelay;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_pass http://127.0.0.1:8097;
}
location / {
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_pass http://127.0.0.1:8097;
}
```

Adicione a restrição de IP/VPN/autenticação conforme sua infraestrutura antes de publicar. Não há necessidade de webhook Telegram nem porta pública para o bot.

## 5. Backup, atualização e restauração

Backup consistente, mesmo com WAL ativo:

```sh
docker compose exec web python manage.py backup /data/backup.sqlite3
docker compose cp web:/data/backup.sqlite3 ./backup.sqlite3
```

Guarde também a versão do código e `.env` de modo privado. Copie o backup criptografado para outro host; não inclua credenciais no ZIP de código. Não copiar apenas `db.sqlite3` durante escrita ativa: pode faltar estado do WAL.

Antes de atualizar:

```sh
docker compose stop worker
# Faça o backup e copie para fora do volume antes da atualização.
docker compose build
docker compose run --rm --no-deps web python manage.py migrate
docker compose up -d
```

Preserve o volume e `.env`. Para restaurar, pare ambos os serviços e trabalhe somente no volume deste Compose:

```sh
docker compose stop web worker
docker compose run --rm --no-deps -v "$PWD/backup.sqlite3:/restore/backup.sqlite3:ro" web python -c 'import os, sqlite3; p="/data/db.sqlite3"; [os.unlink(x) for x in [p,p+"-wal",p+"-shm"] if os.path.exists(x)]; s=sqlite3.connect("/restore/backup.sqlite3"); t=sqlite3.connect(p); s.backup(t); print(t.execute("PRAGMA integrity_check").fetchone()[0]); t.close(); s.close()'
docker compose up -d
```

Restauração substitui o estado atual pelo backup. Um backup antigo pode reabrir envios/offsets já processados; mantenha avisos desativados no Notion e confira o histórico antes de retomar. O backup contém dados pessoais.

Não usar `docker compose down -v`: apaga o estado das confirmações. `docker compose down` sem `-v` preserva volume. Nunca executar `docker system prune --volumes` como etapa deste projeto.

## 6. Diagnóstico

- `sync falhou`: conferir token, compartilhamento, data source ID e nomes/tipos das propriedades.
- Registro inválido: Enviar em exige horário e fuso; Tipo e números devem respeitar o contrato.
- Worker unhealthy: conferir Runtime/Event. Docker marca unhealthy, mas não reinicia automaticamente um processo ainda ativo; restart policy reinicia processos encerrados. Use monitoramento da VPS para alertar sobre unhealthy.
- Não envia: verificar Ativo, paused, silêncio, próxima data, contagem, estado unknown, sync recente e tarefa relacionada.
- Conflito getUpdates: outro consumidor ou webhook usando o bot.
- Writeback pendente: conferir capacidade de atualização da integração e campo Última confirmação.
- Erro de edição Admin: pode ter sido publicado no Notion antes da falha de verificação. Ler o registro e recarregar antes de tentar novamente.
- Disco: acompanhar tamanho do SQLite/Event/Delivery. Registros de auditoria não são removidos automaticamente. Defina retenção/backups antes de crescimento prolongado.
