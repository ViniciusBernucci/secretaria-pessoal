import os,json
import requests
from django.utils import timezone
from .models import ModelUsage

def generate(prompt,purpose):
    if ModelUsage.objects.filter(created__gte=timezone.now().astimezone(__import__('zoneinfo').ZoneInfo('America/Sao_Paulo')).replace(hour=0,minute=0,second=0,microsecond=0)).count()>=int(os.getenv('ASSISTANT_MAX_CALLS_PER_DAY','100')):
        raise ValueError('Limite diário local atingido. Os avisos existentes continuam funcionando.')
    if len(prompt.encode())>180000:raise ValueError('Contexto grande demais. Refine a consulta, sem descartar o manual.')
    # Conta também tentativas, limitando uso em falhas.
    ModelUsage.objects.create(purpose=purpose)
    try:
        r=requests.post(os.getenv('ASSISTANT_GATEWAY_URL','http://codex:8001'),headers={'Authorization':'Bearer '+os.environ['ASSISTANT_GATEWAY_KEY']},json={'prompt':prompt},timeout=200)
    except requests.RequestException:raise ValueError('Codex indisponível. Verifique serviço, login e limites da assinatura.')
    if not r.ok:raise ValueError('Codex indisponível. Verifique login da conta e limites da assinatura.')
    result=r.json()
    if not isinstance(result.get('text'),str) or not isinstance(result.get('calls'),list) or len(result['calls'])>4:raise ValueError('Resposta inválida do modelo.')
    return result
