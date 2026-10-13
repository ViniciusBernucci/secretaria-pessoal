import os,time,signal,fcntl
from pathlib import Path
from datetime import datetime,timedelta,time as civiltime
from zoneinfo import ZoneInfo
from django.db import connection
from django.core.management.base import BaseCommand
from django.utils import timezone
from conversation.models import Incoming,DailyBriefing,ChatTurn,Operation
from conversation.gateway import enqueue
from conversation.assistant import reply
from notifications.models import Runtime,Event
TZ=ZoneInfo('America/Sao_Paulo')

def schedule_daily(now=None):
    if os.getenv('DAILY_BRIEFING_ENABLED','true')!='true':return
    now=(now or timezone.now()).astimezone(TZ)
    at=datetime.combine(now.date(),civiltime.fromisoformat(os.getenv('DAILY_BRIEFING_TIME','08:00')),TZ)
    # Recuperação apenas na janela de 2h, sem briefings velhos durante a noite.
    if not at<=now<at+timedelta(hours=2):return
    daily,created=DailyBriefing.objects.get_or_create(day=now.date())
    if created:
        Incoming.objects.get_or_create(update_id=-int(now.strftime('%Y%m%d')),defaults={'kind':'daily','text':'Briefing pessoal de hoje. Consulte fatos atuais, organize por horário e prioridade registrada e cite fontes. Não altere registros.'})

def process(item):
    item.state='running';item.save(update_fields=['state'])
    try:
        output=reply(item)
    except Exception as exc:
        output=str(exc) if isinstance(exc,ValueError) else 'Não consegui concluir. Verifique acessos e Events no painel; sem presumir resultados.'
        item.state='failed'
        Event.objects.create(category='conversa falhou',detail=type(exc).__name__)
    else:item.state='done'
    item.result=output;item.save(update_fields=['state','result'])
    enqueue('answer:'+str(item.pk),output)
    if item.kind=='chat' and item.text!='/limpar':
        ChatTurn.objects.create(role='user',text=item.text);ChatTurn.objects.create(role='assistant',text=output)
    if item.kind=='daily':DailyBriefing.objects.filter(day=item.created.astimezone(TZ).date()).update(state=item.state)

class Command(BaseCommand):
    help='Processador de conversa/briefing; nunca consome getUpdates'
    def handle(self,*args,**options):
        lock=(Path(connection.settings_dict['NAME']).parent/'assistant.lock').open('a')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Uma escrita pode já ter sido aplicada: não repetir automaticamente pedidos interrompidos.
        for item in Incoming.objects.filter(state='running'):
            item.state='unknown';item.save(update_fields=['state'])
            enqueue('interrupted:'+str(item.pk),'Solicitação interrompida. Confira Operations/Notion antes de repetir alterações.')
        Operation.objects.filter(state='running').update(state='unknown')
        running=True
        def stop(*_):
            nonlocal running
            running=False
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        while running:
            Runtime.objects.update_or_create(key='assistant_heartbeat',defaults={'value':timezone.now().isoformat()})
            try:
                schedule_daily()
                item=Incoming.objects.filter(state='queued').order_by('created').first()
                if item:process(item)
            except Exception as exc:Event.objects.create(category='assistant falhou',detail=type(exc).__name__)
            time.sleep(2)
