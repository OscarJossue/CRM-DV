from rest_framework import serializers

from .models import Supervision


class SupervisionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_supervision", read_only=True)
    target_type = serializers.CharField(read_only=True)
    target_code = serializers.CharField(read_only=True)
    target_name = serializers.CharField(read_only=True)
    company_name = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    supervisor_email = serializers.EmailField(source="id_supervisor.email", read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Supervision
        fields = [
            "id",
            "id_supervision",
            "id_project",
            "id_inspection_assignment",
            "target_type",
            "target_code",
            "target_name",
            "company_name",
            "client_name",
            "id_supervisor",
            "supervisor_email",
            "observations",
            "approved",
            "rejected",
            "rejection_reason",
            "final_audit",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "approved",
            "rejected",
            "rejection_reason",
            "final_audit",
            "created_at",
            "updated_at",
        ]

    def get_company_name(self, obj):
        company = obj.company
        return getattr(company, "name", "") if company else ""

    def get_client_name(self, obj):
        client = obj.client
        return getattr(client, "name", "") if client else ""

    def validate(self, attrs):
        project = attrs.get("id_project", getattr(self.instance, "id_project", None))
        inspection = attrs.get(
            "id_inspection_assignment",
            getattr(self.instance, "id_inspection_assignment", None),
        )
        if bool(project) == bool(inspection):
            raise serializers.ValidationError(
                "Select exactly one project or inspection for this audit."
            )
        target = project or inspection
        current_target_id = None
        if self.instance:
            current_target_id = (
                ("project", self.instance.id_project_id)
                if self.instance.id_project_id
                else ("inspection", self.instance.id_inspection_assignment_id)
            )
        requested_target_id = (
            ("project", project.pk) if project else ("inspection", inspection.pk)
        )
        if target.status != "audit" and (not self.instance or requested_target_id != current_target_id):
            raise serializers.ValidationError(
                "Only a project or inspection currently waiting for audit can enter the audit queue."
            )

        supervisor = attrs.get("id_supervisor", getattr(self.instance, "id_supervisor", None))
        company_id = project.id_company_id if project else inspection.id_company_id
        if supervisor and supervisor.id_company_id != company_id:
            raise serializers.ValidationError(
                "Supervisor must belong to the same company as the audited record."
            )
        if supervisor and getattr(getattr(supervisor, "id_role", None), "is_contractor_only", False):
            raise serializers.ValidationError(
                "A contractor-only user cannot be assigned as auditor."
            )
        return attrs
