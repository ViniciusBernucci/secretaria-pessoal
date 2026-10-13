import os
from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import Reminder, Delivery, Runtime, Writeback
from .engine import sync, send_due, handle_update, poll, writebacks, quiet, finish, normalize, SCHEMA
from .api import APIError, Notion

def page(now=None, active=True):
    now = now or timezone.now()
    values = {"Nome":"Teste", "Mensagem":"Mensagem", "Tipo":"Tarefa", "Ativo":active, "Enviar em":now.isoformat(), "Insistente":True, "Intervalo (min)":5, "Máximo de avisos":3, "Recorrência (dias)":0, "Link":None, "Alvo":None, "Progresso":None, "Última confirmação":None, "Tarefa":[]}
    props = {}
    for name, kind in SCHEMA.items():
        value = values[name]
        if kind in {"title","rich_text"}: value = [{"plain_text":value}]
        elif kind == "select": value = {"name":value}
        elif kind == "date": value = {"start":value} if value else None
        props[name] = {"type":kind, kind:value}
    return {"id":"11111111-1111-1111-1111-111111111111", "url":"https://notion.so/test", "properties":props}

@patch.dict(os.environ, {"TELEGRAM_CHAT_ID":"123", "TELEGRAM_USER_ID":"123", "NOTION_DATA_SOURCE_ID":"ds", "QUIET_START":"00:00", "QUIET_END":"00:00"})
class EngineTests(TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"TELEGRAM_CHAT_ID":"123", "TELEGRAM_USER_ID":"123", "NOTION_DATA_SOURCE_ID":"ds", "QUIET_START":"00:00", "QUIET_END":"00:00"})
        env.start()
        self.addCleanup(env.stop)
        self.now = timezone.now()
        self.notion = Mock()
        self.p = page(self.now - timedelta(minutes=1))
        self.notion.pages.return_value = [self.p]
        self.notion.request.side_effect = lambda method,path,*args: {"properties":{k:{"type":v} for k,v in SCHEMA.items()}} if path.startswith("data_sources") else self.p
        sync(self.notion)
        self.obj = Reminder.objects.get()
        self.telegram = Mock()
        self.telegram.call.return_value = {"message_id":99}
    def update(self, action="ack", user=123, cycle=None):
        return {"callback_query":{"id":"cb", "from":{"id":user}, "message":{"chat":{"id":123},"message_id":99}, "data":f"{action}:{self.obj.pk.hex}:{self.obj.cycle if cycle is None else cycle}"}}
    def send(self): send_due(self.notion,self.telegram)
    def test_delivery_and_no_duplicate_after_restart(self):
        self.send(); self.send()
        self.assertEqual(Delivery.objects.count(),1)
        self.assertEqual(self.telegram.call.call_count,1)
    def test_ack_persisted_and_sync_does_not_reopen(self):
        self.send(); handle_update(self.update(),self.telegram); sync(self.notion)
        self.obj.refresh_from_db()
        self.assertTrue(self.obj.acknowledged)
        self.assertIsNone(self.obj.next_send)
        self.assertEqual(Writeback.objects.count(),1)
        handle_update(self.update(),self.telegram)
        self.assertEqual(Writeback.objects.count(),1)
    def test_unauthorized_user_and_old_cycle(self):
        self.send(); handle_update(self.update(user=456),self.telegram)
        handle_update(self.update(cycle=999),self.telegram)
        self.assertEqual(Writeback.objects.count(),0)
    def test_unknown_send_blocks_retry(self):
        self.telegram.call.side_effect = APIError()
        self.send()
        self.assertEqual(Delivery.objects.get().state,"unknown")
        Reminder.objects.update(next_send=self.now)
        self.send()
        self.assertEqual(self.telegram.call.call_count,1)
    def test_429_retry_not_unknown(self):
        self.telegram.call.side_effect = APIError(429,120)
        self.send()
        self.assertEqual(Delivery.objects.get().state,"retry")
        self.obj.refresh_from_db()
        self.assertGreater(self.obj.next_send,self.now+timedelta(seconds=100))
    def test_partial_snapshot_does_not_disable(self):
        self.notion.pages.side_effect = APIError()
        with self.assertRaises(APIError): sync(self.notion)
        self.obj.refresh_from_db(); self.assertTrue(self.obj.active)
    def test_removed_record_disabled(self):
        self.notion.pages.return_value=[]; sync(self.notion)
        self.obj.refresh_from_db(); self.assertFalse(self.obj.active)
    def test_date_without_time_rejected(self):
        self.p["properties"]["Enviar em"]["date"]["start"]="2026-10-12"
        with self.assertRaises(ValueError): normalize(self.p)
    def test_reschedule_new_cycle(self):
        self.p["properties"]["Enviar em"]["date"]["start"]=(self.now+timedelta(days=1)).isoformat()
        sync(self.notion);self.obj.refresh_from_db()
        self.assertEqual(self.obj.cycle,1);self.assertEqual(self.obj.next_send,self.obj.due)
    def test_recurrence_skips_missed(self):
        self.obj.due=self.now-timedelta(days=10); self.obj.recurrence_days=1
        finish(self.obj,self.now)
        self.assertGreater(self.obj.next_send,self.now)
        self.assertEqual(self.obj.attempts,0)
    def test_writeback_retries(self):
        self.send();handle_update(self.update(),self.telegram)
        self.notion.request.side_effect=APIError()
        writebacks(self.notion)
        self.assertFalse(Writeback.objects.get().done)
        self.assertEqual(Writeback.objects.get().retries,1)
    def test_quiet_crosses_midnight(self):
        from datetime import datetime
        with patch.dict(os.environ,{"QUIET_START":"22:00","QUIET_END":"07:00"}):
            self.assertTrue(quiet(datetime.fromisoformat("2026-10-12T23:00:00-03:00")))
            self.assertFalse(quiet(datetime.fromisoformat("2026-10-12T10:00:00-03:00")))
    def test_poll_offset_and_ack_atomic(self):
        self.send()
        self.telegram.call.side_effect=lambda method,**kwargs: [{**self.update(),"update_id":42}] if method=="getUpdates" else True
        poll(self.telegram)
        self.assertEqual(Runtime.objects.get(key="telegram_offset").value,"43")
        self.assertEqual(Writeback.objects.count(),1)
    def test_stale_sync_blocks_send(self):
        Runtime.objects.filter(key="sync").update(value=(self.now-timedelta(minutes=5)).isoformat())
        self.send();self.assertEqual(Delivery.objects.count(),0)
    def test_task_completed_suppresses(self):
        self.p["properties"]["Tarefa"]["relation"]=[{"id":"task"}]
        base=self.notion.request.side_effect
        self.notion.request.side_effect=lambda method,path,*args: {"properties":{"Status":{"type":"status","status":{"name":"Concluída"}}}} if path=="pages/task" else base(method,path,*args)
        self.send();self.assertEqual(Delivery.objects.count(),0)
    def test_one_shot_ack_button_works(self):
        self.p["properties"]["Insistente"]["checkbox"]=False
        sync(self.notion);self.obj.refresh_from_db()
        self.send();handle_update(self.update(),self.telegram)
        self.assertEqual(Writeback.objects.count(),1)

    def test_pause_survives_sync(self):
        self.send(); handle_update(self.update(action="pause"),self.telegram); sync(self.notion)
        self.obj.refresh_from_db();self.assertTrue(self.obj.paused)
    def test_snooze_updates_schedule(self):
        self.send();handle_update(self.update(action="snooze"),self.telegram)
        self.obj.refresh_from_db();self.assertGreater(self.obj.next_send,self.now+timedelta(minutes=29))
    def test_limit_stops_insistence(self):
        Reminder.objects.update(attempts=3,next_send=self.now)
        self.send();self.obj.refresh_from_db()
        self.assertIsNone(self.obj.next_send);self.assertEqual(Delivery.objects.count(),0)
    def test_external_ack_prevents_send(self):
        self.p["properties"]["Última confirmação"]["date"]={"start":self.now.isoformat()}
        self.send();self.assertEqual(Delivery.objects.count(),0)
    def test_recurrent_ack_not_reapplied_to_next_occurrence(self):
        self.p["properties"]["Recorrência (dias)"]["number"]=7
        sync(self.notion);self.obj.refresh_from_db();self.send()
        handle_update(self.update(),self.telegram)
        self.p["properties"]["Última confirmação"]["date"]={"start":self.now.isoformat()}
        sync(self.notion);self.obj.refresh_from_db()
        self.assertEqual(self.obj.cycle,1)
        self.assertGreater(self.obj.next_send,self.now+timedelta(days=6))

