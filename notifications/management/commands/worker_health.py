from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from notifications.models import Runtime
class Command(BaseCommand):
    def handle(self, *args, **options):
        for key in ["heartbeat", "sync"]:
            row = Runtime.objects.filter(key=key).first()
            if not row or timezone.now() - datetime.fromisoformat(row.value) > timedelta(minutes=5):
                raise CommandError(f"Worker sem {key} recente")
