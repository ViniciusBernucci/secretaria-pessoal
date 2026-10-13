import uuid
from django.db import models
from django.utils import timezone


class Incoming(models.Model):
    update_id = models.BigIntegerField(verbose_name='ID da atualização', unique=True)
    text = models.TextField(verbose_name='Texto')
    state = models.CharField(verbose_name='Estado', choices=[('queued', 'Na fila'), ('running', 'Em processamento'), ('done', 'Concluído'), ('failed', 'Falhou'), ('unknown', 'Resultado incerto')], max_length=12, default='queued')
    created = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    result = models.TextField(verbose_name='Resultado', blank=True)
    kind = models.CharField(verbose_name='Tipo', choices=[('chat', 'Conversa'), ('daily', 'Resumo diário'), ('apply', 'Aplicação do plano')], max_length=12, default='chat')

    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'mensagem recebida'
        verbose_name_plural = 'mensagens recebidas'

class ChatTurn(models.Model):
    role = models.CharField(verbose_name='Papel', choices=[('user', 'Usuário'), ('assistant', 'Assistente')], max_length=12)
    text = models.TextField(verbose_name='Texto')
    created = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'mensagem da conversa'
        verbose_name_plural = 'mensagens da conversa'

class Outgoing(models.Model):
    key = models.CharField(verbose_name='Chave', max_length=100, unique=True)
    text = models.TextField(verbose_name='Texto')
    buttons = models.JSONField(verbose_name='Botões', default=list)
    state = models.CharField(verbose_name='Estado', choices=[('queued', 'Na fila'), ('sending', 'Enviando'), ('sent', 'Enviado'), ('unknown', 'Resultado incerto')], max_length=12, default='queued')
    next_try = models.DateTimeField(verbose_name='Próxima tentativa', default=timezone.now)
    message_id = models.BigIntegerField(verbose_name='ID da mensagem', null=True)
    created = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'mensagem enviada'
        verbose_name_plural = 'mensagens enviadas'

class Operation(models.Model):
    id = models.UUIDField(verbose_name='ID', primary_key=True, default=uuid.uuid4, editable=False)
    incoming = models.ForeignKey(Incoming, verbose_name='Mensagem recebida', on_delete=models.PROTECT)
    key = models.CharField(verbose_name='Chave', max_length=100, unique=True)
    kind = models.CharField(verbose_name='Tipo', choices=[('notice', 'Configuração de aviso'), ('week', 'Plano semanal')], max_length=20)
    payload = models.JSONField(verbose_name='Dados da operação', default=dict)
    result = models.JSONField(verbose_name='Resultado', default=dict)
    state = models.CharField(verbose_name='Estado', choices=[('pending', 'Pendente'), ('running', 'Em processamento'), ('done', 'Concluído'), ('unknown', 'Resultado incerto'), ('partial', 'Parcial'), ('cancelled', 'Cancelado')], max_length=12, default='pending')
    created = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    expires = models.DateTimeField(verbose_name='Expira em')

    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'operação'
        verbose_name_plural = 'operações'

class DailyBriefing(models.Model):
    day = models.DateField(verbose_name='Dia', unique=True)
    state = models.CharField(verbose_name='Estado', choices=[('queued', 'Na fila'), ('running', 'Em processamento'), ('done', 'Concluído'), ('failed', 'Falhou'), ('unknown', 'Resultado incerto')], max_length=12, default='queued')
    created = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'resumo diário'
        verbose_name_plural = 'resumos diários'

class ModelUsage(models.Model):
    created = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    input_tokens = models.PositiveIntegerField(verbose_name='Tokens de entrada', default=0)
    output_tokens = models.PositiveIntegerField(verbose_name='Tokens de saída', default=0)
    purpose = models.CharField(verbose_name='Finalidade', choices=[('chat', 'Conversa'), ('daily', 'Resumo diário'), ('apply', 'Aplicação do plano')], max_length=20)

    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'uso do modelo'
        verbose_name_plural = 'usos do modelo'
