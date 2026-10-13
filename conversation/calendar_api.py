import os, hashlib
from datetime import datetime, timedelta, time
from urllib.parse import quote
import requests
from notifications.api import APIError
from .sources import TZ

class Calendar:
    def __init__(self):self.token=None
    def access(self):
        if self.token:return self.token
        keys=['GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_REFRESH_TOKEN']
        if not all(os.getenv(k) for k in keys):raise ValueError('Configure a conexão Google Calendar.')
        try:r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':os.environ[keys[0]],'client_secret':os.environ[keys[1]],'refresh_token':os.environ[keys[2]],'grant_type':'refresh_token'},timeout=20)
        except requests.RequestException:raise APIError()
        if not r.ok:raise APIError(r.status_code)
        self.token=r.json()['access_token'];return self.token
    def request(self,method,calendar,path,payload=None,params=None):
        try:r=requests.request(method,'https://www.googleapis.com/calendar/v3/calendars/'+quote(calendar,safe='')+'/'+path,headers={'Authorization':'Bearer '+self.access()},json=payload,params=params,timeout=20)
        except requests.RequestException:raise APIError()
        if not r.ok:raise APIError(r.status_code)
        return r.json()
    def events(self,first,last):
        rows=[]
        for calendar in os.getenv('GOOGLE_CALENDAR_IDS','primary').split(','):
            params={'timeMin':datetime.combine(first,time.min,TZ).isoformat(),'timeMax':datetime.combine(last+timedelta(days=1),time.min,TZ).isoformat(),'singleEvents':'true','orderBy':'startTime','maxResults':250}
            while True:
                data=self.request('GET',calendar,'events',params=params)
                rows.extend({'id':x['id'],'calendar':calendar,'title':x.get('summary','Compromisso'),'start':x['start'],'end':x['end'],'transparency':x.get('transparency','opaque'),'description':x.get('description',''),'private':x.get('extendedProperties',{}).get('private',{})} for x in data.get('items',[]) if x.get('status')!='cancelled')
                if len(rows)>1500:raise ValueError('Agenda excede limite; consulta incompleta.')
                if not data.get('nextPageToken'):break
                params['pageToken']=data['nextPageToken']
        return rows
    def mirror(self,task_id,title,start,end,existing=None):
        calendar=os.getenv('GOOGLE_WRITE_CALENDAR_ID','primary')
        event_id='secretaria'+hashlib.sha256(task_id.encode()).hexdigest()[:40]
        body={'summary':title,'start':{'dateTime':start,'timeZone':'America/Sao_Paulo'},'end':{'dateTime':end,'timeZone':'America/Sao_Paulo'},'extendedProperties':{'private':{'notion_task':task_id}},'reminders':{'useDefault':False,'overrides':[{'method':'email','minutes':1440},{'method':'popup','minutes':60},{'method':'popup','minutes':10}]}}
        if existing:
            return self.request('PATCH',existing['calendar'],'events/'+existing['id'],body)
        try:return self.request('POST',calendar,'events',{**body,'id':event_id})
        except APIError as exc:
            if exc.status==409:return self.request('PATCH',calendar,'events/'+event_id,body)
            raise
