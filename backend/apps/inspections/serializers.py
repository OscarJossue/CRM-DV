from rest_framework import serializers

from .models import Inspection


class InspectionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_inspection", read_only=True)
    project_name = serializers.CharField(source="id_project.project_name", read_only=True)
    client_name = serializers.CharField(source="id_project.id_client.name", read_only=True)
    company_name = serializers.CharField(source="id_project.id_company.name", read_only=True)
    inspector_email = serializers.EmailField(source="id_inspector.email", read_only=True)

    class Meta:
        model = Inspection
        fields = [
            "id",
            "id_inspection",
            "id_project",
            "project_name",
            "client_name",
            "company_name",
            "id_inspector",
            "inspector_email",
            "inspection_date",
            "damage_description",
            "materials",
            "photos",
            "estimated_time",
            "status",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "id_inspection",
            "project_name",
            "client_name",
            "company_name",
            "inspector_email",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        project = attrs.get("id_project") or getattr(self.instance, "id_project", None)
        inspector = attrs.get("id_inspector") or getattr(self.instance, "id_inspector", None)

        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication is required.")

        if request.user.is_superuser:
            return attrs

        if not request.user.id_company_id:
            raise serializers.ValidationError("Your user does not have a company assigned.")

        if project and project.id_company_id != request.user.id_company_id:
            raise serializers.ValidationError("Project must belong to your company.")

        if inspector and inspector.id_company_id != request.user.id_company_id:
            raise serializers.ValidationError("Inspector must belong to your company.")

        return attrs