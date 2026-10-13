import math, os
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from django.db import transaction
from django.utils import timezone
from .models import Reminder, Delivery, Writeback, Runtime, Event
from .api import Notion, Telegram, APIError

SCHEMA = {"Nome": "title", "Mensagem": "rich_text", "Tipo": "select", "Ativo": "checkbox", "Enviar em": "date", "Insistente": "checkbox", "Intervalo (min)": "number", "Máximo de avisos": "number", "Recorrência (dias)": "number", "Link": "url", "Alvo": "number", "Progresso": "number", "Última confirmação": "date", "Tarefa": "relation"}
KINDS = {"Tarefa", "Objetivo", "Meta", "Mensagem"}

def event(category, detail):
    Event.objects.create(category=category, detail=str(detail)[:250])

def get_value(properties, name):
    prop = properties[name]
    kind = SCHEMA[name]
    value = prop.get(kind)
    if kind in {"title", "rich_text"}: return "".join(x.get("plain_text", x.get("text", {}).get("content", "")) for x in value)
    if kind == "select": return value["name"] if value else ""
    if kind == "date": return value["start"] if value else None
    return value

def aware_date(value):
    if not value or "T" not in value: raise ValueError("Enviar em exige data e horário explícitos")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None: raise ValueError("Enviar em exige fuso horário")
    return dt

def number(value, default, low, high):
    value = default if value is None else value
    if int(value) != value or not low <= value <= high: raise ValueError("Valor numérico fora dos limites")
    return int(value)

def normalize(page):
    p = page["properties"]
    for name, kind in SCHEMA.items():
        if name not in p or p[name].get("type") != kind: raise ValueError(f"Campo ausente ou tipo incorreto: {name}")
    v = lambda name: get_value(p, name)
    if not v("Nome") or len(v("Nome")) > 200: raise ValueError("Nome deve ter 1–200 caracteres")
    if v("Tipo") not in KINDS: raise ValueError("Tipo desconhecido")
    return dict(notion_id=page["id"], title=v("Nome"), message=v("Mensagem"), kind=v("Tipo"), link=v("Link") or page["url"], active=bool(v("Ativo")) and not page.get("archived", False) and not page.get("in_trash", False), due=aware_date(v("Enviar em")), repeat_minutes=number(v("Intervalo (min)"),30,5,1440), max_attempts=number(v("Máximo de avisos"),8,1,100) if v("Insistente") else 1, recurrence_days=number(v("Recorrência (dias)"),0,0,365), target=v("Alvo"), progress=v("Progresso")), v("Última confirmação")

def sync(notion):
    schema = notion.request("GET", "data_sources/" + os.environ["NOTION_DATA_SOURCE_ID"])
    for name, kind in SCHEMA.items():
        if schema.get("properties", {}).get(name, {}).get("type") != kind:
            raise ValueError(f"Estrutura da base: {name} deve ser {kind}")
    pages = notion.pages()  # nenhuma alteração local até receber todas as páginas
    normalized, invalid = [], []
    for page in pages:
        try: normalized.append((page["id"], normalize(page)))
        except (KeyError, TypeError, ValueError) as exc: invalid.append((page["id"], str(exc)))
    now = timezone.now()
    with transaction.atomic():
        seen = [page["id"] for page in pages]
        Reminder.objects.exclude(notion_id__in=seen).update(active=False)
        for page_id, reason in invalid:
            Reminder.objects.filter(notion_id=page_id).update(active=False)
            event("registro inválido", f"{page_id}: {reason}")
        for page_id, (values, ack) in normalized:
            obj, created = Reminder.objects.get_or_create(notion_id=page_id, defaults={**values, "next_send": values["due"], "occurrence_due": values["due"]})
            rescheduled = obj.due != values["due"]
            for key, value in values.items(): setattr(obj, key, value)
            if rescheduled:
                obj.cycle += 1
                obj.attempts, obj.acknowledged = 0, False
                obj.next_send = obj.due
                obj.occurrence_due = obj.due
            # Confirmações externas só encerram a ocorrência vigente.
            cycle_due = obj.occurrence_due
            if ack and aware_date(ack) >= cycle_due and not obj.acknowledged:
                finish(obj, now)
            obj.last_seen = now
            obj.save()
        Runtime.objects.update_or_create(key="sync", defaults={"value": now.isoformat()})

