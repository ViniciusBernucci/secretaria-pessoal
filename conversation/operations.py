import os,json,re,hashlib,math
from datetime import datetime,timedelta
import requests
from django.utils import timezone
from .models import Operation
from .sources import ref,uid,value,summary,TZ
from .gateway import enqueue
from notifications.engine import SCHEMA,normalize,aware_date
from notifications.api import APIError

NOTICE_FIELDS={'title':'Nome','message':'Mensagem','kind':'Tipo','active':'Ativo','due':'Enviar em','insistent':'Insistente','repeat_minutes':'Intervalo (min)','max_attempts':'Máximo de avisos','recurrence_days':'Recorrência (dias)','link':'Link','target':'Alvo','progress':'Progresso','task_id':'Tarefa'}

def source_is(page,source,src):
    parent=page.get('parent',{})
    if parent.get('data_source_id'):return uid(parent['data_source_id'])==uid(source)
    if parent.get('database_id'):
        db=src.notion.request('GET','databases/'+parent['database_id'])
        return uid(source) in [uid(x['id']) for x in db.get('data_sources',[])]
    return False

def properties(fields):
    result={}
    for key,v in fields.items():
        if key not in NOTICE_FIELDS:raise ValueError('Campo de aviso não permitido: '+key)
        name=NOTICE_FIELDS[key];kind=SCHEMA[name]
        if kind in ('title','rich_text'):
            if not isinstance(v,str) or len(v)>3500:raise ValueError('Texto inválido ou grande demais.')
            data=[{'text':{'content':v[i:i+1900]}} for i in range(0,len(v),1900)]
        elif kind=='select':data={'name':v}
        elif kind=='date':data={'start':aware_date(v).isoformat()}
        elif kind=='relation':data=[{'id':uid(v)}] if v else []
        elif kind=='checkbox':
            if not isinstance(v,bool):raise ValueError('Checkbox exige booleano.')
            data=v
        else:data=v
        result[name]={kind:data,'type':kind}
    return result

