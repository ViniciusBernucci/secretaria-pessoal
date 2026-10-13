# Tradução dos metadados exibidos no painel de administração.
import django.core.validators
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0001_initial")]

    operations = [
        migrations.AlterModelOptions(
            name='reminder',
            options={'verbose_name': 'lembrete', 'verbose_name_plural': 'lembretes'},
        ),
        migrations.AlterField(
            model_name='reminder',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='notion_id',
            field=models.CharField(max_length=36, unique=True, verbose_name='ID no Notion'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='title',
            field=models.CharField(max_length=200, verbose_name='Título'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='message',
            field=models.TextField(blank=True, verbose_name='Mensagem'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='kind',
            field=models.CharField(choices=[('Tarefa', 'Tarefa'), ('Objetivo', 'Objetivo'), ('Meta', 'Meta'), ('Mensagem', 'Mensagem')], max_length=20, verbose_name='Tipo'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='link',
            field=models.URLField(blank=True, verbose_name='Link'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='active',
            field=models.BooleanField(default=False, verbose_name='Ativo'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='paused',
            field=models.BooleanField(default=False, help_text='Suspensão local de emergência; não altera o Notion', verbose_name='Pausado'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='due',
            field=models.DateTimeField(verbose_name='Enviar em'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='occurrence_due',
            field=models.DateTimeField(verbose_name='Data da ocorrência'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='repeat_minutes',
            field=models.PositiveIntegerField(default=30, validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(1440)], verbose_name='Intervalo (minutos)'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='max_attempts',
            field=models.PositiveIntegerField(default=8, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name='Máximo de avisos'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='recurrence_days',
            field=models.PositiveIntegerField(default=0, validators=[django.core.validators.MaxValueValidator(365)], verbose_name='Recorrência (dias)'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='target',
            field=models.FloatField(blank=True, null=True, verbose_name='Alvo'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='progress',
            field=models.FloatField(blank=True, null=True, verbose_name='Progresso'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='next_send',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Próximo envio'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='attempts',
            field=models.PositiveIntegerField(default=0, verbose_name='Tentativas'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='cycle',
            field=models.PositiveIntegerField(default=0, verbose_name='Ciclo'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='acknowledged',
            field=models.BooleanField(default=False, verbose_name='Confirmado'),
        ),
        migrations.AlterField(
            model_name='reminder',
            name='last_seen',
            field=models.DateTimeField(null=True, verbose_name='Última sincronização'),
        ),
        migrations.AlterModelOptions(
            name='delivery',
            options={'verbose_name': 'entrega', 'verbose_name_plural': 'entregas'},
        ),
        migrations.AlterField(
            model_name='delivery',
            name='reminder',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='notifications.reminder', verbose_name='Lembrete'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='cycle',
            field=models.PositiveIntegerField(verbose_name='Ciclo'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='attempt',
            field=models.PositiveIntegerField(verbose_name='Tentativa'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='state',
            field=models.CharField(default='sending', max_length=12, verbose_name='Estado', choices=[('sending', 'Enviando'), ('sent', 'Enviado'), ('unknown', 'Resultado incerto'), ('retry', 'Nova tentativa')]),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='message_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='ID da mensagem'),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterModelOptions(
            name='writeback',
            options={'verbose_name': 'confirmação no Notion', 'verbose_name_plural': 'confirmações no Notion'},
        ),
        migrations.AlterField(
            model_name='writeback',
            name='reminder',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='notifications.reminder', verbose_name='Lembrete'),
        ),
        migrations.AlterField(
            model_name='writeback',
            name='cycle',
            field=models.PositiveIntegerField(verbose_name='Ciclo'),
        ),
        migrations.AlterField(
            model_name='writeback',
            name='acknowledged_at',
            field=models.DateTimeField(verbose_name='Confirmado em'),
        ),
        migrations.AlterField(
            model_name='writeback',
            name='done',
            field=models.BooleanField(default=False, verbose_name='Concluído'),
        ),
        migrations.AlterField(
            model_name='writeback',
            name='retries',
            field=models.PositiveIntegerField(default=0, verbose_name='Novas tentativas'),
        ),
        migrations.AlterField(
            model_name='writeback',
            name='next_try',
            field=models.DateTimeField(verbose_name='Próxima tentativa'),
        ),
        migrations.AlterModelOptions(
            name='runtime',
            options={'verbose_name': 'estado do sistema', 'verbose_name_plural': 'estados do sistema'},
        ),
        migrations.AlterField(
            model_name='runtime',
            name='key',
            field=models.CharField(max_length=40, primary_key=True, serialize=False, verbose_name='Chave'),
        ),
        migrations.AlterField(
            model_name='runtime',
            name='value',
            field=models.TextField(blank=True, verbose_name='Valor'),
        ),
        migrations.AlterModelOptions(
            name='event',
            options={'verbose_name': 'evento', 'verbose_name_plural': 'eventos'},
        ),
        migrations.AlterField(
            model_name='event',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterField(
            model_name='event',
            name='category',
            field=models.CharField(max_length=40, verbose_name='Categoria'),
        ),
        migrations.AlterField(
            model_name='event',
            name='detail',
            field=models.CharField(max_length=250, verbose_name='Detalhes'),
        ),
    ]
