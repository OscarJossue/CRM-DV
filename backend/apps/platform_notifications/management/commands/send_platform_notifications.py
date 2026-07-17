from django.core.management.base import BaseCommand

from apps.platform_notifications.services import send_due_subscription_notifications


class Command(BaseCommand):
    help = "Send CEO MARKETING SaaS subscription renewal and expiration notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-before",
            type=int,
            default=5,
            help="Days before renewal date to send reminders.",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Send even if a notification was already sent today.",
        )

    def handle(self, *args, **options):
        result = send_due_subscription_notifications(
            days_before=options["days_before"],
            force=options["force"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Notifications processed. "
                f"Emails sent: {result.get('sent', 0)}. "
                f"Emails skipped: {result.get('skipped', 0)}. "
                f"Emails failed: {result.get('failed', 0)}. "
                f"Bell notifications created: {result.get('bell_created', 0)}. "
                f"Bell notifications skipped: {result.get('bell_skipped', 0)}."
            )
        )