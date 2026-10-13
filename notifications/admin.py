from django.contrib import admin
from django.utils import timezone
from .models import Reminder, Delivery, Writeback, Runtime, Event
from .api import Notion
from .engine import normalize, event

@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "active", "paused", "next_send", "attempts", "acknowledged"]
    list_filter = ["kind", "active", "paused", "acknowledged"]
    search_fields = ["title", "notion_id"]
    readonly_fields = ["id", "notion_id", "occurrence_due", "next_send", "attempts", "cycle", "acknowledged", "last_seen"]
    def save_model(self, request, obj, form, change):
        # Edição de configuração é publicada no Notion; campos de tarefa não são alterados.
        fields = {"title", "message", "kind", "link", "active", "due", "repeat_minutes", "max_attempts", "recurrence_days", "target", "progress"}
        if fields.intersection(form.changed_data):
            notion = Notion()
            page = notion.request("GET", "pages/" + obj.notion_id)
            normalize(page)  # validar estrutura e registro antes de alterar
            rich = lambda value: [{"text": {"content": value[i:i+1900]}} for i in range(0,len(value),1900)]
            props = {"Nome": {"title":rich(obj.title)}, "Mensagem": {"rich_text":rich(obj.message)}, "Tipo": {"select":{"name":obj.kind}}, "Link": {"url":obj.link or None}, "Ativo":{"checkbox":obj.active}, "Enviar em":{"date":{"start":obj.due.isoformat()}}, "Insistente":{"checkbox":obj.max_attempts > 1}, "Intervalo (min)":{"number":obj.repeat_minutes}, "Máximo de avisos":{"number":obj.max_attempts}, "Recorrência (dias)":{"number":obj.recurrence_days}, "Alvo":{"number":obj.target}, "Progresso":{"number":obj.progress}}
            mapping = dict(zip(["title","message","kind","link","active","due","repeat_minutes","max_attempts","recurrence_days","target","progress"], ["Nome","Mensagem","Tipo","Link","Ativo","Enviar em","Intervalo (min)","Máximo de avisos","Recorrência (dias)","Alvo","Progresso"]))
            changed_props = {mapping[key] for key in fields.intersection(form.changed_data)}
            if "max_attempts" in form.changed_data: changed_props.add("Insistente")
            notion.request("PATCH", "pages/" + obj.notion_id, {"properties":{key:value for key,value in props.items() if key in changed_props}})
            verified, _ = normalize(notion.request("GET", "pages/" + obj.notion_id))
            if "link" in form.changed_data and not obj.link: obj.link = verified["link"]
            for key in fields.intersection(form.changed_data):
                if verified[key] != getattr(obj, key): raise ValueError("Não foi possível verificar edição no Notion")
            if "due" in form.changed_data:
                obj.cycle += 1
                obj.next_send = obj.occurrence_due = obj.due
                obj.attempts, obj.acknowledged = 0, False
            event("configuração", f"Configuração publicada: {obj.pk}")
        changed = set(form.changed_data)
        if "due" in changed: changed.update(["cycle", "next_send", "occurrence_due", "attempts", "acknowledged"])
        if changed: obj.save(update_fields=list(changed))
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.action(description="Reenviar entregas incertas (pode duplicar mensagem)")
def retry_unknown(modeladmin, request, queryset):
    for delivery in queryset.filter(state="unknown"):
        delivery.state = "retry"
        delivery.save(update_fields=["state"])
        Reminder.objects.filter(pk=delivery.reminder_id).update(next_send=timezone.now())

class AuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False

@admin.register(Delivery)
class DeliveryAdmin(AuditAdmin):
    list_display = ["reminder", "cycle", "attempt", "state", "created"]
    list_filter = ["state"]
    actions = [retry_unknown]
    def has_change_permission(self, request, obj=None): return request.user.is_superuser
    readonly_fields = [f.name for f in Delivery._meta.fields]

@admin.register(Writeback)
class WritebackAdmin(AuditAdmin):
    list_display = ["reminder", "done", "retries", "next_try"]

@admin.register(Event)
class EventAdmin(AuditAdmin):
    list_display = ["created", "category", "detail"]
admin.site.register(Runtime, AuditAdmin)
admin.site.site_header = "Secretária — Notificações"
admin.site.site_title = "Administração da Secretária"
admin.site.index_title = "Painel de administração"
