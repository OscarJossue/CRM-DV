from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import UserAccount
from apps.platform_plans.models import PlatformPlan
from apps.platform_plans.models.choices import PLAN_STATUS_ACTIVE
from apps.platform_subscriptions.services import calculate_plan_renewal_date

from .models import Company
from .services import provision_company_with_admin


class CompanySerializer(serializers.ModelSerializer):
    """Platform company serializer with atomic tenant provisioning on POST.

    A company can no longer be created through the API without its SaaS plan,
    active subscription and first company administrator.
    """

    id_plan = serializers.PrimaryKeyRelatedField(
        queryset=PlatformPlan.objects.filter(status=PLAN_STATUS_ACTIVE),
        write_only=True,
        required=False,
    )
    start_date = serializers.DateField(write_only=True, required=False, default=timezone.localdate)
    renewal_date = serializers.DateField(write_only=True, required=False, allow_null=True)
    admin_first_name = serializers.CharField(write_only=True, required=False, max_length=150)
    admin_last_name = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=150)
    admin_email = serializers.EmailField(write_only=True, required=False)
    admin_phone = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=30)
    admin_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
        style={"input_type": "password"},
    )
    subscription_id = serializers.SerializerMethodField()

    provisioning_fields = {
        "id_plan",
        "start_date",
        "renewal_date",
        "admin_first_name",
        "admin_last_name",
        "admin_email",
        "admin_phone",
        "admin_password",
    }

    class Meta:
        model = Company
        fields = [
            "id_company",
            "name",
            "slug",
            "legal_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "country",
            "logo",
            "description",
            "default_language",
            "plan",
            "status",
            "user_limit",
            "created_at",
            "subscription_id",
            "id_plan",
            "start_date",
            "renewal_date",
            "admin_first_name",
            "admin_last_name",
            "admin_email",
            "admin_phone",
            "admin_password",
        ]
        read_only_fields = [
            "id_company",
            "slug",
            "plan",
            "user_limit",
            "created_at",
        ]


    def get_subscription_id(self, company):
        subscription = company.platform_subscriptions.order_by("-created_at").first()
        return subscription.id_subscription if subscription else None

    def validate_name(self, value):
        value = value.strip()
        queryset = Company.objects.filter(name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A company with this name already exists.")
        return value

    def validate_email(self, value):
        return value.strip().lower() if value else value

    def validate_admin_email(self, value):
        value = value.strip().lower()
        if UserAccount.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            supplied = self.provisioning_fields.intersection(self.initial_data.keys())
            if supplied:
                raise serializers.ValidationError(
                    "Administrator and subscription provisioning fields are only accepted when creating a company."
                )
            return attrs

        required = {
            "id_plan": "SaaS plan is required.",
            "admin_first_name": "Administrator first name is required.",
            "admin_email": "Administrator email is required.",
            "admin_password": "Administrator password is required.",
        }
        errors = {field: message for field, message in required.items() if not attrs.get(field)}
        if errors:
            raise serializers.ValidationError(errors)

        plan = attrs.get("id_plan")
        start_date = attrs.get("start_date") or timezone.localdate()
        renewal_date = attrs.get("renewal_date")
        if not renewal_date:
            renewal_date = calculate_plan_renewal_date(plan, start_date=start_date)
            attrs["renewal_date"] = renewal_date

        if renewal_date < start_date:
            raise serializers.ValidationError({"renewal_date": "Renewal date cannot be before the start date."})
        if renewal_date < timezone.localdate():
            raise serializers.ValidationError({"renewal_date": "Renewal date must be today or later."})

        password = attrs.get("admin_password")
        candidate = UserAccount(
            email=attrs.get("admin_email", ""),
            first_name=attrs.get("admin_first_name", ""),
            last_name=attrs.get("admin_last_name", ""),
        )
        try:
            validate_password(password, user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"admin_password": list(exc.messages)})

        return attrs

    def create(self, validated_data):
        plan = validated_data.pop("id_plan")
        start_date = validated_data.pop("start_date", timezone.localdate())
        renewal_date = validated_data.pop("renewal_date", None)
        admin_data = {
            "first_name": validated_data.pop("admin_first_name"),
            "last_name": validated_data.pop("admin_last_name", ""),
            "email": validated_data.pop("admin_email"),
            "phone": validated_data.pop("admin_phone", ""),
            "password": validated_data.pop("admin_password"),
        }

        # Status and plan limits are authoritative outputs of provisioning, not
        # client-controlled fields during creation.
        validated_data.pop("status", None)

        result = provision_company_with_admin(
            company_data=validated_data,
            admin_data=admin_data,
            subscription_data={
                "id_plan": plan,
                "start_date": start_date,
                "renewal_date": renewal_date,
            },
        )
        return result["company"]
