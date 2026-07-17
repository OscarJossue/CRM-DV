from django.test import TestCase

from apps.accounts.models import Role, UserAccount
from apps.companies.models import Company
from apps.employees.services import employee_create, employee_update


class EmployeeCompatibilityServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Service Tenant", status="active")
        self.role = Role.objects.create(id_company=self.company, name="Technician")
        self.user = UserAccount.objects.create_user(
            email="service-employee@example.com",
            password="Service-Strong-2026!",
            first_name="Service",
            last_name="Employee",
            id_company=self.company,
            id_role=self.role,
            status="active",
            is_active=True,
        )

    def test_legacy_create_is_an_upsert_not_a_duplicate(self):
        original_profile_id = self.user.employee_profile.pk
        profile = employee_create(
            id_company=self.company,
            id_user=self.user,
            identification="ID-100",
            position="Installer",
            schedule="Mon-Fri",
            hourly_rate=20,
            status="active",
        )

        self.assertEqual(profile.pk, original_profile_id)
        self.assertEqual(profile.identification, "ID-100")
        self.assertEqual(profile.position, "Installer")
        self.assertEqual(profile.schedule, "Mon-Fri")
        self.assertEqual(profile.hourly_rate, 20)

    def test_legacy_update_keeps_user_and_profile_status_synchronized(self):
        profile = employee_update(
            self.user.employee_profile,
            position="Supervisor",
            status="inactive",
        )
        self.user.refresh_from_db()
        profile.refresh_from_db()

        self.assertEqual(profile.position, "Supervisor")
        self.assertEqual(profile.status, "inactive")
        self.assertEqual(self.user.status, "inactive")
        self.assertFalse(self.user.is_active)
