# Tradução dos metadados exibidos no painel de administração.
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("conversation", "0001_initial")]

    operations = [
        migrations.AlterModelOptions(
            name='incoming',
            options={'verbose_name': 'mensagem recebida', 'verbose_name_plural': 'mensagens recebidas'},
        ),
        migrations.AlterField(
            model_name='incoming',
            name='update_id',
            field=models.BigIntegerField(unique=True, verbose_name='ID da atualização'),
        ),
        migrations.AlterField(
            model_name='incoming',
            name='text',
            field=models.TextField(verbose_name='Texto'),
        ),
        migrations.AlterField(
            model_name='incoming',
            name='state',
            field=models.CharField(default='queued', max_length=12, verbose_name='Estado', choices=[('queued', 'Na fila'), ('running', 'Em processamento'), ('done', 'Concluído'), ('failed', 'Falhou'), ('unknown', 'Resultado incerto')]),
        ),
        migrations.AlterField(
            model_name='incoming',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterField(
            model_name='incoming',
            name='result',
            field=models.TextField(blank=True, verbose_name='Resultado'),
        ),
        migrations.AlterField(
            model_name='incoming',
            name='kind',
            field=models.CharField(default='chat', max_length=12, verbose_name='Tipo', choices=[('chat', 'Conversa'), ('daily', 'Resumo diário'), ('apply', 'Aplicação do plano')]),
        ),
        migrations.AlterModelOptions(
            name='chatturn',
            options={'verbose_name': 'mensagem da conversa', 'verbose_name_plural': 'mensagens da conversa'},
        ),
        migrations.AlterField(
            model_name='chatturn',
            name='role',
            field=models.CharField(max_length=12, verbose_name='Papel', choices=[('user', 'Usuário'), ('assistant', 'Assistente')]),
        ),
        migrations.AlterField(
            model_name='chatturn',
            name='text',
            field=models.TextField(verbose_name='Texto'),
        ),
        migrations.AlterField(
            model_name='chatturn',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterModelOptions(
            name='outgoing',
            options={'verbose_name': 'mensagem enviada', 'verbose_name_plural': 'mensagens enviadas'},
        ),
        migrations.AlterField(
            model_name='outgoing',
            name='key',
            field=models.CharField(max_length=100, unique=True, verbose_name='Chave'),
        ),
        migrations.AlterField(
            model_name='outgoing',
            name='text',
            field=models.TextField(verbose_name='Texto'),
        ),
        migrations.AlterField(
            model_name='outgoing',
            name='buttons',
            field=models.JSONField(default=list, verbose_name='Botões'),
        ),
        migrations.AlterField(
            model_name='outgoing',
            name='state',
            field=models.CharField(default='queued', max_length=12, verbose_name='Estado', choices=[('queued', 'Na fila'), ('sending', 'Enviando'), ('sent', 'Enviado'), ('unknown', 'Resultado incerto')]),
        ),
        migrations.AlterField(
            model_name='outgoing',
            name='next_try',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='Próxima tentativa'),
        ),
        migrations.AlterField(
            model_name='outgoing',
            name='message_id',
            field=models.BigIntegerField(null=True, verbose_name='ID da mensagem'),
        ),
        migrations.AlterField(
            model_name='outgoing',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterModelOptions(
            name='operation',
            options={'verbose_name': 'operação', 'verbose_name_plural': 'operações'},
        ),
        migrations.AlterField(
            model_name='operation',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='operation',
            name='incoming',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='conversation.incoming', verbose_name='Mensagem recebida'),
        ),
        migrations.AlterField(
            model_name='operation',
            name='key',
            field=models.CharField(max_length=100, unique=True, verbose_name='Chave'),
        ),
        migrations.AlterField(
            model_name='operation',
            name='kind',
            field=models.CharField(max_length=20, verbose_name='Tipo', choices=[('notice', 'Configuração de aviso'), ('week', 'Plano semanal')]),
        ),
        migrations.AlterField(
            model_name='operation',
            name='payload',
            field=models.JSONField(default=dict, verbose_name='Dados da operação'),
        ),
        migrations.AlterField(
            model_name='operation',
            name='result',
            field=models.JSONField(default=dict, verbose_name='Resultado'),
        ),
        migrations.AlterField(
            model_name='operation',
            name='state',
            field=models.CharField(default='pending', max_length=12, verbose_name='Estado', choices=[('pending', 'Pendente'), ('running', 'Em processamento'), ('done', 'Concluído'), ('unknown', 'Resultado incerto'), ('partial', 'Parcial'), ('cancelled', 'Cancelado')]),
        ),
        migrations.AlterField(
            model_name='operation',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterField(
            model_name='operation',
            name='expires',
            field=models.DateTimeField(verbose_name='Expira em'),
        ),
        migrations.AlterModelOptions(
            name='dailybriefing',
            options={'verbose_name': 'resumo diário', 'verbose_name_plural': 'resumos diários'},
        ),
        migrations.AlterField(
            model_name='dailybriefing',
            name='day',
            field=models.DateField(unique=True, verbose_name='Dia'),
        ),
        migrations.AlterField(
            model_name='dailybriefing',
            name='state',
            field=models.CharField(default='queued', max_length=12, verbose_name='Estado', choices=[('queued', 'Na fila'), ('running', 'Em processamento'), ('done', 'Concluído'), ('failed', 'Falhou'), ('unknown', 'Resultado incerto')]),
        ),
        migrations.AlterField(
            model_name='dailybriefing',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterModelOptions(
            name='modelusage',
            options={'verbose_name': 'uso do modelo', 'verbose_name_plural': 'usos do modelo'},
        ),
        migrations.AlterField(
            model_name='modelusage',
            name='created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterField(
            model_name='modelusage',
            name='input_tokens',
            field=models.PositiveIntegerField(default=0, verbose_name='Tokens de entrada'),
        ),
        migrations.AlterField(
            model_name='modelusage',
            name='output_tokens',
            field=models.PositiveIntegerField(default=0, verbose_name='Tokens de saída'),
        ),
        migrations.AlterField(
            model_name='modelusage',
            name='purpose',
            field=models.CharField(max_length=20, verbose_name='Finalidade', choices=[('chat', 'Conversa'), ('daily', 'Resumo diário'), ('apply', 'Aplicação do plano')]),
        ),
    ]