def finish(obj, now):
    obj.acknowledged = True
    if obj.recurrence_days:
        step = timedelta(days=obj.recurrence_days)
        # Pula ocorrências antigas sem enviar uma enxurrada após indisponibilidade.
        due = obj.due + step * max(1, math.floor((now - obj.due) / step) + 1)
        obj.cycle += 1
        obj.occurrence_due = due
        obj.next_send, obj.attempts, obj.acknowledged = due, 0, False
    else: obj.next_send = None

def quiet(now):
    local = now.astimezone(ZoneInfo(os.getenv("NOTIFICATION_TZ", "America/Sao_Paulo")))
    start = time.fromisoformat(os.getenv("QUIET_START", "22:00"))
    end = time.fromisoformat(os.getenv("QUIET_END", "07:00"))
    t = local.time().replace(tzinfo=None)
    return start != end and (start <= t < end if start < end else t >= start or t < end)

def source_allows(notion, obj):
    page = notion.request("GET", "pages/" + obj.notion_id)
    if page.get("archived") or page.get("in_trash"): return False
    values, ack = normalize(page)
    if ack and aware_date(ack) >= obj.occurrence_due: return False
    if not values["active"] or any(getattr(obj, key) != value for key, value in values.items()): return False
    relation = page["properties"]["Tarefa"]
    if relation.get("has_more"): raise ValueError("Relação Tarefa excede limite; configure apenas uma tarefa")
    tasks = relation["relation"]
    if len(tasks) > 1: raise ValueError("Cada notificação pode referenciar apenas uma tarefa")
    for task in tasks:
        linked = notion.request("GET", "pages/" + task["id"])
        prop = linked.get("properties", {}).get("Status", {})
        status = prop.get(prop.get("type"), {}) or {}
        if linked.get("archived") or linked.get("in_trash") or status.get("name") in {"Concluída", "Cancelada", "Adiada"}: return False
        if status.get("name") not in {"Entrada", "Planejada", "Em andamento"}: raise ValueError("Status da tarefa desconhecido")
    return True

def send_due(notion, telegram):
    now = timezone.now()
    synced = Runtime.objects.filter(key="sync").first()
    if not synced or now - datetime.fromisoformat(synced.value) > timedelta(seconds=180) or quiet(now): return
    for obj in Reminder.objects.filter(active=True, paused=False, next_send__lte=now).order_by("next_send")[:10]:
        try:
            if not source_allows(notion, obj): continue
        except (APIError, ValueError, KeyError) as exc:
            event("fonte indisponível", f"{obj.pk}: {type(exc).__name__}")
            continue
        if obj.attempts >= obj.max_attempts:
            if obj.recurrence_days:
                finish(obj, now)
            else:
                obj.next_send = None
            obj.save(update_fields=["acknowledged", "cycle", "occurrence_due", "next_send", "attempts"])
            continue
        if Delivery.objects.filter(reminder=obj, cycle=obj.cycle, state__in=["unknown", "sending"]).exists(): continue
        delivery, created = Delivery.objects.get_or_create(reminder=obj, cycle=obj.cycle, attempt=obj.attempts + 1)
        if not created and delivery.state != "retry": continue
        delivery.state = "sending"
        delivery.save(update_fields=["state"])
        text = f"🔔 {obj.kind}: {obj.title}\n{obj.message}"
        if obj.target is not None: text += f"\nProgresso registrado: {obj.progress or 0} / {obj.target}"
        text = text[:3500] + f"\n{obj.link}"
        token = f"{obj.pk.hex}:{obj.cycle}"
        buttons = [[{"text": "✅ Confirmar aviso", "callback_data": "ack:" + token}, {"text": "⏰ +30 min", "callback_data": "snooze:" + token}], [{"text": "⏸ Pausar", "callback_data": "pause:" + token}]]
        try:
            result = telegram.call("sendMessage", chat_id=os.environ["TELEGRAM_CHAT_ID"], text=text[:4096], reply_markup={"inline_keyboard":buttons}, link_preview_options={"is_disabled":True})
        except APIError as exc:
            # HTTP 429 declara que o envio foi rejeitado; transporte/5xx é ambíguo.
            delivery.state = "retry" if exc.status == 429 else "unknown"
            delivery.save(update_fields=["state"])
            obj.next_send = now + timedelta(seconds=max(60, exc.retry))
            obj.save(update_fields=["next_send"])
            event("envio", f"{obj.pk}: {delivery.state}; HTTP {exc.status}")
            continue
        with transaction.atomic():
            delivery.state, delivery.message_id = "sent", result["message_id"]
            delivery.save()
            obj.attempts += 1
            obj.next_send = now + timedelta(minutes=obj.repeat_minutes)
            obj.save(update_fields=["attempts", "next_send"])

