from django.core.management.base import BaseCommand

from apps.companies.models import Company
from apps.company_modules.services import sync_company_modules


class Command(BaseCommand):
    help = "Sync available CRM modules for all companies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--disabled",
            action="store_true",
            help="Create missing company modules as disabled instead of enabled.",
        )

    def handle(self, *args, **options):
        default_enabled = not options["disabled"]

        companies = Company.objects.all().order_by("name")
        total_created = 0

        for company in companies:
            created_items = sync_company_modules(
                company,
                default_enabled=default_enabled,
            )

            total_created += len(created_items)

            self.stdout.write(
                self.style.SUCCESS(
                    f"{company.name}: {len(created_items)} module rules created."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Total module rules created: {total_created}"
            )
        )
