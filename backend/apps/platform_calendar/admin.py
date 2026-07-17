from django.contrib import admin

from .models import PlatformCalendarEvent


@admin.register(PlatformCalendarEvent)
class PlatformCalendarEventAdmin(admin.ModelAdmin):
    list_display = (
        "id_event",
        "title",
        "event_type",
        "id_company",
        "start_date",
        "start_time",
        "status",
        "priority",
        "created_by",
    )
    list_filter = ("event_type", "status", "priority", "start_date")
    search_fields = ("title", "id_company__name", "description")