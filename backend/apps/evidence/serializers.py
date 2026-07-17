from rest_framework import serializers

from .models import EvidenceFile


class EvidenceFileSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_file", read_only=True)
    project_name = serializers.CharField(source="id_project.name", read_only=True)
    company_name = serializers.CharField(source="id_project.id_company.name", read_only=True)
    client_name = serializers.CharField(source="id_project.id_client.name", read_only=True)
    uploaded_by_email = serializers.EmailField(source="id_user.email", read_only=True)

    class Meta:
        model = EvidenceFile
        fields = [
            "id",
            "id_file",
            "id_project",
            "project_name",
            "company_name",
            "client_name",
            "id_user",
            "uploaded_by_email",
            "file_type",
            "file_url",
            "description",
            "created_at",
        ]
        read_only_fields = [
            "id_user",
            "created_at",
        ]
