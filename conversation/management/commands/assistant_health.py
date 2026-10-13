from datetime import datetime,timedelta
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from notifications.models import Runtime
class Command(BaseCommand):
    def handle(self,*args,**options):
        row=Runtime.objects.filter(key='assistant_heartbeat').first()
        if not row or timezone.now()-datetime.fromisoformat(row.value)>timedelta(minutes=30):raise CommandError('Conversa sem heartbeat recente')
