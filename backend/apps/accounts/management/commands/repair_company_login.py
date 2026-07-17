from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, RolePermission, UserAccount
from apps.accounts.models.choices import MODULE_CHOICES, STATUS_ACTIVE
from apps.companies.models.choices import STATUS_ACTIVE as COMPANY_ACTIVE
from apps.company_modules.models import CompanyModule
from apps.core.access_policy import get_user_runtime_access_code
from apps.core.redirects import get_user_dashboard_url
from apps.platform_subscriptions.models import PlatformSubscription
from apps.platform_subscriptions.services import reactivate_platform_subscription


COMPANY_MODULES = tuple(
    module
    for module, _label in MODULE_CHOICES
    if not module.startswith("platform_")
)


class Command(BaseCommand):
    help = (
        "Repair the runtime login state for a company user without turning the "
        "account into a platform superuser."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", default=None)
        parser.add_argument(
            "--grant-all",
            action="store_true",
            help="Grant all tenant CRM permissions to the user's company role.",
        )
        parser.add_argument(
            "--set-owner",
            action="store_true",
            help="Mark the user as the company owner and grant all tenant permissions.",
        )
        parser.add_argument(
            "--renew-subscription",
            action="store_true",
            help="Reactivate the latest subscription and start a new billing cycle.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()

        user = (
            UserAccount.objects.select_related("id_company", "id_role")
            .filter(email__iexact=email)
            .first()
        )

        if not user:
            raise CommandError(f"No user exists with email {email}.")

        if user.is_superuser or user.is_staff:
            raise CommandError(
                "This command is only for company users. Use ensure_platform_admin "
                "for platform administrators."
            )

        company = user.id_company

        if not company:
            raise CommandError("The user is not assigned to a company.")

        before = {
            "user_is_active": user.is_active,
            "user_status": user.status,
            "company_status": company.status,
            "role": user.id_role.name if user.id_role else None,
            "role_status": user.id_role.status if user.id_role else None,
            "is_company_owner": user.is_company_owner,
            "access_code": get_user_runtime_access_code(user),
        }

        user.is_active = True
        user.status = STATUS_ACTIVE

        if options.get("password"):
            user.set_password(options["password"])

        if options.get("set_owner"):
            user.is_company_owner = True

        company.status = COMPANY_ACTIVE
        company.save(update_fields=["status"])

        role = user.id_role

        if not role and (user.is_company_owner or options.get("grant_all")):
            role_name = "Owner" if user.is_company_owner else "Company Administrator"
            role, _created = Role.objects.get_or_create(
                id_company=company,
                name=role_name,
                defaults={
                    "description": "Full company CRM access.",
                    "status": STATUS_ACTIVE,
                },
            )
            user.id_role = role

        if role:
            role.status = STATUS_ACTIVE
            role.save(update_fields=["status"])

        grant_all = bool(
            options.get("grant_all")
            or options.get("set_owner")
            or user.is_company_owner
        )

        if grant_all:
            if not role:
                raise CommandError("A company role could not be assigned to the user.")

            for module in COMPANY_MODULES:
                RolePermission.objects.update_or_create(
                    id_role=role,
                    module=module,
                    defaults={
                        "can_view": True,
                        "can_create": True,
                        "can_edit": True,
                        "can_delete": True,
                        "can_approve": True,
                    },
                )

                CompanyModule.objects.update_or_create(
                    id_company=company,
                    module=module,
                    defaults={"is_enabled": True},
                )

        user.save()

        subscription = (
            PlatformSubscription.objects.select_related("id_plan")
            .filter(id_company=company)
            .order_by("-created_at")
            .first()
        )

        if options.get("renew_subscription"):
            if not subscription:
                raise CommandError(
                    "The company has no subscription to renew. Create one from the "
                    "platform subscriptions screen."
                )

            reactivate_platform_subscription(
                subscription,
                force_new_cycle=True,
            )
            subscription.refresh_from_db()
            company.refresh_from_db()
            user.refresh_from_db()

        access_code = get_user_runtime_access_code(user)
        dashboard_url = get_user_dashboard_url(user)

        self.stdout.write(self.style.SUCCESS("COMPANY LOGIN REPAIRED"))
        self.stdout.write(f"Email: {user.email}")
        self.stdout.write(f"Company: {company.name} ({company.slug})")
        self.stdout.write(f"User active/status: {user.is_active}/{user.status}")
        self.stdout.write(f"Company status: {company.status}")
        self.stdout.write(f"Company owner: {user.is_company_owner}")
        self.stdout.write(f"Role: {user.id_role.name if user.id_role else 'No role'}")
        self.stdout.write(f"Runtime access: {access_code}")
        self.stdout.write(f"Dashboard: {dashboard_url}")

        if subscription:
            self.stdout.write(
                "Subscription: "
                f"{subscription.status} | renewal={subscription.renewal_date or 'not set'}"
            )
        else:
            self.stdout.write("Subscription: no subscription record")

        self.stdout.write(f"Previous state: {before}")

        if access_code != "allowed":
            raise CommandError(
                f"The account is still blocked with runtime code: {access_code}."
            )
