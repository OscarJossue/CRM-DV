from django.core.management.base import BaseCommand

from apps.audit.services import purge_expired_system_logs


class Command(BaseCommand):
    help = "Delete audit logs whose configured retention period has expired."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args, **options):
        deleted = purge_expired_system_logs(batch_size=options["batch_size"])
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired audit log(s)."))
