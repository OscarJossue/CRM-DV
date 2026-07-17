from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.audit.models import SystemLog
from apps.companies.models import Company


class SystemLogModelTest(TestCase):
    def test_history_record_is_immutable(self):
        company = Company.objects.create(name="Audit Company")
        record = SystemLog.objects.create(
            id_company=company,
            module="clients",
            action_type="created",
            object_type="Client",
            object_label="Example Client",
        )
        record.object_label = "Changed"
        with self.assertRaises(ValidationError):
            record.save()
