import os,json
from datetime import datetime,timedelta
from unittest.mock import patch,Mock
from django.test import TestCase
from django.utils import timezone
from .models import Incoming,Outgoing,Operation,DailyBriefing,ModelUsage
from .gateway import receive,enqueue,flush
from .sources import Source,DEFAULTS,value
from .operations import properties,notice,validated_plan
from .management.commands.assistant_worker import schedule_daily,process
from notifications.api import APIError
from notifications.models import Runtime
from notifications.engine import poll

class GatewayTests(TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{'TELEGRAM_USER_ID':'123','TELEGRAM_CHAT_ID':'123'});p.start();self.addCleanup(p.stop)
    def update(self,id=1,user=123,text='Olá'):return {'update_id':id,'message':{'from':{'id':user},'chat':{'id':123},'text':text}}
    def test_ingestion_idempotent(self):
        receive(self.update());receive(self.update());self.assertEqual(Incoming.objects.count(),1)
    def test_unauthorized_ignored(self):
        receive(self.update(user=99));self.assertFalse(Incoming.objects.exists())
    def test_unsupported_media_replied(self):
        u=self.update();del u['message']['text'];receive(u);self.assertTrue(Outgoing.objects.exists())
    def test_old_notification_buttons_routed_unchanged(self):self.assertFalse(receive({'callback_query':{'data':'ack:uuid:0'}}))
    def test_poller_single_offset_messages(self):
        t=Mock();t.call.return_value=[self.update()];poll(t)
        self.assertEqual(Runtime.objects.get(key='telegram_offset').value,'2');self.assertEqual(Incoming.objects.count(),1)
        poll(t);self.assertEqual(Incoming.objects.count(),1)
    def test_outgoing_chunks_idempotent(self):
        enqueue('x','a'*8000);enqueue('x','a'*8000);self.assertEqual(Outgoing.objects.count(),3)
    def test_uncertain_reply_not_automatically_retried(self):
        enqueue('x','Olá');t=Mock();t.call.side_effect=APIError();flush(t);flush(t)
        self.assertEqual(t.call.call_count,1);self.assertEqual(Outgoing.objects.get().state,'unknown')
    def test_429_scheduled_retry(self):
        enqueue('x','Olá');t=Mock();t.call.side_effect=APIError(429,180);flush(t)
        obj=Outgoing.objects.get();self.assertEqual(obj.state,'queued');self.assertGreater(obj.next_try,timezone.now()+timedelta(seconds=150))
    def test_proposal_callback_bound_to_sent_message(self):
        item=Incoming.objects.create(update_id=3,text='organize');op=Operation.objects.create(key='p',incoming=item,kind='week',expires=timezone.now()+timedelta(hours=1))
        q={'update_id':4,'callback_query':{'data':'apply:'+op.pk.hex,'from':{'id':123},'message':{'chat':{'id':123},'message_id':99}}}
        receive(q);self.assertEqual(Incoming.objects.count(),1)
        Outgoing.objects.create(key=f'proposal:{op.pk}:0',text='proposta',state='sent',message_id=99)
        receive(q);self.assertEqual(Incoming.objects.filter(kind='apply').count(),1)

class ScheduleTests(TestCase):
    @patch.dict(os.environ,{'DAILY_BRIEFING_TIME':'08:00','DAILY_BRIEFING_ENABLED':'true'})
    def test_exact_time_and_no_duplicate(self):
        schedule_daily(datetime.fromisoformat('2026-10-12T07:59:00-03:00'));self.assertFalse(Incoming.objects.exists())
        schedule_daily(datetime.fromisoformat('2026-10-12T08:00:00-03:00'));schedule_daily(datetime.fromisoformat('2026-10-12T08:05:00-03:00'))
        self.assertEqual(Incoming.objects.count(),1);self.assertEqual(DailyBriefing.objects.count(),1)
    @patch.dict(os.environ,{'DAILY_BRIEFING_TIME':'08:00','DAILY_BRIEFING_ENABLED':'true'})
    def test_no_old_briefing_at_night(self):
        schedule_daily(datetime.fromisoformat('2026-10-12T21:00:00-03:00'));self.assertFalse(Incoming.objects.exists())
    def test_worker_failure_is_not_replayed(self):
        item=Incoming.objects.create(update_id=1,text='Olá')
        with patch('conversation.management.commands.assistant_worker.reply',side_effect=ValueError('teste')):process(item)
        item.refresh_from_db();self.assertEqual(item.state,'failed');self.assertTrue(Outgoing.objects.exists())

