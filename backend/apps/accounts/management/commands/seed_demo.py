import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.accounts.models import Role, RolePermission, UserAccount
from apps.accounts.models.choices import TENANT_MODULE_CODES
from apps.clients.models import Client
from apps.companies.models import Company
from apps.employees.services import employee_update, sync_employee_profile
from apps.estimates.models import Estimate
from apps.invoices.models import Invoice
from apps.leads.models import Lead
from apps.projects.models import Project

MODULES = list(TENANT_MODULE_CODES)


class Command(BaseCommand):
    help = "Create demo company, users, roles and starter CRM data."

    def handle(self, *args, **options):
        allow_production_seed = os.getenv("ALLOW_DEMO_SEED", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if not settings.DEBUG and not allow_production_seed:
            raise CommandError(
                "seed_demo is disabled outside DEBUG mode because it creates public demo credentials."
            )

        demo_passwords = {
            "admin": os.getenv("DEMO_PLATFORM_ADMIN_PASSWORD", "").strip(),
            "owner": os.getenv("DEMO_COMPANY_OWNER_PASSWORD", "").strip(),
            "secretary": os.getenv("DEMO_SECRETARY_PASSWORD", "").strip(),
            "inspector": os.getenv("DEMO_INSPECTOR_PASSWORD", "").strip(),
        }
        missing_passwords = [name for name, value in demo_passwords.items() if not value]
        if missing_passwords:
            raise CommandError(
                "Demo passwords are not hardcoded. Set DEMO_PLATFORM_ADMIN_PASSWORD, "
                "DEMO_COMPANY_OWNER_PASSWORD, DEMO_SECRETARY_PASSWORD and "
                "DEMO_INSPECTOR_PASSWORD before running seed_demo."
            )

        self.stdout.write(
            self.style.WARNING(
                "Creating development-only demo records. Never enable AUTO_SEED in production."
            )
        )

        company, _ = Company.objects.get_or_create(
            name="Demo Roofing Company",
            defaults={"description": "Demo company for CRM SaaS", "plan": "Pro", "user_limit": 20},
        )

        owner_role, _ = Role.objects.get_or_create(id_company=company, name="Owner", defaults={"description": "Full company access"})
        secretary_role, _ = Role.objects.get_or_create(id_company=company, name="Secretary", defaults={"description": "Administrative access"})
        inspector_role, _ = Role.objects.get_or_create(id_company=company, name="Inspector", defaults={"description": "Project inspection access"})

        for role in [owner_role, secretary_role, inspector_role]:
            for module in MODULES:
                defaults = dict(can_view=True, can_create=True, can_edit=True, can_delete=role == owner_role, can_approve=role == owner_role)
                if role == inspector_role and module not in ["projects", "inspections", "evidence", "calendar_events", "notifications", "dashboard"]:
                    defaults = dict(can_view=True, can_create=False, can_edit=False, can_delete=False, can_approve=False)
                RolePermission.objects.get_or_create(id_role=role, module=module, defaults=defaults)

        admin = UserAccount.objects.filter(email="admin@demo.com").first()
        if not admin:
            admin = UserAccount.objects.create_superuser(
                email="admin@demo.com",
                password=demo_passwords["admin"],
                first_name="Super",
                last_name="Admin",
            )

        owner = self._user(
            "owner@demo.com",
            demo_passwords["owner"],
            company,
            owner_role,
            "Company",
            "Owner",
            is_company_owner=True,
        )
        secretary = self._user(
            "secretary@demo.com",
            demo_passwords["secretary"],
            company,
            secretary_role,
            "Demo",
            "Secretary",
        )
        inspector = self._user(
            "inspector@demo.com",
            demo_passwords["inspector"],
            company,
            inspector_role,
            "Demo",
            "Inspector",
        )

        employee = sync_employee_profile(
            inspector,
            identification="DEMO-INS-001",
            position="Inspector",
        )
        employee_update(
            employee,
            schedule="Mon-Fri 8am-5pm",
            hourly_rate=25,
            status="active",
        )

        client, _ = Client.objects.get_or_create(
            id_company=company,
            email="client@example.com",
            defaults={
                "name": "John Demo Client",
                "phone": "555-100-2000",
                "address": "100 Demo Street",
                "city": "Demo City",
                "state": "CT",
                "notes": "Starter client created by seed_demo",
            },
        )

        Lead.objects.get_or_create(
            id_company=company,
            email="lead@example.com",
            defaults={
                "id_assigned_user": secretary,
                "name": "Mary Demo Lead",
                "phone": "555-300-4000",
                "source": "Website",
                "status": "new",
                "notes": "Demo lead",
            },
        )

        project, _ = Project.objects.get_or_create(
            id_company=company,
            id_client=client,
            name="Demo Roof Replacement",
            defaults={
                "id_inspector": inspector,
                "description": "Initial demo project",
                "status": "pending",
                "progress": 10,
            },
        )

        Estimate.objects.get_or_create(
            id_company=company,
            id_client=client,
            id_project=project,
            defaults={
                "description": "Demo estimate",
                "detail_items": [{"quantity": 1, "description": "Roof replacement", "unit_price": 5000, "total": 5000}],
                "subtotal": 5000,
                "tax": 0,
                "total": 5000,
                "validity_days": 15,
                "status": "pending",
            },
        )

        Invoice.objects.get_or_create(
            id_company=company,
            id_client=client,
            id_project=project,
            defaults={
                "detail_items": [{"quantity": 1, "description": "Deposit", "unit_price": 1500, "total": 1500}],
                "subtotal": 1500,
                "tax": 0,
                "total": 1500,
                "balance": 1500,
                "status": "pending",
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready."))

    def _user(self, email, password, company, role, first_name, last_name, **flags):
        user = UserAccount.objects.filter(email=email).first()
        if user:
            return user
        return UserAccount.objects.create_user(
            email=email,
            password=password,
            id_company=company,
            id_role=role,
            first_name=first_name,
            last_name=last_name,
            is_staff=flags.get("is_staff", False),
            is_superuser=flags.get("is_superuser", False),
            is_company_owner=flags.get("is_company_owner", False),
        )
