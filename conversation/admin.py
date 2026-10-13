from django.contrib import admin
from .models import Incoming, ChatTurn, Outgoing, Operation, DailyBriefing, ModelUsage
class ReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request,obj=None): return False
    def has_change_permission(self, request,obj=None): return False
@admin.register(Incoming)
class IncomingAdmin(ReadOnly):
    list_display=['created','kind','state','update_id']
    list_filter=['state','kind']
@admin.register(Outgoing)
class OutgoingAdmin(ReadOnly):
    list_display=['created','key','state','message_id']
    list_filter=['state']
@admin.register(Operation)
class OperationAdmin(ReadOnly):
    list_display=['created','kind','state','id']
@admin.register(DailyBriefing)
class BriefingAdmin(ReadOnly):
    list_display=['day','state']
admin.site.register(ChatTurn,ReadOnly)
admin.site.register(ModelUsage,ReadOnly)
