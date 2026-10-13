import sqlite3
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
class Command(BaseCommand):
    help = "Backup consistente via SQLite Online Backup API"
    def add_arguments(self, parser): parser.add_argument("destination")
    def handle(self, *args, **options):
        destination = options["destination"]
        if destination == str(settings.DATABASES["default"]["NAME"]): raise CommandError("Destino deve ser diferente da base ativa")
        with sqlite3.connect(settings.DATABASES["default"]["NAME"]) as source, sqlite3.connect(destination) as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok": raise CommandError("Backup inválido")
        self.stdout.write("Backup verificado")