class PaginationTests(TestCase):
    def test_all_cursors(self):
        notion=Notion()
        with patch.dict(os.environ,{"NOTION_DATA_SOURCE_ID":"ds"}), patch.object(notion,"request",side_effect=[{"results":[1],"has_more":True,"next_cursor":"c"},{"results":[2],"has_more":False}]) as req:
            self.assertEqual(notion.pages(),[1,2]);self.assertEqual(req.call_args.args[2]["start_cursor"],"c")

class PanelTests(TestCase):
    def test_login_and_health(self):
        self.assertEqual(self.client.get('/admin/login/').status_code, 200)
        self.assertEqual(self.client.get('/health/').json(), {"status":"ok"})
    def test_admin_requires_login(self):
        self.assertEqual(self.client.get('/admin/').status_code,302)
    def test_edit_publishes_only_changed_property(self):
        from django.contrib.admin.sites import AdminSite
        from .admin import ReminderAdmin
        values, _ = normalize(page())
        obj = Reminder.objects.create(**values,occurrence_due=values['due'],next_send=values['due'])
        obj.message = "Texto novo"
        remote = page(values['due'])
        verified = page(values['due'])
        verified['properties']['Mensagem']['rich_text']=[{'plain_text':'Texto novo'}]
        fake = Mock()
        fake.request.side_effect=[remote,{},verified]
        form = Mock(changed_data=['message'])
        with patch('notifications.admin.Notion',return_value=fake):
            ReminderAdmin(Reminder,AdminSite()).save_model(Mock(),obj,form,True)
        patch_body=fake.request.call_args_list[1].args[2]
        self.assertEqual(set(patch_body['properties']),{'Mensagem'})
        obj.refresh_from_db(); self.assertEqual(obj.message,'Texto novo')
