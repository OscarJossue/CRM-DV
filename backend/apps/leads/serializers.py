from rest_framework import serializers

from .models import Lead


class LeadSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_lead", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    assigned_user_email = serializers.EmailField(source="id_assigned_user.email", read_only=True)
    converted_client_name = serializers.CharField(source="id_converted_client.name", read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "id_lead",
            "id_company",
            "company_name",
            "id_assigned_user",
            "assigned_user_email",
            "id_converted_client",
            "converted_client_name",
            "name",
            "phone",
            "email",
            "source",
            "address",
            "status",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "id_converted_client",
            "created_at",
        ]
