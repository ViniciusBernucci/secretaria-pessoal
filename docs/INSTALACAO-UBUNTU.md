# Instalação completa em Ubuntu com outros projetos ativos

Este roteiro adiciona a Secretária em `/opt/secretaria-telegram`, com projeto Compose próprio, dois containers e volume próprio. O painel será acessado por túnel SSH. Você não precisa mexer no Nginx, Traefik, certificados ou firewall dos projetos existentes para começar.

Não tenho acesso à sua VPS: nomes de usuário, IP, recursos, portas e versões precisam ser verificados pelos comandos abaixo. Substitua `USUARIO` e `IP_DA_VPS` pelos seus dados. Se o SSH usa outra porta, acrescente `-p PORTA` ao ssh e `-P PORTA` ao scp. Execute um bloco por vez, verificando o resultado.

## 1. Entrar e conferir o servidor — na VPS

No terminal do seu computador:

```sh
ssh USUARIO@IP_DA_VPS
```

Na sessão da VPS:

```sh
cat /etc/os-release
uname -m
whoami
uptime
free -h
df -h / /var/lib/docker
sudo systemctl is-active docker
sudo docker version
sudo docker compose version
sudo docker compose ls
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo docker stats --no-stream
sudo ss -ltnp
sudo docker volume ls
```

O Docker deve estar ativo, o Compose disponível, e os projetos atuais saudáveis. Guarde a lista de containers para comparar depois. Todos os containers compartilham CPU, RAM e disco: isolamento de rede/volume não elimina concorrência por recursos. Se a VPS já estiver pressionada, não faça o build antes de liberar capacidade ou definir uma janela adequada.

Confira especificamente a porta proposta:

```sh
sudo ss -ltnp 'sport = :8097'
```

Sem linha LISTEN, a porta está livre. Se houver processo, não o pare: escolha outra porta para a Secretária na etapa 5.

Se já existe um projeto Compose chamado `secretaria-telegram`, uma pasta `/opt/secretaria-telegram` ou o volume `secretaria-telegram_secretaria-data`, trate como instalação anterior: faça backup e use o roteiro de atualização, em vez de uma instalação nova.

### Se só o Compose estiver faltando

Não reinstale Docker Engine nem reinicie o daemon numa VPS com projetos ativos. Verifique o pacote disponível:

```sh
apt-cache policy docker-compose-plugin
```

Quando existir candidato no repositório Docker já configurado:

```sh
sudo apt-get update
sudo apt-get --simulate install docker-compose-plugin
```

Confira que a simulação não remove nem substitui o Docker que está rodando. Depois:

```sh
sudo apt-get install docker-compose-plugin
sudo docker compose version
```

