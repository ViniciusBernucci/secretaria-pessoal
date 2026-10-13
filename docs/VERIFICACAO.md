# Verificação da entrega — 12/10/2026

- 25 testes automatizados aprovados: confirmação durável, limites, adiamento, pausa, acesso, botão de ocorrência antiga, paginação, snapshot parcial, envios incertos, retry 429, objetivo recorrente, silêncio, tarefa concluída, painel e publicação somente da propriedade alterada.
- Migrações aplicadas em SQLite local; nenhuma migração pendente.
- Arquivos estáticos do Django Admin gerados (127 arquivos).
- Backup SQLite criado e integrity_check aprovado.
- Docker Compose validado com `ENV_FILE=.env.example docker compose config --quiet`.
- Django system check sem problemas. Check de deploy no perfil HTTPS com segredo de teste adequado retorna somente aviso sobre HSTS preload, desativado intencionalmente para não submeter domínio desconhecido à lista permanente dos navegadores. Perfil por túnel HTTP requer as opções descritas no deploy.

Testes executados localmente em Python 3.14 / Django 5.2.18. A imagem usa Python 3.12. Build/execução da imagem não verificados: Docker CLI instalado, daemon local desligado. Nada implantado na VPS. Não houve envio real Telegram nem uso de token Notion da aplicação; os testes de APIs usam simulações.

O recebimento real, autenticação da integração e acesso ao Notion pela VPS precisam ser comprovados seguindo a etapa de aceitação de DEPLOY.md. Não marcar a tarefa pessoal como concluída antes disso.
