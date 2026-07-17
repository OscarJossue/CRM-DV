from rest_framework import serializers

from .models import CalendarEvent


class CalendarEventSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="id_event", read_only=True)
    company_name = serializers.CharField(source="id_company.name", read_only=True)
    project_name = serializers.CharField(source="id_project.name", read_only=True)
    client_name = serializers.CharField(source="id_project.id_client.name", read_only=True)
    assigned_user_email = serializers.EmailField(
        source="id_assigned_user.email",
        read_only=True,
    )
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "id_event",
            "id_company",
            "company_name",
            "related_type",
            "id_project",
            "project_name",
            "client_name",
            "id_inspection_assignment",
            "id_estimate",
            "id_invoice",
            "id_payment",
            "id_client",
            "id_opportunity",
            "id_assigned_user",
            "assigned_user_email",
            "title",
            "description",
            "category",
            "category_label",
            "priority",
            "priority_label",
            "event_date",
            "start_time",
            "end_time",
            "location",
            "status",
            "status_label",
        ]
