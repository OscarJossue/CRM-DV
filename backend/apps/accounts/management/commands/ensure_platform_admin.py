from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or repair a platform super administrator account."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--first-name", default="Platform")
        parser.add_argument("--last-name", default="Administrator")

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        password = options["password"]

        if not email:
            raise CommandError("Email is required.")

        if not password:
            raise CommandError("Password is required.")

        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        created = False

        if user is None:
            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=options["first_name"],
                last_name=options["last_name"],
            )
            created = True
        else:
            user.email = email
            user.first_name = user.first_name or options["first_name"]
            user.last_name = user.last_name or options["last_name"]
            user.is_active = True
            user.status = "active"
            user.is_staff = True
            user.is_superuser = True
            user.id_company = None
            user.id_role = None
            user.set_password(password)
            user.save(
                update_fields=[
                    "email",
                    "first_name",
                    "last_name",
                    "is_active",
                    "status",
                    "is_staff",
                    "is_superuser",
                    "id_company",
                    "id_role",
                    "password",
                ]
            )

        # A platform administrator is never a tenant employee.
        try:
            from apps.employees.models import Employee

            Employee.objects.filter(id_user=user).delete()
        except Exception:
            pass

        action = "created" if created else "repaired"
        self.stdout.write(
            self.style.SUCCESS(
                f"Platform administrator {action}: {user.email} "
                f"(superuser={user.is_superuser}, staff={user.is_staff}, active={user.is_active}, status={user.status})"
            )
        )
