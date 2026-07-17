from django.db import transaction
from rest_framework import serializers

from apps.accounts.models.choices import STATUS_ACTIVE
from apps.core.tenant import user_is_global_admin

from .models import Employee
from .services import employee_validate_company_user, sync_employee_profile


class EmployeeSerializer(serializers.ModelSerializer):
    """Compatibility API for clients that still call ``/api/employees/``.

    The user account is the canonical record. Creating through this endpoint is
    treated as an upsert of the user's employment profile, while updates keep
    login status synchronized.
    """

    id = serializers.IntegerField(source="id_employee", read_only=True)
    user_name = serializers.CharField(source="id_user.get_full_name", read_only=True)
    user_email = serializers.CharField(source="id_user.email", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    role_name = serializers.CharField(source="id_user.id_role.name", read_only=True)
    hire_date = serializers.DateField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "id_employee", "id_user", "user_name", "user_email",
            "company_name", "role_name", "id_company", "identification",
            "position", "hire_date", "status",
        ]
        read_only_fields = ["id_employee"]

    def validate(self, attrs):
        request = self.context.get("request")
        request_user = getattr(request, "user", None)
        user_account = attrs.get("id_user") or getattr(self.instance, "id_user", None)
        company = attrs.get("id_company") or getattr(self.instance, "id_company", None)

        if request_user and request_user.is_authenticated and not user_is_global_admin(request_user):
            company = request_user.id_company
            attrs["id_company"] = company

        employee_validate_company_user(company, user_account)

        if self.instance and "id_user" in attrs and attrs["id_user"].pk != self.instance.id_user_id:
            raise serializers.ValidationError({"id_user": "The linked user cannot be changed."})

        return attrs

    @staticmethod
    def _sync_user_status(user_account, status):
        if status is None:
            return
        user_account.status = status
        user_account.is_active = status == STATUS_ACTIVE
        user_account.save(update_fields=["status", "is_active"])

    @transaction.atomic
    def create(self, validated_data):
        user_account = validated_data["id_user"]
        status = validated_data.get("status", user_account.status)
        self._sync_user_status(user_account, status)
        profile_data = {}
        if "identification" in validated_data:
            profile_data["identification"] = validated_data["identification"]
        if "position" in validated_data:
            profile_data["position"] = validated_data["position"]
        return sync_employee_profile(user_account, **profile_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        status = validated_data.get("status")
        self._sync_user_status(instance.id_user, status)

        profile_data = {}
        if "identification" in validated_data:
            profile_data["identification"] = validated_data["identification"]
        if "position" in validated_data:
            profile_data["position"] = validated_data["position"]

        return sync_employee_profile(instance.id_user, **profile_data)