def handle_update(update, telegram):
    query = update.get("callback_query")
    if not query: return
    authorized = str(query.get("from", {}).get("id")) == os.environ["TELEGRAM_USER_ID"] and str(query.get("message", {}).get("chat", {}).get("id")) == os.environ["TELEGRAM_CHAT_ID"]
    reply = "Acesso negado"
    if authorized:
        try:
            action, uuid, cycle = query["data"].split(":")
            with transaction.atomic():
                obj = Reminder.objects.get(pk=uuid)
                valid_delivery = Delivery.objects.filter(reminder=obj, cycle=int(cycle), message_id=query["message"]["message_id"], state="sent").exists()
                if not valid_delivery or obj.cycle != int(cycle) or obj.acknowledged or not obj.active:
                    reply = "Aviso antigo ou já confirmado"
                elif action == "ack":
                    now = timezone.now().replace(microsecond=0)
                    Writeback.objects.get_or_create(reminder=obj, cycle=obj.cycle, defaults={"acknowledged_at":now, "next_try":now})
                    finish(obj, now)
                    obj.save(update_fields=["acknowledged", "cycle", "occurrence_due", "next_send", "attempts"])
                    reply = "Aviso confirmado. Tarefa/meta não foi concluída."
                elif action == "snooze":
                    # A repetição de um update não prolonga novamente: offset salvo na mesma transação.
                    obj.next_send = timezone.now() + timedelta(minutes=30)
                    obj.save(update_fields=["next_send"])
                    reply = "Adiado por 30 minutos"
                elif action == "pause":
                    obj.paused = True
                    obj.save(update_fields=["paused"])
                    reply = "Pausado. Retome no painel."
        except (ValueError, KeyError, Reminder.DoesNotExist): reply = "Botão inválido"
    # Falha da resposta visual não desfaz a confirmação persistida.
    try: telegram.call("answerCallbackQuery", callback_query_id=query["id"], text=reply)
    except APIError: pass

def poll(telegram):
    state, _ = Runtime.objects.get_or_create(key="telegram_offset", defaults={"value":"0"})
    updates = telegram.call("getUpdates", offset=int(state.value), timeout=0, allowed_updates=["callback_query", "message"])
    for update in updates:
        if update["update_id"] < int(state.value): continue
        with transaction.atomic():
            from conversation.gateway import receive
            handled = receive(update)
            if not handled: handle_update(update, telegram)
            elif update.get('callback_query'):
                try: telegram.call('answerCallbackQuery', callback_query_id=update['callback_query']['id'], text='Solicitação recebida.')
                except APIError: pass
            state.value = str(update["update_id"] + 1)
            state.save()

def writebacks(notion):
    for item in Writeback.objects.filter(done=False, next_try__lte=timezone.now()).order_by("acknowledged_at")[:10]:
        # Não sobrescrever confirmação mais nova após repetição/reinício.
        try:
            page = notion.request("GET", "pages/" + item.reminder.notion_id)
            value = get_value(page["properties"], "Última confirmação")
            if not value or aware_date(value) < item.acknowledged_at:
                notion.acknowledge(item.reminder.notion_id, item.acknowledged_at)
            item.done = True
        except (APIError, ValueError, KeyError):
            item.retries += 1
            item.next_try = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** min(item.retries, 7)))
        item.save()