class SourceTests(TestCase):
    def test_query_complete_pagination(self):
        n=Mock();n.request.side_effect=[{'properties':{}},{'results':[{'id':'a'}],'has_more':True,'next_cursor':'c'},{'results':[{'id':'b'}],'has_more':False}]
        self.assertEqual(len(Source(n).query('tasks')),2)
    def test_incomplete_query_rejected(self):
        n=Mock();n.request.side_effect=[{'properties':{}},{'results':[],'has_more':False,'request_status':{'incomplete_reason':'limit'}}]
        with self.assertRaises(ValueError):Source(n).query('tasks')
    def test_foreign_page_rejected(self):
        n=Mock();n.request.return_value={'parent':{'data_source_id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}}
        with self.assertRaises(ValueError):Source(n).page('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
    def test_block_tables_preserved(self):
        n=Mock();n.request.return_value={'has_more':False,'results':[{'type':'table_row','table_row':{'cells':[[{'plain_text':'Segunda'}],[{'plain_text':'19:00–20:00'}]]}}]}
        self.assertEqual(Source(n).blocks('x')[0]['text'],'Segunda | 19:00–20:00')
    def test_protected_fields_not_allowed(self):
        with self.assertRaises(ValueError):properties({'priority':'P1'})
    def test_date_without_timezone_rejected(self):
        with self.assertRaises(ValueError):properties({'due':'2026-10-12T18:00:00'})
    def test_notice_requires_current_explicit_request(self):
        i=Incoming.objects.create(update_id=1,text='Bom dia')
        with self.assertRaises(ValueError):notice(Mock(),i,{'authorization_quote':'Bom dia','action':'create','fields':{}})
    def test_readonly_daily_cannot_write(self):
        from .assistant import dispatch
        with self.assertRaises(ValueError):dispatch(Mock(),Mock(),'notice',{},readonly=True)
    def test_unknown_windows_block_apply(self):
        context={'calendar':[],'manual':{'last_edited_time':'x'},'memory':{'last_edited_time':'x'},'hours':{'last_edited_time':'x','content':[{'type':'table_row','text':'Dia | Janela autorizada | Situação'},{'type':'table_row','text':'Segunda | A confirmar | Não contar como capacidade'}]},'weeks':[{'id':'w','last_edited_time':'x'}]}
        src=Mock();src.context.return_value=context
        payload={'sources':{'manual':'x','memory':'x','hours':'x','weeks':[['w','x']]},'entries':[]}
        with self.assertRaisesRegex(ValueError,'janelas'):validated_plan(src,payload)
    def test_missing_calendar_blocks_apply(self):
        src=Mock();src.context.return_value={'calendar':None}
        with self.assertRaisesRegex(ValueError,'Calendar'):validated_plan(src,{})

class CodexTests(TestCase):
    def test_gateway_has_no_business_credentials(self):
        from .codex_gateway import infer
        import tempfile
        class Child:
            returncode=0;pid=3
            def communicate(self,prompt,timeout):
                command=fake.call_args.args[0];path=command[command.index('-o')+1]
                from pathlib import Path
                Path(path).write_text(json.dumps({'text':'Olá','calls':[]}))
                return '',''
        with patch.dict(os.environ,{'NOTION_TOKEN':'secret','TELEGRAM_BOT_TOKEN':'secret','OPENAI_API_KEY':'secret','CODEX_HOME':'/tmp/test'}),patch('conversation.codex_gateway.subprocess.Popen',return_value=Child()) as fake:
            self.assertEqual(infer('prompt')['text'],'Olá')
            env=fake.call_args.kwargs['env'];self.assertNotIn('NOTION_TOKEN',env);self.assertNotIn('OPENAI_API_KEY',env)
            self.assertIn('read-only',fake.call_args.args[0])

class NoticeWriteTests(TestCase):
    def test_creation_verified_with_rest_date_shape(self):
        from notifications.engine import SCHEMA
        from conversation.operations import properties
        from copy import deepcopy
        now=(timezone.now()+timedelta(hours=2)).replace(microsecond=0).isoformat()
        fields={'title':'Teste','message':'Texto','kind':'Mensagem','due':now,'active':True,'insistent':False,'repeat_minutes':30,'max_attempts':1,'recurrence_days':0}
        props=properties(fields)
        props.update({'Link':{'type':'url','url':None},'Alvo':{'type':'number','number':None},'Progresso':{'type':'number','number':None},'Tarefa':{'type':'relation','relation':[],'has_more':False},'Última confirmação':{'type':'date','date':None}})
        actual=deepcopy(props);actual['Enviar em']['date'].update({'end':None,'time_zone':None})
        src=Mock();src.schema.return_value={k:{'type':v} for k,v in SCHEMA.items()};src.query.return_value=[]
        src.notion.request.return_value={'properties':actual,'url':'https://notion.so/test'}
        incoming=Incoming.objects.create(update_id=1,text='Crie um aviso Teste')
        r=Mock(ok=True);r.json.return_value={'id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}
        with patch.dict(os.environ,{'NOTION_TOKEN':'secret','NOTION_DATA_SOURCE_ID':'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'}),patch('conversation.operations.requests.post',return_value=r) as req:
            result=notice(src,incoming,{'action':'create','fields':fields,'authorization_quote':incoming.text})
        self.assertTrue(result['verified']);self.assertEqual(Operation.objects.get().state,'done');self.assertEqual(req.call_count,1)
    def test_new_schema_never_changes_old_notifications(self):
        from notifications.models import Reminder
        self.assertNotIn('conversation',Reminder._meta.db_table)
    def test_daily_briefing_works_without_model(self):
        from .briefing import render
        ctx={'now':'2026-10-12T08:00:00-03:00','tasks':[],'weeks':[],'calendar':None,'limitations':['Agenda incompleta.']}
        text=render(ctx)
        self.assertIn('briefing parcial',text.lower());self.assertIn('12/10/2026',text)