def notice(src,incoming,args):
    quote=args.get('authorization_quote','')
    if not quote or quote not in incoming.text or not re.search(r'(?i)(cri[ae]|cadastr|registr|lembre|lembrar|avis[oe]|alter|mud[ae]|reprogram|desativ|cancel|atualiz)',quote):
        raise ValueError('Alterar exige um pedido explícito na mensagem atual; recomendações permanecem propostas.')
    fields=args.get('fields',{});action=args.get('action');page_id=args.get('page_id')
    if action not in ('create','update') or not isinstance(fields,dict) or not fields:raise ValueError('Ação de aviso inválida.')
    schema=src.schema('notifications')
    if any(schema.get(k,{}).get('type')!=v for k,v in SCHEMA.items()):raise ValueError('Esquema de avisos divergente.')
    if fields.get('task_id'):
        task=src.page(fields['task_id'])
        if task['archived'] or task['properties'].get('Status') in ('Concluída','Cancelada','Adiada'):raise ValueError('Tarefa não elegível para aviso.')
        raw=src.notion.request('GET','pages/'+uid(fields['task_id']))
        if not source_is(raw,ref('tasks'),src):raise ValueError('Relação não pertence à base Tarefas.')
    if action=='create':
        required={'title','message','kind','due','active','insistent','repeat_minutes','max_attempts','recurrence_days'}
        if not required.issubset(fields):raise ValueError('Informe horário, texto, tipo e política explícita; não deduzir insistência.')
        defaults={'Link':{'type':'url','url':None},'Alvo':{'type':'number','number':None},'Progresso':{'type':'number','number':None},'Última confirmação':{'type':'date','date':None},'Tarefa':{'type':'relation','relation':[]}}
        props={**defaults,**properties(fields)}
        dummy={'id':'00000000-0000-0000-0000-000000000000','url':'https://notion.so/test','properties':props}
    else:
        raw=src.notion.request('GET','pages/'+uid(page_id))
        if not source_is(raw,ref('notifications'),src) or raw.get('archived') or raw.get('in_trash'):raise ValueError('Aviso fora da base ou arquivado.')
        src.page(page_id) # ler conteúdo/decisões antes da alteração
        props=properties(fields);dummy={**raw,'properties':{**raw['properties'],**props}}
    normalize(dummy)
    if 'due' in fields and aware_date(fields['due'])<=timezone.now():raise ValueError('Novo horário deve estar no futuro.')
    if action=='create':
        duplicates=src.query('notifications',{'property':'Nome','title':{'equals':fields['title']}})
        for item in duplicates:
            try:
                normalized,_=normalize(item)
                if normalized['due']==aware_date(fields['due']):return {'duplicate':True,'url':item['url'],'message':'Aviso equivalente já existe. Nenhuma duplicata criada.'}
            except (ValueError,KeyError):continue
    key=hashlib.sha256((str(incoming.pk)+json.dumps(args,sort_keys=True)).encode()).hexdigest()
    op,created=Operation.objects.get_or_create(key=key,defaults={'incoming':incoming,'kind':'notice','payload':args,'expires':timezone.now()+timedelta(hours=1)})
    if not created:
        if op.state=='done':return op.result
        raise ValueError('Operação anterior não está confirmada; conferir Notion antes de repetir.')
    op.state='running';op.save(update_fields=['state'])
    clean={k:{t:v for t,v in p.items() if t!='type'} for k,p in props.items()}
    try:
        if action=='create':
            # POST sem retries: timeout pode ter criado a página. Evita duplicação automática.
            r=requests.post('https://api.notion.com/v1/pages',headers={'Authorization':'Bearer '+os.environ['NOTION_TOKEN'],'Notion-Version':'2025-09-03'},json={'parent':{'data_source_id':ref('notifications')},'properties':clean},timeout=20)
            if not r.ok:raise APIError(r.status_code)
            page_id=r.json()['id']
        else:src.notion.request('PATCH','pages/'+uid(page_id),{'properties':clean})
        actual=src.notion.request('GET','pages/'+uid(page_id))
        for name in props:
            actual_value=value(actual['properties'][name]);expected=value(props[name])
            if SCHEMA[name]=='date':
                same=(actual_value is None and expected is None) or (actual_value is not None and expected is not None and aware_date(actual_value['start'])==aware_date(expected['start']))
            else:same=actual_value==expected
            if not same:raise ValueError('Verificação divergente; conferir o registro no Notion.')
        result={'url':actual['url'],'id':page_id,'verified':True}
        op.state='done';op.result=result;op.save(update_fields=['state','result']);return result
    except Exception:
        op.state='unknown';op.save(update_fields=['state']);raise ValueError('Resultado da escrita incerto. Confira o Notion e a operação no painel antes de repetir.')


def week_plan(src,incoming,args):
    focus=args.get('focus',[])
    if not isinstance(focus,list) or len(focus)>3 or any(not isinstance(x,str) or len(x)>300 for x in focus):raise ValueError('No máximo três focos textuais semanais.')
    entries=args.get('entries',[])
    if not isinstance(entries,list) or not entries or len(entries)>20:raise ValueError('Proposta deve conter 1–20 blocos de tarefas existentes.')
    if len({uid(e['task_id']) for e in entries})!=len(entries):raise ValueError('Uma tarefa só pode ter um bloco nesta proposta.')
    # Releitura de fontes obrigatórias, sem confiar em contexto fabricado pelo modelo.
    context=src.context('weekly')
    for entry in entries:
        task=src.page(entry['task_id'])
        if task['archived'] or task['properties'].get('Status') not in ('Entrada','Planejada','Em andamento'):raise ValueError('Tarefa não elegível.')
        entry['snapshot']=task['last_edited_time']
        entry['title']=task['properties'].get('Tarefa','Tarefa')
        entry['energy']=task['properties'].get('Energia')
        start=aware_date(entry['start']);end=aware_date(entry['end'])
        if end<=start or start<=timezone.now():raise ValueError('Bloco inválido ou passado.')
        duration=task['properties'].get('Duração (min)')
        if not duration or abs((end-start).total_seconds()/60-duration)>1:raise ValueError('Duração registrada ausente ou divergente; não inventar.')
        for relation in task['properties'].get('Projeto',{}).get('ids',[]):src.page(relation)
    payload={**args,'sources':{'manual':context['manual']['last_edited_time'],'hours':context['hours']['last_edited_time'],'memory':context['memory']['last_edited_time'],'weeks':[(w['id'],w['last_edited_time']) for w in context['weeks']]}}
    op=Operation.objects.create(key='week:'+str(incoming.pk),incoming=incoming,kind='week',payload=payload,expires=timezone.now()+timedelta(hours=1))
    lines=['Proposta de semana — ainda não registrada.','Focos: '+', '.join(args.get('focus',[]))]
    lines.extend(f"{e['title']}: {e['start']} → {e['end']}" for e in entries)
    lines.append(args.get('rationale',''))
    lines.extend(context['limitations'])
    lines.append('Aplicar só será permitido após validar janelas confirmadas no Notion, capacidade e Calendar. Sem isso, a proposta permanece provisória.')
    enqueue('proposal:'+str(op.pk),'\n'.join(lines),[[{'text':'Aplicar proposta','callback_data':'apply:'+op.pk.hex},{'text':'Cancelar','callback_data':'cancel:'+op.pk.hex}]])
    return {'proposal_id':str(op.pk),'state':'pending','message':'Proposta enviada com botão de aplicação; não afirmar escrita.'}

