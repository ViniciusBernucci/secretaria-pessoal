# Modelo público: copie para sources.py antes de executar ou construir a imagem.
# Não inclua credenciais ou IDs pessoais neste arquivo de exemplo.
import os, re, uuid
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from notifications.api import Notion, APIError

TZ=ZoneInfo('America/Sao_Paulo')
# Preencha os IDs pelas variáveis NOTION_*_ID no .env privado.
DEFAULTS={
 'manual':'',
 'memory':'',
 'hours':'',
 'tasks':'',
 'projects':'',
 'weeks':'',
}
def ref(name): return os.getenv('NOTION_'+name.upper()+'_ID',DEFAULTS.get(name,os.getenv('NOTION_DATA_SOURCE_ID','')))
def uid(value): return str(uuid.UUID(value))
def value(prop):
    kind=prop.get('type'); data=prop.get(kind)
    if kind in ('title','rich_text'):return ''.join(x.get('plain_text',x.get('text',{}).get('content','')) for x in data or [])
    if kind in ('select','status'):return (data or {}).get('name')
    if kind=='relation': return {'ids':[x['id'] for x in data or []],'has_more':prop.get('has_more',False)}
    return data

def summary(page):
    return {'id':page['id'],'url':page.get('url'),'last_edited_time':page.get('last_edited_time'),'properties':{k:value(v) for k,v in page.get('properties',{}).items()}}

class Source:
    def __init__(self,notion=None): self.notion=notion or Notion();self.schemas={};self.opened={}
    def schema(self,name):
        if name not in self.schemas:self.schemas[name]=self.notion.request('GET','data_sources/'+ref(name))['properties']
        return self.schemas[name]
    def query(self,name,filter=None):
        self.schema(name)
        rows=[];cursor=None
        while True:
            body={'page_size':100}
            if filter:body['filter']=filter
            if cursor:body['start_cursor']=cursor
            data=self.notion.request('POST','data_sources/'+ref(name)+'/query',body)
            if data.get('request_status',{}).get('incomplete_reason'):raise ValueError('Consulta incompleta; não afirmar ausência de pendências.')
            rows.extend(data['results'])
            if len(rows)>500:raise ValueError('Consulta supera 500 registros; refine os filtros.')
            if not data['has_more']:return rows
            cursor=data['next_cursor']
            if not cursor:raise ValueError('Paginação incompleta.')
    def page(self,page_id):
        page_id=uid(page_id)
        page=self.notion.request('GET','pages/'+page_id)
        parent=page.get('parent',{})
        allowed={uid(ref(n)) for n in ('tasks','projects','weeks','notifications') if ref(n)}
        ds=parent.get('data_source_id')
        if ds:okay=uid(ds) in allowed
        elif parent.get('database_id'):
            db=self.notion.request('GET','databases/'+parent['database_id'])
            okay=any(uid(x['id']) in allowed for x in db.get('data_sources',[]))
        else:okay=page_id in {uid(ref(n)) for n in ('manual','memory','hours')}
        if not okay:raise ValueError('Página fora das bases pessoais autorizadas.')
        result={**summary(page),'content':self.blocks(page_id),'archived':page.get('archived',False) or page.get('in_trash',False)}
        self.opened[page_id]=result
        return result
    def blocks(self,block_id):
        count=[0]
        def read(parent,depth=0):
            if depth>12:raise ValueError('Página profunda demais; leitura incompleta.')
            result=[];cursor=None
            while True:
                path='blocks/'+parent+'/children?page_size=100'+('&start_cursor='+cursor if cursor else '')
                data=self.notion.request('GET',path)
                for block in data['results']:
                    count[0]+=1
                    if count[0]>500:raise ValueError('Página supera limite de leitura; não usar resumo parcial como manual completo.')
                    kind=block['type'];body=block.get(kind,{})
                    text=''.join(x.get('plain_text',x.get('text',{}).get('content','')) for x in body.get('rich_text',[]))
                    if kind=='table_row':text=' | '.join(''.join(x.get('plain_text',x.get('text',{}).get('content','')) for x in cell) for cell in body['cells'])
                    if kind in ('child_page','child_database'):text=body.get('title','')
                    if kind in ('bookmark','link_preview','link_to_page'):text=str(body.get('url',body))
                    result.append({'type':kind,'text':text})
                    if block.get('has_children'):result.extend(read(block['id'],depth+1))
                if not data['has_more']:break
                cursor=data['next_cursor']
                if not cursor:raise ValueError('Leitura de blocos incompleta.')
            return result
        result=read(block_id)
        if sum(len(x['text']) for x in result)>90000:raise ValueError('Página grande demais; leitura completa necessária.')
        return result
    def tasks(self,mode='open',day=None):
        schema=self.schema('tasks'); status_type=schema['Status']['type']
        allowed={'or':[{'property':'Status',status_type:{'equals':x}} for x in ['Entrada','Planejada','Em andamento']]}
        if mode=='today':
            day=day or datetime.now(TZ).date()
            relevant={'or':[{'property':'Executar em','date':{'equals':day.isoformat()}},{'property':'Status',status_type:{'equals':'Em andamento'}},{'property':'Prazo real','date':{'on_or_before':(day+timedelta(days=7)).isoformat()}}]}
            allowed={'and':[allowed,relevant]}
        return self.query('tasks',allowed)
    def weeks(self,start,end):
        return self.query('weeks',{'and':[{'property':'Início','date':{'on_or_before':end.isoformat()}},{'property':'Fim','date':{'on_or_after':start.isoformat()}}]})
    def context(self,mode):
        now=datetime.now(TZ);day=now.date();start=day-timedelta(days=day.weekday());end=start+timedelta(days=6)
        result={'now':now.isoformat(),'timezone':'America/Sao_Paulo','manual':self.page(ref('manual')),'limitations':[]}
        # Manual nunca substituído pelo histórico da conversa.
        if mode not in ('daily','weekly'):result['memory']=self.page(ref('memory'));return result
        if mode=='weekly':
            result['memory']=self.page(ref('memory'));result['hours']=self.page(ref('hours'))
            tasks=self.tasks('open');first,last=start,end
        else:tasks=self.tasks('today',day);first=last=day
        result['tasks']=[summary(p) for p in tasks]
        weeks=self.weeks(first,last)
        result['weeks']=[self.page(p['id']) for p in weeks]
        if not weeks:result['limitations'].append('Não há semana cobrindo o período na consulta completa.')
        if mode=='weekly':
            result['projects']=[summary(p) for p in self.query('projects')]
            result['warning']='Antes de selecionar focos/blocos, abrir as páginas dos candidatos, projetos e dependências relevantes. Janelas desconhecidas não são livres.'
        from .calendar_api import Calendar
        try:result['calendar']=Calendar().events(first,last)
        except (ValueError,APIError):result['calendar']=None;result['limitations'].append('Google Calendar não consultado; agenda incompleta. Não registrar blocos como confirmados.')
        return result
