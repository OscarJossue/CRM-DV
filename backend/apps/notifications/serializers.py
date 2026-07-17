from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_notification", read_only=True)
    user_email = serializers.EmailField(source="id_user.email", read_only=True)
    company_name = serializers.CharField(source="id_user.id_company.name", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "id_notification",
            "id_user",
            "user_email",
            "company_name",
            "type",
            "title",
            "message",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "created_at",
        ]
