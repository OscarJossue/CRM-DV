from rest_framework import serializers

from .models import Project, ProjectAssignment


class ProjectSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_project", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    client_name = serializers.CharField(source="id_client.name", read_only=True)
    inspector_email = serializers.EmailField(source="id_inspector.email", read_only=True)
    project_name = serializers.CharField(source="name", read_only=True)
    expected_end_date = serializers.DateField(source="end_date", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "id_project",
            "project_code",
            "id_company",
            "company_name",
            "id_client",
            "client_name",
            "id_opportunity",
            "id_inspector",
            "inspector_email",
            "invoice_status",
            "name",
            "project_name",
            "project_address",
            "description",
            "status",
            "progress",
            "contract_amount",
            "start_date",
            "end_date",
            "expected_end_date",
            "created_by",
            "updated_by",
            "submitted_for_audit_at",
            "audit_completed_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "id_project",
            "project_code",
            "company_name",
            "client_name",
            "inspector_email",
            "project_name",
            "expected_end_date",
            "created_by",
            "updated_by",
            "submitted_for_audit_at",
            "audit_completed_at",
            "created_at",
            "updated_at",
        ]

    def validate_status(self, value):
        current_status = getattr(self.instance, "status", None) if self.instance else None
        if value in {"review", "completed", "cancelled"} and value != current_status:
            raise serializers.ValidationError(
                "Under Review, Approved and Void are controlled by the dedicated workflow actions."
            )
        if current_status in {"completed", "cancelled"} and value != current_status:
            raise serializers.ValidationError("Approved or void projects cannot return to a previous status.")
        return value


class ProjectAssignmentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_assignment", read_only=True)
    project_name = serializers.CharField(source="id_project.name", read_only=True)
    user_email = serializers.EmailField(source="id_user.email", read_only=True)
    user_name = serializers.SerializerMethodField()
    role_name = serializers.CharField(source="id_user.id_role.name", read_only=True)
    company_name = serializers.CharField(source="id_project.id_company.name", read_only=True)

    class Meta:
        model = ProjectAssignment
        fields = [
            "id",
            "id_assignment",
            "id_project",
            "project_name",
            "id_user",
            "user_name",
            "user_email",
            "role_name",
            "company_name",
            "task",
            "progress",
            "status",
            "assigned_at",
        ]

        read_only_fields = [
            "id",
            "id_assignment",
            "project_name",
            "user_name",
            "user_email",
            "role_name",
            "company_name",
            "assigned_at",
        ]

    def get_user_name(self, obj):
        if not obj.id_user:
            return ""

        full_name = f"{obj.id_user.first_name or ''} {obj.id_user.last_name or ''}".strip()

        return full_name or obj.id_user.email