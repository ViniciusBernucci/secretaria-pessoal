import fcntl, os, signal, time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone
from notifications.api import Notion, Telegram
from notifications.engine import sync, poll, send_due, writebacks, event
from notifications.models import Delivery, Runtime

class Command(BaseCommand):
    help = "Worker único com estado durável no SQLite"
    def handle(self, *args, **options):
        for key in ["NOTION_TOKEN", "NOTION_DATA_SOURCE_ID", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_USER_ID"]:
            if not os.getenv(key): raise CommandError(f"Configure {key}")
        path = Path(connection.settings_dict["NAME"]).parent / "worker.lock"
        lock = path.open("a")
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise CommandError("Outro worker já está executando")
        with connection.cursor() as cursor: cursor.execute("PRAGMA journal_mode=WAL")
        Delivery.objects.filter(state="sending").update(state="unknown")
        from conversation.models import Outgoing
        from conversation.gateway import flush
        Outgoing.objects.filter(state="sending").update(state="unknown")
        running = True
        def stop(*_):
            nonlocal running
            running = False
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        notion, telegram = Notion(), Telegram()
        last_sync = 0
        while running:
            try: poll(telegram)
            except Exception as exc: event("poll falhou", type(exc).__name__)
            try: flush(telegram)
            except Exception as exc: event("resposta falhou", type(exc).__name__)
            try: writebacks(notion)
            except Exception as exc: event("confirmação falhou", type(exc).__name__)
            if time.monotonic() - last_sync >= 60:
                try: sync(notion)
                except Exception as exc:
                    # Bloqueia envio de snapshot antigo imediatamente.
                    Runtime.objects.filter(key="sync").delete()
                    event("sync falhou", str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
                last_sync = time.monotonic()
            try: send_due(notion, telegram)
            except Exception as exc: event("worker falhou", type(exc).__name__)
            Runtime.objects.update_or_create(key="heartbeat", defaults={"value":timezone.now().isoformat()})
            for _ in range(5):
                if running: time.sleep(1)
        lock.close()
