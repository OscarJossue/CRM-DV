from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import UserAccount
from apps.accounts.models.choices import STATUS_ACTIVE
from apps.core.access_policy import get_user_runtime_access_code

from apps.companies.models import Company
from apps.companies.services import (
    create_owner_role_for_company,
    enable_default_company_modules,
)


class Command(BaseCommand):
    help = "Audit company administrators and optionally repair one or all company workspaces."

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int)
        parser.add_argument("--fix", action="store_true")
        parser.add_argument("--admin-email")
        parser.add_argument("--admin-first-name", default="Company")
        parser.add_argument("--admin-last-name", default="Administrator")
        parser.add_argument("--password")
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Explicitly mark the selected company active while repairing it.",
        )

    def handle(self, *args, **options):
        companies = Company.objects.all().order_by("id_company")
        company_id = options.get("company_id")
        if company_id:
            companies = companies.filter(id_company=company_id)
        if not companies.exists():
            raise CommandError("No matching company was found.")

        if options.get("admin_email") and not company_id:
            raise CommandError("--admin-email requires --company-id.")
        if bool(options.get("admin_email")) != bool(options.get("password")):
            raise CommandError("Use --admin-email and --password together when creating or resetting an administrator.")

        for company in companies:
            self._process_company(company, options)

    @transaction.atomic
    def _process_company(self, company, options):
        owners = list(
            UserAccount.objects.select_related("id_role")
            .filter(id_company=company, is_company_owner=True)
            .order_by("id_user")
        )
        owner = owners[0] if owners else None
        requested_email = (options.get("admin_email") or "").strip().lower()
        password = options.get("password")

        if requested_email:
            matching = UserAccount.objects.filter(email__iexact=requested_email).first()
            if matching and matching.id_company_id != company.id_company:
                raise CommandError(f"{requested_email} already belongs to another company.")
            owner = matching or owner

        if options.get("fix"):
            role = create_owner_role_for_company(company)
            enable_default_company_modules(company)

            if options.get("activate") and company.status != "active":
                company.status = "active"
                company.save(update_fields=["status"])

            # One workspace has exactly one primary company administrator.
            # Additional staff remain normal company users. When --admin-email
            # selects an existing staff account, demote every previous owner.
            for existing_owner in owners:
                if owner and existing_owner.pk == owner.pk:
                    continue
                existing_owner.is_company_owner = False
                existing_owner.save(update_fields=["is_company_owner"])

            if owner:
                owner.id_company = company
                owner.id_role = role
                owner.is_company_owner = True
                owner.is_staff = False
                owner.is_superuser = False
                owner.is_active = True
                owner.status = STATUS_ACTIVE
                if requested_email:
                    owner.email = requested_email
                if password:
                    validate_password(password, user=owner)
                    owner.set_password(password)
                owner.save()
            elif requested_email and password:
                candidate = UserAccount(
                    email=requested_email,
                    first_name=options.get("admin_first_name") or "Company",
                    last_name=options.get("admin_last_name") or "Administrator",
                )
                validate_password(password, user=candidate)
                owner = UserAccount.objects.create_user(
                    email=requested_email,
                    password=password,
                    first_name=candidate.first_name,
                    last_name=candidate.last_name,
                    id_company=company,
                    id_role=role,
                    status=STATUS_ACTIVE,
                    is_active=True,
                    is_company_owner=True,
                    is_staff=False,
                    is_superuser=False,
                )

        status = get_user_runtime_access_code(owner) if owner else "missing_administrator"
        owner_label = owner.email if owner else "MISSING"
        duplicate_count = max(len(owners) - 1, 0)
        self.stdout.write(
            f"company={company.id_company} name={company.name!r} status={company.status} "
            f"administrator={owner_label} access={status} duplicate_admins={duplicate_count}"
        )