def validated_plan(src,payload):
    from .calendar_api import Calendar
    context=src.context('weekly')
    if context['calendar'] is None:raise ValueError('Conecte o Calendar antes de registrar blocos de execução.')
    if len(context['weeks'])!=1:raise ValueError('Semana do período ausente/ambígua; conferir o Notion.')
    for name in ['manual','hours','memory']:
        if context[name]['last_edited_time']!=payload['sources'][name]:raise ValueError('Fonte mudou; gere uma proposta atualizada.')
    current_weeks=[(w['id'],w['last_edited_time']) for w in context['weeks']]
    if [list(x) for x in current_weeks]!=[list(x) for x in payload['sources']['weeks']]:raise ValueError('Semana mudou; refaça a proposta.')
    windows={};in_windows=False
    days=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo']
    for row in context['hours']['content']:
        text=row['text']
        if text.startswith('Dia | Janela autorizada'):in_windows=True;continue
        if in_windows and row['type']=='table_row':
            cells=text.split(' | ')
            if cells[0] in days and len(cells)>1:
                times=re.findall(r'\b\d{2}:\d{2}\b',cells[1])
                if len(times)==2 and 'a confirmar' not in text.lower():windows[days.index(cells[0])]=times
    if not windows:raise ValueError('As janelas utilizáveis no Notion ainda estão A confirmar. A proposta permanece provisória; registre janelas confirmadas antes de aplicar.')
    week=context['weeks'][0];capacity=week['properties'].get('Capacidade (h)')
    if not capacity or capacity<=0:raise ValueError('Capacidade da semana não registrada; não inventar.')
    entries=payload['entries'];dates=set();total=0;high={};intervals=[];events=context['calendar'];now=datetime.now(TZ)
    for entry in entries:
        task=src.page(entry['task_id'])
        if task['last_edited_time']!=entry['snapshot']:raise ValueError('Tarefa mudou desde a proposta; refaça.')
        if task['properties'].get('Status') not in ('Entrada','Planejada','Em andamento'):raise ValueError('Tarefa já não está elegível.')
        a=aware_date(entry['start']).astimezone(TZ);b=aware_date(entry['end']).astimezone(TZ)
        if a.date()!=b.date() or a<=now or a.date()>now.date()+timedelta(days=6-now.weekday()):raise ValueError('A aplicação está limitada à semana atual e a blocos futuros no mesmo dia.')
        if a.weekday() not in windows:raise ValueError('Janela desse dia não está confirmada no Notion.')
        low,upper=windows[a.weekday()]
        if not low<=a.strftime('%H:%M')<b.strftime('%H:%M')<=upper:raise ValueError('Bloco fora da janela confirmada.')
        if any(a<y and b>x for x,y in intervals):raise ValueError('Blocos da proposta se sobrepõem.')
        intervals.append((a,b));total+=(b-a).total_seconds()/3600
        if entry['energy']=='Alta':
            high[a.date()]=high.get(a.date(),0)+1
            if high[a.date()]>1:raise ValueError('Mais de uma tarefa de alta energia no mesmo dia.')
        matches=[]
        for event in events:
            marked=event['private'].get('notion_task')==entry['task_id'] or uid(entry['task_id']).replace('-','') in event['description'].replace('-','')
            if marked:matches.append(event);continue
            if event['transparency']=='transparent':continue
            start=event['start'].get('dateTime') or event['start'].get('date');end=event['end'].get('dateTime') or event['end'].get('date')
            if 'T' not in start:start+='T00:00:00-03:00';end+='T00:00:00-03:00'
            if a<aware_date(end) and b>aware_date(start):raise ValueError('Conflito com compromisso existente no Calendar.')
        if len(matches)>1:raise ValueError('Mais de um evento espelho para a tarefa; resolver duplicatas antes de aplicar.')
        entry['event']=matches[0] if matches else None
        old=task['properties'].get('Executar em')
        if old and old.get('start'):
            # Se o evento antigo está fora desta semana, não criar novo sem localizar o espelho antigo.
            old_start=old['start']
            if 'T' in old_start and not entry['event']:
                old_day=aware_date(old_start).astimezone(TZ).date()
                older=Calendar().events(old_day,old_day)
                old_matches=[e for e in older if e['private'].get('notion_task')==entry['task_id'] or uid(entry['task_id']).replace('-','') in e['description'].replace('-','')]
                if len(old_matches)!=1:raise ValueError('Evento espelho anterior não localizado de forma única. Não criar duplicata.')
                entry['event']=old_matches[0]
    selected={uid(e['task_id']) for e in entries}
    for task in context['tasks']:
        p=task['properties'];date=p.get('Executar em')
        if uid(task['id']) in selected or not date:continue
        start=date.get('start','')
        if 'T' in start:
            when=aware_date(start).astimezone(TZ)
            if now.date()-timedelta(days=now.weekday())<=when.date()<=now.date()+timedelta(days=6-now.weekday()):
                duration=p.get('Duração (min)')
                if not duration:raise ValueError('Tarefa já planejada sem duração; capacidade incompleta.')
                total+=duration/60
                if p.get('Energia')=='Alta' and high.get(when.date(),0):raise ValueError('Alta energia já ocupada no dia.')
    if total>capacity*.75:raise ValueError('Plano supera 75% da capacidade registrada.')
    return context,entries

