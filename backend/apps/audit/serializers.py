from rest_framework import serializers

from .models import SystemLog


class SystemLogSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_log", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    user_email = serializers.CharField(source="actor_email", read_only=True)
    user_name = serializers.CharField(source="actor_name", read_only=True)
    action_label = serializers.CharField(source="get_action_type_display", read_only=True)
    severity_label = serializers.CharField(source="get_severity_display", read_only=True)

    class Meta:
        model = SystemLog
        fields = [
            "id",
            "id_log",
            "id_company",
            "company_name",
            "id_user",
            "user_name",
            "user_email",
            "module",
            "action",
            "action_type",
            "action_label",
            "severity",
            "severity_label",
            "result",
            "object_type",
            "object_id",
            "object_label",
            "changes",
            "ip",
            "request_id",
            "created_at",
            "expires_at",
        ]
        read_only_fields = fields
