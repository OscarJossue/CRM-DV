from django.core.management.base import BaseCommand

from apps.platform_subscriptions.services import sync_all_platform_subscriptions


class Command(BaseCommand):
    help = "Sync platform subscriptions and company access based on renewal dates."

    def handle(self, *args, **options):
        result = sync_all_platform_subscriptions()

        self.stdout.write(
            self.style.SUCCESS(
                f"Subscription sync completed. "
                f"Subscriptions checked: {result['subscriptions_checked']}. "
                f"Companies checked: {result['companies_checked']}."
            )
        )