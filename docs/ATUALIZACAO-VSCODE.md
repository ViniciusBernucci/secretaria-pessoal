# Atualizar pelo VS Code remoto com pausa breve

A atualização não promete zero interrupção da Secretária: o worker único precisa ser trocado. Prepare build, testes e login antes; a pausa fica no corte final. Os demais projetos Compose da VPS não precisam parar.

## Preparação

No Mac, baixe o ZIP v2 e envie:

```bash
scp ~/Downloads/secretaria-telegram-v2.zip lefabrique-dev:~/secretaria/
```

No terminal remoto do VS Code:

```bash
mkdir -p ~/secretaria/upgrade-v2
unzip -n ~/secretaria/secretaria-telegram-v2.zip -d ~/secretaria/upgrade-v2
cp -n ~/secretaria/secretaria-telegram/.env ~/secretaria/upgrade-v2/secretaria-telegram/.env
chmod 600 ~/secretaria/upgrade-v2/secretaria-telegram/.env
```

Se upgrade-v2 já tiver uma extração anterior, confira sua versão antes; unzip -n não substitui arquivos existentes. Não repetir este procedimento sobre uma pasta antiga sem revisar diferenças.

Abra essa pasta de preparação no VS Code, adicionando-a ao workspace remoto. Edite somente o .env da preparação. Siga a lista de variáveis da seção 3 de UPGRADE-V2.md, incluindo ASSISTANT_GATEWAY_KEY gerado com openssl e briefing 08:00. Preserve credenciais antigas. Acrescentar Google Calendar pode ser feito depois, com as limitações descritas no guia.

No terminal remoto, defina as duas funções:

```bash
dc() {
  sudo docker compose --project-directory /home/vinicius/secretaria/secretaria-telegram -f /home/vinicius/secretaria/secretaria-telegram/compose.yaml --env-file /home/vinicius/secretaria/secretaria-telegram/.env -p secretaria-telegram "$@"
}
prep() {
  sudo docker compose --project-directory /home/vinicius/secretaria/upgrade-v2/secretaria-telegram -f /home/vinicius/secretaria/upgrade-v2/secretaria-telegram/compose.yaml --env-file /home/vinicius/secretaria/upgrade-v2/secretaria-telegram/.env -p secretaria-telegram "$@"
}
```

prep usa o mesmo nome de projeto para preparar as imagens e o volume de autenticação que serão usados no corte. Use SOMENTE config/build/run nos passos abaixo. Não executar prep up/down/stop: o mesmo nome poderia administrar os containers atuais.

Guarde a imagem anterior antes de construir:

```bash
sudo docker image tag secretaria-telegram:local secretaria-telegram:antes-v2
```

Guarde o código anterior e a configuração privada:

```bash
cd /home/vinicius/secretaria/secretaria-telegram
install -d -m 700 backups
cp -n .env backups/env-before-v2
tar --exclude='./.env' --exclude='./backups' --exclude='./.git' --exclude='./.venv' -czf /home/vinicius/secretaria/codigo-antes-v2.tar.gz .
chmod 600 backups/env-before-v2 /home/vinicius/secretaria/codigo-antes-v2.tar.gz
```

Valide e construa sem parar os containers atuais:

```bash
prep config --quiet
prep build
prep run --rm --no-deps web python manage.py test
```

Build muda as tags de imagem, mas containers existentes continuam usando a imagem com que foram criados. O teste Django usa banco de teste, não aplica migrações no banco ativo. Ele usa o mesmo volume montado, então execute apenas o comando test conhecido da entrega, não comandos experimentais de alteração de dados.

Autentique antes de parar:

```bash
prep run --rm --no-deps codex codex login --device-auth
prep run --rm --no-deps codex codex login status
```

Siga o login oficial no navegador do Mac. Falha de autenticação deve ser resolvida antes do corte se quiser ativar conversa logo. O motor de avisos pode ser iniciado sem a conversa. Amplie o acesso da integração Notion conforme UPGRADE-V2.md.

## Corte final

Somente depois de preparação bem-sucedida:

```bash
dc stop web worker
```

Após parar as escritas, gere um backup consistente com a imagem anterior:

```bash
sudo docker run --rm --user 10001:10001 -v secretaria-telegram_secretaria-data:/data -e DB_PATH=/data/db.sqlite3 -e DJANGO_SECRET_KEY=backup-only secretaria-telegram:antes-v2 python manage.py backup /data/backup-before-v2.sqlite3
```

O container web antigo parado ainda existe. docker cp consegue ler seu volume:

```bash
dc cp web:/data/backup-before-v2.sqlite3 backups/backup-before-v2.sqlite3
chmod 600 backups/backup-before-v2.sqlite3
```

Copie a versão preparada, que agora inclui o .env revisado:

```bash
cp -a /home/vinicius/secretaria/upgrade-v2/secretaria-telegram/. /home/vinicius/secretaria/secretaria-telegram/
chmod 600 /home/vinicius/secretaria/secretaria-telegram/.env
dc run --rm --no-deps web python manage.py migrate
```

Se migrate falhar, não continuar com up. Preserve a saída, a imagem anterior e os backups; não restaurar o banco automaticamente.

Inicie:

```bash
dc up -d web worker codex assistant
dc ps
curl --fail http://127.0.0.1:8097/health/
dc logs --tail=60 worker assistant codex
```

Aguarde a primeira sync e confira:

```bash
dc exec worker python manage.py worker_health
dc exec assistant python manage.py assistant_health
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Teste /ajuda, /hoje e uma consulta pelo Telegram. O acesso Admin por túnel permanece. Não é necessário reiniciar Docker, Ubuntu, PostgreSQL ou projetos La Fabrique.

## Se falhar

- Antes do corte: não executar o corte; os containers atuais continuam rodando.
- Depois do corte: não apagar volume e não repetir escrita incerta. Guarde erro.
- Falha apenas da conversa: parar assistant; os avisos continuam independentes. O worker ainda é o receptor de mensagens.
- Rollback completo exige recuperar código, Compose e .env anteriores e a tag antiga. As tabelas novas são aditivas, mas isso não autoriza restaurar backup antigo sem analisar perda de novos dados.

Nenhum destes comandos foi executado na VPS por esta documentação. As imagens da v2 ainda precisam passar pelo build real e login da conta.
