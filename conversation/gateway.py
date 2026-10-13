import os
from django.utils import timezone
from datetime import timedelta
from .models import Incoming, Outgoing, Operation
from notifications.api import APIError

HELP = ('Sou sua Secretária. Pergunte sobre tarefas, peça um aviso ou organize a semana.\n'
        '/hoje — briefing agora\n/semana — organizar a semana\n/avisos — consultar avisos\n'
        '/ajuda — comandos\n/limpar — apagar apenas contexto local recente\n'
        'Reconhecer um aviso não conclui uma tarefa. Áudios e anexos ainda não são processados.')

def authorized(user,chat):
    return str(user)==os.environ.get('TELEGRAM_USER_ID') and str(chat)==os.environ.get('TELEGRAM_CHAT_ID')

def enqueue(key,text,buttons=None):
    # Partes individualmente persistidas: reinício não repete partes com sucesso conhecido.
    for index, start in enumerate(range(0,max(1,len(text)),3900)):
        Outgoing.objects.get_or_create(key=f'{key}:{index}',defaults={'text':text[start:start+3900] or 'Sem conteúdo.', 'buttons':buttons or [] if index==0 else []})

def receive(update):
    """Chamado dentro da transação do único poller. Sem HTTP/IA."""
    message=update.get('message')
    if message:
        if not authorized(message.get('from',{}).get('id'),message.get('chat',{}).get('id')): return True
        text=message.get('text')
        if not text:
            enqueue(f'unsupported:{update["update_id"]}','Nesta versão, envie sua solicitação em texto.')
            return True
        if len(text)>6000:
            enqueue(f'long:{update["update_id"]}','Divida a solicitação em mensagens de até 6000 caracteres.')
            return True
        Incoming.objects.get_or_create(update_id=update['update_id'],defaults={'text':text})
        return True
    q=update.get('callback_query',{})
    data=q.get('data','')
    if not data.startswith(('apply:','cancel:')): return False
    if not authorized(q.get('from',{}).get('id'),q.get('message',{}).get('chat',{}).get('id')): return True
    try:
        action,pk=data.split(':')
        op=Operation.objects.get(pk=pk)
        delivery=Outgoing.objects.filter(key__startswith=f'proposal:{op.pk}:',state='sent',message_id=q['message']['message_id']).exists()
        if not delivery or op.state!='pending' or op.expires<timezone.now():
            enqueue(f'stale:{update["update_id"]}','Proposta expirada, antiga ou já processada.')
        elif action=='cancel':
            op.state='cancelled';op.save(update_fields=['state'])
            enqueue(f'cancel:{op.pk}','Proposta cancelada. Nada foi alterado.')
        else:
            Incoming.objects.get_or_create(update_id=update['update_id'],defaults={'text':str(op.pk),'kind':'apply'})
    except (ValueError,KeyError,Operation.DoesNotExist):
        enqueue(f'bad:{update["update_id"]}','Proposta inválida.')
    return True

def flush(telegram):
    for item in Outgoing.objects.filter(state='queued',next_try__lte=timezone.now()).order_by('created')[:5]:
        item.state='sending';item.save(update_fields=['state'])
        try:
            kwargs={'chat_id':os.environ['TELEGRAM_CHAT_ID'],'text':item.text,'link_preview_options':{'is_disabled':True}}
            if item.buttons:kwargs['reply_markup']={'inline_keyboard':item.buttons}
            result=telegram.call('sendMessage',**kwargs)
        except APIError as exc:
            item.state='queued' if exc.status==429 else 'unknown'
            item.next_try=timezone.now()+timedelta(seconds=max(60,exc.retry))
        else:item.state='sent';item.message_id=result['message_id']
        item.save(update_fields=['state','next_try','message_id'])
