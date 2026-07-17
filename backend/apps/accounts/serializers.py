from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Role, RolePermission, UserAccount
from .models.choices import STATUS_ACTIVE, STATUS_INACTIVE, TENANT_MODULE_CODES
from .forms import (
    company_active_user_limit_reached,
    get_company_user_limit_message,
)


def _request_user(serializer):
    request = serializer.context.get("request")
    return getattr(request, "user", None)


class RoleSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_role", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "id_role",
            "id_company",
            "company_name",
            "name",
            "description",
            "status",
        ]
        read_only_fields = ["id_role"]

    def validate_id_company(self, company):
        user = _request_user(self)
        if user and user.is_authenticated and not user.is_superuser:
            if user.id_company_id != company.id_company:
                raise serializers.ValidationError("You can only manage roles in your company.")
        return company

    def validate(self, attrs):
        user = _request_user(self)
        if self.instance and user and not user.is_superuser:
            attrs["id_company"] = user.id_company
        return attrs


class RolePermissionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_permission", read_only=True)
    role_name = serializers.CharField(source="id_role.name", read_only=True)
    company_name = serializers.CharField(source="id_role.id_company.name", read_only=True)

    class Meta:
        model = RolePermission
        fields = [
            "id",
            "id_permission",
            "id_role",
            "role_name",
            "company_name",
            "module",
            "can_view",
            "can_create",
            "can_edit",
            "can_delete",
            "can_approve",
        ]
        read_only_fields = ["id_permission"]

    def validate_id_role(self, role):
        user = _request_user(self)
        if user and user.is_authenticated and not user.is_superuser:
            if user.id_company_id != role.id_company_id:
                raise serializers.ValidationError("You can only manage permissions in your company.")
        return role

    def validate_module(self, module):
        if module not in TENANT_MODULE_CODES:
            raise serializers.ValidationError("This is not a company-workspace module.")
        return module


class UserAccountSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_user", read_only=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    role_name = serializers.CharField(source="id_role.name", read_only=True)
    identification = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    position = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    hire_date = serializers.DateField(read_only=True)

    class Meta:
        model = UserAccount
        fields = [
            "id", "id_user", "id_company", "company_name", "id_role", "role_name",
            "first_name", "last_name", "email", "phone", "identification", "position",
            "hire_date", "password", "password_confirm", "status", "is_active",
            "is_staff", "is_superuser", "is_company_owner", "last_login", "created_at",
        ]
        read_only_fields = [
            "id_user", "is_staff", "is_superuser", "is_company_owner", "last_login", "created_at",
        ]

    def validate_email(self, value):
        return value.strip().lower()

    def validate_id_company(self, company):
        user = _request_user(self)
        if user and user.is_authenticated and not user.is_superuser:
            if user.id_company_id != company.id_company:
                raise serializers.ValidationError("You can only manage users in your company.")
        return company

    def validate_id_role(self, role):
        user = _request_user(self)
        if user and user.is_authenticated and not user.is_superuser:
            if user.id_company_id != role.id_company_id:
                raise serializers.ValidationError("You can only assign roles from your company.")
        return role

    def validate(self, attrs):
        request_user = _request_user(self)
        company = attrs.get("id_company") or getattr(self.instance, "id_company", None)
        role = attrs.get("id_role") or getattr(self.instance, "id_role", None)
        password = attrs.get("password")
        password_confirm = attrs.pop("password_confirm", None)

        if request_user and request_user.is_authenticated and not request_user.is_superuser:
            company = request_user.id_company
            attrs["id_company"] = company
        if not company:
            raise serializers.ValidationError({"id_company": "A company is required."})
        if role and role.id_company_id != company.id_company:
            raise serializers.ValidationError({"id_role": "The role must belong to the selected company."})
        if role and role.status != STATUS_ACTIVE:
            raise serializers.ValidationError({"id_role": "The selected role is inactive."})
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Password is required."})
        if password_confirm is not None and password != password_confirm:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        if password:
            candidate = self.instance or UserAccount(
                email=attrs.get("email", ""),
                first_name=attrs.get("first_name", ""),
                last_name=attrs.get("last_name", ""),
                id_company=company,
            )
            try:
                validate_password(password, user=candidate)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})

        status = attrs.get("status", getattr(self.instance, "status", STATUS_ACTIVE))
        activating = bool(
            self.instance
            and not self.instance.is_active
            and status == STATUS_ACTIVE
        )
        creating_active = self.instance is None and status == STATUS_ACTIVE

        if (activating or creating_active) and company_active_user_limit_reached(company):
            raise serializers.ValidationError({"status": get_company_user_limit_message(company)})

        if (
            self.instance
            and request_user
            and request_user.is_authenticated
            and request_user.pk == self.instance.pk
            and status == STATUS_INACTIVE
        ):
            raise serializers.ValidationError({"status": "You cannot deactivate your own account."})

        attrs["is_active"] = status != STATUS_INACTIVE
        return attrs

    def _sync_profile(self, user, profile_data):
        from apps.employees.services import sync_employee_profile
        sync_employee_profile(user, **profile_data)

    def create(self, validated_data):
        profile_data = {
            "identification": validated_data.pop("identification", None),
            "position": validated_data.pop("position", None),
        }
        password = validated_data.pop("password")
        validated_data["is_staff"] = False
        validated_data["is_superuser"] = False
        validated_data["is_company_owner"] = False
        user = UserAccount.objects.create_user(password=password, **validated_data)
        self._sync_profile(user, profile_data)
        return user

    def update(self, instance, validated_data):
        profile_data = {}
        if "identification" in validated_data:
            profile_data["identification"] = validated_data.pop("identification")
        if "position" in validated_data:
            profile_data["position"] = validated_data.pop("position")
        password = validated_data.pop("password", None)
        validated_data.pop("is_staff", None)
        validated_data.pop("is_superuser", None)
        validated_data.pop("is_company_owner", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.email = instance.email.strip().lower()
        if password:
            instance.set_password(password)
        instance.save()
        self._sync_profile(instance, profile_data)
        return instance