def apply_week(src,op):
    if op.state!='pending' or op.expires<timezone.now():raise ValueError('Proposta expirada ou já processada.')
    context,entries=validated_plan(src,op.payload)
    from .calendar_api import Calendar
    calendar=Calendar();op.state='running';op.save(update_fields=['state'])
    results=[]
    try:
        for entry in entries:
            # Sem supor transação distribuída: registrar progresso por item para revisão em falha.
            calendar_event=calendar.mirror(entry['task_id'],entry['title'],entry['start'],entry['end'],entry['event'])
            results.append({'task':entry['task_id'],'calendar':calendar_event['id'],'notion':False})
            op.result={'items':results};op.save(update_fields=['result'])
            patch={'Executar em':{'date':{'start':entry['start'],'end':entry['end']}},'Semana':{'relation':[{'id':context['weeks'][0]['id']}]}}
            src.notion.request('PATCH','pages/'+uid(entry['task_id']),{'properties':patch})
            check=src.notion.request('GET','pages/'+uid(entry['task_id']))
            actual=value(check['properties']['Executar em'])
            if aware_date(actual['start'])!=aware_date(entry['start']) or aware_date(actual['end'])!=aware_date(entry['end']):raise ValueError('Execução não verificada no Notion.')
            results[-1]['notion']=True;op.result={'items':results};op.save(update_fields=['result'])
        focuses=op.payload.get('focus',[])
        props={f'Foco {i+1}':{'rich_text':[{'text':{'content':focuses[i]}}] if i<len(focuses) else []} for i in range(3)}
        src.notion.request('PATCH','pages/'+context['weeks'][0]['id'],{'properties':props})
        check=src.notion.request('GET','pages/'+context['weeks'][0]['id'])
        if any(value(check['properties'][f'Foco {i+1}'])!=(focuses[i] if i<len(focuses) else '') for i in range(3)):raise ValueError('Focos não verificados.')
        op.state='done';op.save(update_fields=['state']);return 'Plano registrado no Notion e espelhado no Calendar. Prazos, prioridades e conclusões preservados.'
    except Exception:
        op.state='partial';op.save(update_fields=['state']);raise ValueError('Aplicação parcial/incerta. Consulte Operation no painel e Calendar/Notion antes de reaplicar. Nenhum rollback automático destrutivo foi feito.')
