from datetime import timedelta

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.audit.models import SystemLog
from apps.audit.models.choices import ACTION_LOGIN, SEVERITY_CRITICAL, SEVERITY_SECURITY
from apps.audit.services import log_system_action, purge_expired_system_logs
from apps.companies.models import Company


@override_settings(AUDIT_LOG_RETENTION_DAYS=3, AUDIT_CRITICAL_RETENTION_DAYS=7)
class SystemLogServiceTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="History Company")
        self.user = UserAccount.objects.create_user(
            email="owner@example.com",
            password="StrongPassword123!",
            first_name="Owner",
            id_company=self.company,
            is_company_owner=True,
        )

    def test_security_event_keeps_actor_snapshot_and_seven_day_retention(self):
        request = RequestFactory().post("/login/", HTTP_USER_AGENT="Test Browser")
        request.user = self.user
        request.current_company = self.company
        before = timezone.now()

        record = log_system_action(
            user=self.user,
            company=self.company,
            module="authentication",
            action="accounts.useraccount:login",
            action_type=ACTION_LOGIN,
            request=request,
            object_type="User account",
            object_id=self.user.pk,
            object_label=self.user.email,
            severity=SEVERITY_SECURITY,
        )

        self.assertEqual(record.actor_email, self.user.email)
        self.assertEqual(record.actor_name, "Owner")
        self.assertGreaterEqual(record.expires_at, before + timedelta(days=7))
        self.assertLess(record.expires_at, before + timedelta(days=7, minutes=1))

    def test_normal_event_uses_three_day_retention(self):
        before = timezone.now()
        record = log_system_action(
            user=self.user,
            company=self.company,
            module="clients",
            action="client updated",
            action_type="updated",
        )

        self.assertGreaterEqual(record.expires_at, before + timedelta(days=3))
        self.assertLess(record.expires_at, before + timedelta(days=3, minutes=1))

    def test_expired_history_is_deleted_in_batches(self):
        expired = SystemLog.objects.create(
            id_company=self.company,
            module="clients",
            action_type="updated",
            expires_at=timezone.now() - timedelta(days=1),
        )
        active = SystemLog.objects.create(
            id_company=self.company,
            module="clients",
            action_type="updated",
            expires_at=timezone.now() + timedelta(days=3),
        )

        deleted = purge_expired_system_logs(batch_size=100)

        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(SystemLog.objects.filter(pk=expired.pk).exists())
        self.assertTrue(SystemLog.objects.filter(pk=active.pk).exists())

    def test_short_policy_also_removes_records_created_with_old_long_expiry(self):
        old_normal = SystemLog.objects.create(
            id_company=self.company,
            module="clients",
            action_type="updated",
            expires_at=timezone.now() + timedelta(days=365),
        )
        recent_critical = SystemLog.objects.create(
            id_company=self.company,
            module="permissions",
            action_type="permissions_updated",
            severity=SEVERITY_CRITICAL,
            expires_at=timezone.now() + timedelta(days=730),
        )
        old_critical = SystemLog.objects.create(
            id_company=self.company,
            module="permissions",
            action_type="permissions_updated",
            severity=SEVERITY_CRITICAL,
            expires_at=timezone.now() + timedelta(days=730),
        )

        SystemLog.objects.filter(pk=old_normal.pk).update(created_at=timezone.now() - timedelta(days=4))
        SystemLog.objects.filter(pk=recent_critical.pk).update(created_at=timezone.now() - timedelta(days=6))
        SystemLog.objects.filter(pk=old_critical.pk).update(created_at=timezone.now() - timedelta(days=8))

        purge_expired_system_logs(batch_size=100)

        self.assertFalse(SystemLog.objects.filter(pk=old_normal.pk).exists())
        self.assertTrue(SystemLog.objects.filter(pk=recent_critical.pk).exists())
        self.assertFalse(SystemLog.objects.filter(pk=old_critical.pk).exists())
