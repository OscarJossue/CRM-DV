from rest_framework import serializers

from .models import Contract


class ContractSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_contract", read_only=True)
    client_name = serializers.CharField(source="id_client.name", read_only=True)
    project_name = serializers.CharField(source="id_project.name", read_only=True)
    company_name = serializers.CharField(source="id_project.id_company.name", read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "id_contract",
            "id_client",
            "client_name",
            "id_project",
            "project_name",
            "company_name",
            "terms",
            "file_url",
            "signed_date",
            "status",
        ]
