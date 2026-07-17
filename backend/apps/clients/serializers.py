from rest_framework import serializers

from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_client", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Client
        fields = [
            "id",
            "id_client",
            "id_company",
            "company_name",
            "client_code",
            "name",
            "full_name",
            "first_name",
            "middle_name",
            "last_name",
            "second_last_name",
            "dni",
            "phone",
            "email",
            "address",
            "city",
            "state",
            "notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "id_client",
            "client_code",
            "company_name",
            "full_name",
            "created_at",
            "updated_at",
        ]