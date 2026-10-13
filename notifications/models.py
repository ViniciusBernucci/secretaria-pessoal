import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Reminder(models.Model):
    id = models.UUIDField(verbose_name='ID', primary_key=True, default=uuid.uuid4, editable=False)
    notion_id = models.CharField(verbose_name='ID no Notion', max_length=36, unique=True)
    title = models.CharField(verbose_name='Título', max_length=200)
    message = models.TextField(verbose_name='Mensagem', blank=True)
    kind = models.CharField(verbose_name='Tipo', max_length=20, choices=[(x,x) for x in ["Tarefa", "Objetivo", "Meta", "Mensagem"]])
    link = models.URLField(verbose_name='Link', blank=True)
    active = models.BooleanField(verbose_name='Ativo', default=False)
    paused = models.BooleanField(verbose_name='Pausado', default=False, help_text="Suspensão local de emergência; não altera o Notion")
    due = models.DateTimeField(verbose_name='Enviar em')
    occurrence_due = models.DateTimeField(verbose_name='Data da ocorrência')
    repeat_minutes = models.PositiveIntegerField(verbose_name='Intervalo (minutos)', default=30, validators=[MinValueValidator(5), MaxValueValidator(1440)])
    max_attempts = models.PositiveIntegerField(verbose_name='Máximo de avisos', default=8, validators=[MinValueValidator(1), MaxValueValidator(100)])
    recurrence_days = models.PositiveIntegerField(verbose_name='Recorrência (dias)', default=0, validators=[MaxValueValidator(365)])
    target = models.FloatField(verbose_name='Alvo', null=True, blank=True)
    progress = models.FloatField(verbose_name='Progresso', null=True, blank=True)
    next_send = models.DateTimeField(verbose_name='Próximo envio', null=True, blank=True)
    attempts = models.PositiveIntegerField(verbose_name='Tentativas', default=0)
    cycle = models.PositiveIntegerField(verbose_name='Ciclo', default=0)
    acknowledged = models.BooleanField(verbose_name='Confirmado', default=False)
    last_seen = models.DateTimeField(verbose_name='Última sincronização', null=True)
    def __str__(self): return self.title

    class Meta:
        verbose_name = 'lembrete'
        verbose_name_plural = 'lembretes'

class Delivery(models.Model):
    reminder = models.ForeignKey(Reminder, verbose_name='Lembrete', on_delete=models.PROTECT)
    cycle = models.PositiveIntegerField(verbose_name='Ciclo')
    attempt = models.PositiveIntegerField(verbose_name='Tentativa')
    state = models.CharField(verbose_name='Estado', choices=[("sending", "Enviando"), ("sent", "Enviado"), ("unknown", "Resultado incerto"), ("retry", "Nova tentativa")], max_length=12, default="sending")
    message_id = models.BigIntegerField(verbose_name='ID da mensagem', null=True, blank=True)
    created = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'entrega'
        verbose_name_plural = 'entregas'
        constraints = [models.UniqueConstraint(fields=["reminder", "cycle", "attempt"], name="unique_delivery")]

class Writeback(models.Model):
    reminder = models.ForeignKey(Reminder, verbose_name='Lembrete', on_delete=models.PROTECT)
    cycle = models.PositiveIntegerField(verbose_name='Ciclo')
    acknowledged_at = models.DateTimeField(verbose_name='Confirmado em')
    done = models.BooleanField(verbose_name='Concluído', default=False)
    retries = models.PositiveIntegerField(verbose_name='Novas tentativas', default=0)
    next_try = models.DateTimeField(verbose_name='Próxima tentativa')
    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'confirmação no Notion'
        verbose_name_plural = 'confirmações no Notion'
        constraints = [models.UniqueConstraint(fields=["reminder", "cycle"], name="unique_ack")]

class Runtime(models.Model):
    key = models.CharField(verbose_name='Chave', max_length=40, primary_key=True)
    value = models.TextField(verbose_name='Valor', blank=True)

    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'estado do sistema'
        verbose_name_plural = 'estados do sistema'

class Event(models.Model):
    created = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    category = models.CharField(verbose_name='Categoria', max_length=40)
    detail = models.CharField(verbose_name='Detalhes', max_length=250)

    def __str__(self):
        return f"{self._meta.verbose_name.capitalize()} ({self.pk})"

    class Meta:
        verbose_name = 'evento'
        verbose_name_plural = 'eventos'