Se o pacote não existir ou a simulação alterar o Engine/containerd, pare essa etapa e investigue a instalação atual. Não adicionar/reconfigurar repositórios Docker às cegas. [Documentação oficial do plugin Compose](https://docs.docker.com/compose/install/linux/).

## 2. Transferir o ZIP — no seu computador

Baixe `secretaria-telegram.zip` desta conversa. No terminal do computador, ajuste o caminho local do arquivo:

```sh
scp /CAMINHO/DO/ARQUIVO/secretaria-telegram.zip USUARIO@IP_DA_VPS:~/secretaria-telegram.zip
```

Esse comando envia um arquivo para sua pasta pessoal, sem entrar nas pastas dos projetos ativos. Volte à sessão SSH.

## 3. Extrair e preparar a pasta — na VPS

Confira ferramentas:

```sh
command -v unzip
command -v openssl
command -v nano
```

Se alguma faltar, instale apenas as ferramentas necessárias; não executar upgrade geral do Ubuntu:

```sh
sudo apt-get update
sudo apt-get install unzip openssl nano
```

Confira que o destino ainda não existe:

```sh
ls -ld /opt/secretaria-telegram
```

Para uma instalação nova, deve aparecer “No such file or directory”. Se existir, não prossiga com a cópia sobre a instalação anterior.

```sh
mkdir -p ~/secretaria-upload
unzip -n ~/secretaria-telegram.zip -d ~/secretaria-upload
sudo install -d -m 750 -o "$(id -un)" -g "$(id -gn)" /opt/secretaria-telegram
cp -a ~/secretaria-upload/secretaria-telegram/. /opt/secretaria-telegram/
cd /opt/secretaria-telegram
ls -la
```

Devem existir `compose.yaml`, `Dockerfile`, `manage.py`, `.env.example`, `config/`, `notifications/` e `docs/`.

Defina um atalho de comandos limitado a este projeto:

```sh
dc() {
  sudo docker compose --project-directory /opt/secretaria-telegram -f /opt/secretaria-telegram/compose.yaml -p secretaria-telegram "$@"
}
```

Todos os comandos `dc` deste guia usam explicitamente esse arquivo e esse nome de projeto. Recrie a função ao abrir uma nova sessão SSH. O nome do projeto isola recursos Compose; mantenha sempre o mesmo nome para reutilizar o volume correto. [Documentação oficial sobre nomes de projetos](https://docs.docker.com/compose/how-tos/project-name/).

## 4. Criar a configuração privada

Somente na primeira instalação:

```sh
cp -n .env.example .env
chmod 600 .env
openssl rand -hex 32
nano .env
```

Copie o segredo aleatório gerado para `DJANGO_SECRET_KEY`. No nano: Ctrl+O, Enter para salvar; Ctrl+X para sair.

Configuração inicial:

```dotenv
DJANGO_SECRET_KEY=COLE_AQUI_O_SEGREDO_ALEATORIO
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=
HTTPS=false
TRUST_PROXY=false
NOTION_TOKEN=TOKEN_DA_INTEGRACAO_NOTION
NOTION_DATA_SOURCE_ID=
TELEGRAM_BOT_TOKEN=TOKEN_DO_BOT
TELEGRAM_CHAT_ID=
TELEGRAM_USER_ID=
NOTIFICATION_TZ=America/Sao_Paulo
QUIET_START=22:00
QUIET_END=07:00
```

As opções HTTPS=false/TRUST_PROXY=false são para o painel via túnel SSH. O horário silencioso é um padrão configurável do software. Não envie `.env` ao chat, não coloque tokens em URLs de navegador e não faça `source .env`: o Compose lê esse arquivo diretamente.

## 5. Conferir isolamento e porta

```sh
nano compose.yaml
```

A porta publicada deve ser:

```yaml
ports:
  - "127.0.0.1:8097:8000"
```

Se 8097 estiver ocupada, troque apenas o número do meio, por exemplo `127.0.0.1:8098:8000`. O serviço continua na porta 8000 dentro do container. O IP 127.0.0.1 limita o painel ao próprio servidor.

Este projeto não precisa receber conexões externas do Telegram: o worker consulta a API pela saída HTTPS. Não abrir porta 8097 no UFW e não alterar regras de firewall existentes.

Para evitar que o worker consuma toda a VPS em um problema, você pode acrescentar limites iniciais de execução em um override, conforme a capacidade observada. Exemplo opcional, não dimensionamento comprovado para sua VPS:

```yaml
# /opt/secretaria-telegram/compose.limits.yaml
services:
  web:
    cpus: "0.50"
    mem_limit: 384m
    pids_limit: 100
  worker:
    cpus: "0.50"
    mem_limit: 256m
    pids_limit: 100
```

Se usar esse arquivo, altere a função dc para incluir também `-f /opt/secretaria-telegram/compose.limits.yaml` antes de `-p`, e mantenha essa mesma função nas atualizações. Os limites não controlam a fase de build; um limite de memória baixo pode encerrar o processo. Ajuste observando `docker stats`, sem mexer nos limites dos outros projetos.

## 6. Preparar Telegram

No Telegram:

1. Abra o **@BotFather** e envie `/newbot`.
2. Escolha nome e username; guarde o token no `.env`.
3. Abra uma conversa privada com o novo bot e envie `/start`.

Use um bot exclusivo deste projeto. O worker não remove webhook nem desconecta outro consumidor automaticamente.

Na VPS, valide o Compose sem imprimir os segredos e construa a imagem:

```sh
dc config --quiet
dc build
```

Não rode `dc config` sem `--quiet` em saídas que você pretende compartilhar: ele pode mostrar variáveis de ambiente com tokens.

Confira se existe webhook configurado:

```sh
dc run --rm --no-deps web python -c 'from notifications.api import Telegram; print("Webhook configurado:", bool(Telegram().call("getWebhookInfo").get("url")))'
```

Deve retornar False para um bot novo. Se True, não inicie este worker antes de identificar quem usa esse bot.

Para obter seus IDs:

```sh
dc run --rm --no-deps web python -c 'from notifications.api import Telegram; updates=Telegram().call("getUpdates", timeout=0, allowed_updates=["message"]); [print("chat_id:", u["message"]["chat"]["id"], "user_id:", u["message"]["from"]["id"]) for u in updates if "message" in u]'
```

Copie os IDs da sua mensagem privada:

```sh
nano .env
```

Preencha TELEGRAM_CHAT_ID e TELEGRAM_USER_ID. Se não houver saída, envie uma nova mensagem ao bot e repita. Você ainda não deve ter iniciado o worker.

## 7. Preparar Notion

Abra [as integrações do Notion](https://www.notion.so/profile/integrations), crie uma integração interna para este workspace, habilite leitura e atualização, e coloque seu token em NOTION_TOKEN. A integração da VPS é separada do acesso Notion desta conversa.

Na Central da Vida, procure uma base equivalente antes de criar **Notificações da Secretária**. A base precisa destas propriedades exatas:

| Nome | Tipo |
|---|---|
| Nome | Título |
| Mensagem | Texto |
| Tipo | Seleção: Tarefa, Objetivo, Meta, Mensagem |
| Ativo | Checkbox |
| Enviar em | Data com horário e fuso |
| Insistente | Checkbox |
| Intervalo (min) | Número |
| Máximo de avisos | Número |
| Recorrência (dias) | Número |
| Link | URL |
| Alvo | Número |
| Progresso | Número |
| Última confirmação | Data |
| Tarefa | Relação para a base global Tarefas |

Todos os campos precisam existir; os opcionais podem ficar vazios. Não adicionar esses campos à base global Tarefas. Compartilhe a base dedicada com a integração pelo menu de conexões. Compartilhe a base Tarefas também quando utilizar a relação, para o worker verificar seu status.

Abra a base original em página inteira e copie o ID da base do link: são 32 caracteres hexadecimais, antes dos parâmetros `?`. Não usar o ID da página Central ou de uma visualização vinculada.

Obtenha o data source ID usando o token que já está no `.env`:

```sh
dc run --rm --no-deps web python -c 'from notifications.api import Notion; database_id=input("ID da base dedicada: ").strip(); data=Notion().request("GET", "databases/"+database_id); [print("Data source:", s["id"], "Nome:", s.get("name", "")) for s in data.get("data_sources", [])]'
```

Cole somente o ID da base dedicada quando solicitado. O comando é de leitura. Se retornar mais de uma fonte, escolha a que corresponde à estrutura acima. API usada com versão 2025-09-03; [referência oficial do Notion](https://developers.notion.com/reference/retrieve-a-database).

```sh
nano .env
```

Preencha NOTION_DATA_SOURCE_ID com o ID retornado. Não usar aqui a fonte global Tarefas. O contrato de cadastro e validação completo está em `docs/NOTION.md`.

## 8. Criar banco local e usuário do painel

```sh
dc config --quiet
dc run --rm --no-deps web python manage.py migrate
dc run --rm --no-deps web python manage.py createsuperuser
```

No createsuperuser, informe seu username, email se desejar e senha forte. A senha não aparece enquanto você digita. Não colocar senha na linha de comando.

O volume persistente será `secretaria-telegram_secretaria-data`; não é um banco de outro projeto. O banco e as confirmações sobrevivem a recriações dos containers.

Antes de iniciar o worker, pode rodar os testes da aplicação dentro da imagem:

```sh
dc run --rm --no-deps web python manage.py test
```

Esses testes usam APIs simuladas, sem enviar notificações reais. Depois:

```sh
dc up -d
dc ps
dc logs --tail=100 web worker
dc exec worker python manage.py worker_health
curl --fail http://127.0.0.1:8097/health/
```

Se você mudou a porta, ajuste o curl. Aguarde a primeira sincronização antes de exigir health do worker. O health web deve responder `{"status":"ok"}`. O health worker pode não imprimir nada quando passa: o importante é finalizar sem erro.

Compare os outros containers com a lista inicial:

```sh
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo docker stats --no-stream
```

Os outros projetos devem continuar em execução. Os nomes novos normalmente começam por `secretaria-telegram-`.

## 9. Abrir o painel — no seu computador

Abra outra janela de terminal no seu computador e mantenha este túnel ativo:

```sh
ssh -N -L 18097:127.0.0.1:8097 USUARIO@IP_DA_VPS
```

A porta 18097 é local no seu computador; 8097 é a porta escolhida na VPS. Se usou 8098 na VPS, altere somente o destino do túnel para `127.0.0.1:8098`.

Abra **http://127.0.0.1:18097/admin/** no navegador e faça login com o superusuário. É normal o terminal do túnel ficar sem saída. Encerrar esse terminal fecha o acesso ao painel, mas os containers e avisos continuam funcionando.

No painel:

- Reminders: avisos importados, agenda, contagem e pausa; edição de configuração é publicada no Notion.
- Deliveries: envios e estado de entrega.
- Writebacks: confirmações aguardando envio ao Notion ou concluídas.
- Events: erros e operações sanitizados.
- Runtimes: sincronização e atividade do worker.

Uma lista vazia é normal se ainda não houver registro válido na base dedicada. Cadastros novos e relações são feitos no Notion.

## 10. Testar um aviso real

Crie um registro de teste na base dedicada:

| Campo | Valor de teste |
|---|---|
| Nome | Teste da Secretária |
| Mensagem | Esta é uma notificação de teste. |
| Tipo | Mensagem |
| Ativo | Marcado |
| Enviar em | Data de hoje com horário 2–3 minutos no futuro e fuso São Paulo |
| Insistente | Marcado |
| Intervalo (min) | 5 |
| Máximo de avisos | 3 |
| Recorrência (dias) | 0 |
| Tarefa, Alvo, Progresso, Última confirmação | Vazios |

O software não deduz horário a partir de uma data sem hora. Espere até a primeira sincronização e o horário do aviso.

Teste fora de 22h–07h ou desative temporariamente o silêncio colocando QUIET_START e QUIET_END iguais no `.env`, depois aplique:

```sh
dc up -d --force-recreate worker
```

Ao receber:

1. Clique **+30 min** e confira a próxima data no painel.
2. Clique **Confirmar aviso** na mesma mensagem; confira a data Última confirmação no Notion e Writeback done.
3. Verifique que a insistência parou. Essa confirmação não marca tarefa/meta concluída.
4. Altere Enviar em para outro horário futuro para criar uma nova ocorrência; botões antigos devem ser recusados.
5. Teste Pausar e retome desmarcando paused no painel.
6. Reinicie só o worker e confira que o aviso confirmado não reabre:

```sh
dc restart worker
dc ps
```

Restaure o silêncio caso tenha alterado. Não marcar a tarefa de implementação como concluída até o recebimento real ficar demonstrado.

## 11. Uso com a Secretária

Envie o link da base dedicada nesta conversa. Depois peça, por exemplo:

“Registre no Telegram um aviso para a tarefa X amanhã às 19h, repetindo a cada 30 minutos, até confirmação, limitado a 8 avisos.”

A Secretária deve ler a estrutura, verificar a tarefa e procurar duplicatas; cadastrar o aviso autorizado e conferir o resultado. Ela não envia comandos diretamente à VPS: o worker consulta o Notion e encontra o registro.

Objetivos/metas usam Tipo Objetivo/Meta, texto, link e progresso/alvo factual. Recorrência 7 repete a cada sete dias. Uma mensagem programada usa Tipo Mensagem, data/hora e texto aprovado. Não há geração automática de texto por IA no servidor.

## 12. Operação diária — apenas este projeto

```sh
dc ps
dc logs --tail=100 worker
dc logs --tail=100 web
dc exec worker python manage.py worker_health
dc restart worker
dc stop worker
dc start worker
```

`restart` não aplica alterações de `.env`; depois de editar variáveis, use `dc up -d --force-recreate worker` (ou web quando mudar configuração do painel).

Para parar apenas esta aplicação preservando o banco:

```sh
dc stop web worker
```

Para iniciar:

```sh
dc up -d
```

Não usar `docker stop` com a lista de todos os containers, `docker system prune --volumes`, `dc down -v`, reinício do serviço Docker ou reboot como etapa de instalação. Não modificar os Compose dos outros projetos.

## 13. Backup consistente

Na VPS, em sessão com a função dc definida:

```sh
install -d -m 700 /opt/secretaria-telegram/backups
SECRETARIA_BACKUP_TIME=$(date +%Y%m%d-%H%M%S)
dc exec web python manage.py backup /data/backup.sqlite3
dc cp web:/data/backup.sqlite3 "/opt/secretaria-telegram/backups/db-${SECRETARIA_BACKUP_TIME}.sqlite3"
chmod 600 "/opt/secretaria-telegram/backups/db-${SECRETARIA_BACKUP_TIME}.sqlite3"
cp .env "/opt/secretaria-telegram/backups/env-${SECRETARIA_BACKUP_TIME}"
chmod 600 "/opt/secretaria-telegram/backups/env-${SECRETARIA_BACKUP_TIME}"
```

Execute os comandos com `cd /opt/secretaria-telegram`, para o cp .env correto. Os backups incluem dados pessoais e credenciais; mantenha essa pasta privada. Guarde uma cópia em outro local seguro/criptografado. Não copiar só db.sqlite3 durante operação: SQLite pode ter transações no WAL. O comando backup usa a API consistente do SQLite.

No computador, copiar a pasta por SSH:

```sh
scp -r USUARIO@IP_DA_VPS:/opt/secretaria-telegram/backups /CAMINHO/PRIVADO/DO/BACKUP/
```

## 14. Atualizar sem atingir os demais projetos

Faça backup primeiro. Guarde também a versão anterior do código. Extraia a nova versão numa pasta temporária e compare as alterações; preserve `.env` e `backups/` e não substitua arquivos sem revisar.

Depois de colocar o novo código nesta pasta:

```sh
dc stop web worker
dc build
dc run --rm --no-deps web python manage.py migrate
dc up -d
dc ps
dc exec worker python manage.py worker_health
```

Isso interrompe somente o painel e o worker deste projeto. Não apagar o volume. Se migração falhar, não reiniciar os serviços com schema incompatível: preserve a mensagem e o backup. Restauração detalhada em `docs/DEPLOY.md`; ela substitui o estado atual e exige ambos os serviços parados.

## 15. Diagnóstico rápido

| Sintoma | Verificação |
|---|---|
| Porta ocupada | `sudo ss -ltnp 'sport = :8097'`; escolher outra porta do host |
| Não abre o painel | curl local na VPS; túnel SSH ativo; porta de destino correta |
| Notion 401 | Token da integração no .env; recriar worker depois de editar |
| Notion 403/404 | Compartilhamento das bases e ID de data source correto |
| Sync falhou | Events; propriedades exatas e tipos; data/horário explícitos |
| Lista vazia | Primeiro registro válido; primeira sync; eventos de erro |
| Aviso não chega | Ativo, paused, silêncio, próxima data, limite, sync e tarefa relacionada |
| Writeback pendente | Permissão de atualização e propriedade Última confirmação |
| Telegram conflito 409 | Outro consumidor ou webhook com o mesmo bot |
| Delivery unknown | Envio de resultado incerto; verificar Telegram antes de ação manual de reenvio |
| Worker unhealthy | Runtime/Event; Docker não reinicia automaticamente processo apenas por unhealthy |
| Container encerra por memória | `docker stats`; revisar limites opcionais/capacidade real |

Se precisar compartilhar um diagnóstico, envie os erros sanitizados e `dc ps`, sem o `.env`, tokens ou saída completa de `dc config`.

## Limites da verificação

O projeto passou nos testes locais da entrega anterior. Não foi instalado nem testado na sua VPS; o daemon Docker local estava desligado. Este roteiro precisa do teste real Telegram/Notion acima. Manual Operacional relido nesta interação: a versão retornada possui seções 1–9, sem a seção 12 mencionada nas instruções do projeto. Nenhum dado do Notion foi alterado para escrever este guia.
