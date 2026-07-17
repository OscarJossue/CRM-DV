from rest_framework import serializers

from .models import Lead


class LeadSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_lead", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    client_name = serializers.CharField(source="id_client.name", read_only=True)
    assigned_user_email = serializers.SerializerMethodField()
    converted_project_name = serializers.SerializerMethodField()
    name = serializers.CharField(read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "id_lead",
            "opportunity_code",
            "id_company",
            "company_name",
            "id_client",
            "client_name",
            "id_assigned_user",
            "assigned_user_email",
            "id_converted_project",
            "converted_project_name",
            "contact_name",
            "name",
            "first_name",
            "middle_name",
            "last_name",
            "second_last_name",
            "phone",
            "email",
            "address",
            "source",
            "status",
            "notes",
            "next_follow_up_date",
            "approximate_value",
            "project_description",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "id_lead",
            "opportunity_code",
            "id_company",
            "company_name",
            "id_assigned_user",
            "assigned_user_email",
            "id_converted_project",
            "converted_project_name",
            "contact_name",
            "name",
            "first_name",
            "middle_name",
            "last_name",
            "second_last_name",
            "phone",
            "email",
            "address",
            "created_at",
            "updated_at",
        ]

    def get_assigned_user_email(self, obj):
        if obj.id_assigned_user:
            return obj.id_assigned_user.email

        return None

    def get_converted_project_name(self, obj):
        if obj.id_converted_project:
            return obj.id_converted_project.name

        return None

    def validate_id_client(self, value):
        request = self.context.get("request")

        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication is required.")

        if request.user.is_superuser:
            return value

        if value.id_company_id != request.user.id_company_id:
            raise serializers.ValidationError("Client must belong to your company.")

        return value