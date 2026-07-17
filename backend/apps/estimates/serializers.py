from rest_framework import serializers

from .models import Estimate


class EstimateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_estimate", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    client_name = serializers.CharField(source="id_client.name", read_only=True)
    project_name = serializers.CharField(source="id_project.name", read_only=True)
    inspection_code = serializers.SerializerMethodField()

    class Meta:
        model = Estimate
        fields = [
            "id",
            "id_estimate",
            "id_company",
            "company_name",
            "id_client",
            "client_name",
            "id_project",
            "project_name",
            "id_inspection_assignment",
            "inspection_code",
            "logo",
            "description",
            "detail_items",
            "subtotal",
            "tax",
            "total",
            "validity_days",
            "status",
            "issue_date",
        ]
        read_only_fields = [
            "subtotal",
            "total",
            "issue_date",
        ]
    def get_inspection_code(self, obj):
        if not obj.id_inspection_assignment_id:
            return None
        return f"INS-{obj.id_inspection_assignment_id:05d}"

