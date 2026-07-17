from rest_framework import serializers

from .models import CompanyModule


class CompanyModuleSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_company_module", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)

    class Meta:
        model = CompanyModule
        fields = [
            "id",
            "id_company_module",
            "id_company",
            "company_name",
            "module",
            "is_enabled",
            "created_at",
        ]
        read_only_fields = [
            "created_at",
        ]
