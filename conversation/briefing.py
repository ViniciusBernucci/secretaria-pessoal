from datetime import datetime,timedelta
from .sources import Source,TZ

def display_date(value):
    if not value:return 'sem data'
    raw=value.get('start') if isinstance(value,dict) else value
    if not raw:return 'sem data'
    if 'T' in raw:return datetime.fromisoformat(raw.replace('Z','+00:00')).astimezone(TZ).strftime('%d/%m %H:%M')
    return raw+' (sem horário)'

def render(context):
    now=datetime.fromisoformat(context['now']);day=now.date();tasks=context['tasks']
    def key(task):
        p=task['properties'];scheduled=p.get('Executar em') or {};start=scheduled.get('start','')
        if start.startswith(day.isoformat()) and 'T' in start:
            return (0,datetime.fromisoformat(start.replace('Z','+00:00')).timestamp(),'', '')
        return (1,0,p.get('Prioridade') or 'Z',(p.get('Prazo real') or {}).get('start','9999'))
    lines=[f'☀️ Briefing pessoal — {day.strftime("%d/%m/%Y")}','Fatos registrados; datas de execução não são prazos reais.']
    for week in context['weeks']:
        p=week['properties'];lines.append('Semana: '+str(p.get('Semana'))+' — '+str(p.get('Status')))
        lines.extend(f'Foco {i}: {p[f"Foco {i}"]}' for i in range(1,4) if p.get(f'Foco {i}'))
        lines.append(week['url'])
    if not tasks:lines.append('Nenhuma tarefa correspondeu aos filtros de hoje/em andamento/prazos até 7 dias na consulta completa.')
    for task in sorted(tasks,key=key)[:30]:
        p=task['properties'];lines.append(f"• {p.get('Tarefa','Tarefa')} — {p.get('Status')} — {p.get('Prioridade') or 'prioridade não informada'}")
        if p.get('Executar em'):lines.append('  Execução planejada: '+display_date(p['Executar em']))
        if p.get('Prazo real'):lines.append('  Prazo real: '+display_date(p['Prazo real']))
        lines.append(task['url'])
    if len(tasks)>30:lines.append(f'Mostradas 30 de {len(tasks)} tarefas consultadas. Peça uma consulta específica para as demais.')
    lines.append('Agenda Google Calendar:')
    if context['calendar'] is None:lines.append('Não consultada; briefing parcial de agenda.')
    elif not context['calendar']:lines.append('Nenhum evento no período consultado das agendas configuradas.')
    else:
        lines.extend(f"• {e['title']} — {display_date(e['start'])} → {display_date(e['end'])}" for e in context['calendar'][:30])
        if len(context['calendar'])>30:lines.append('Agenda exibida limitada a 30 eventos; há outros na consulta.')
    lines.extend('Limitação: '+s for s in context['limitations'])
    return '\n'.join(lines)

def daily(src=None):return render((src or Source()).context('daily'))
