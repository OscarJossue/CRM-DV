from django.core.management.base import BaseCommand
from django.db import transaction

from apps.smtp_settings.models import SmtpSetting
from apps.smtp_settings.security import (
    encrypt_smtp_password,
    is_encrypted_smtp_password,
)


class Command(BaseCommand):
    help = "Encrypt legacy plaintext company SMTP passwords without printing them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows require encryption without modifying them.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        queryset = SmtpSetting.objects.exclude(smtp_password="")
        pending_ids = [
            row.id_smtp_setting
            for row in queryset.only("id_smtp_setting", "smtp_password").iterator()
            if not is_encrypted_smtp_password(row.smtp_password)
        ]

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"SMTP credential rows pending encryption: {len(pending_ids)}"
                )
            )
            return

        updated = 0
        with transaction.atomic():
            for row in SmtpSetting.objects.filter(id_smtp_setting__in=pending_ids).iterator():
                row.smtp_password = encrypt_smtp_password(row.smtp_password)
                row.save(update_fields=["smtp_password", "updated_at"])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Encrypted SMTP credential rows: {updated}")
        )
