from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.models.choices import PLATFORM_CALENDAR
from apps.core.platform_permissions import (
    PERMISSION_DELETE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    PlatformPermissionRequiredMixin,
    require_platform_action,
    user_can_platform_action,
)

from apps.core.ui_translation import translate_ui_text as ui

from .forms import PlatformCalendarEventForm
from .models import PlatformCalendarEvent
from .models.choices import EVENT_STATUS_CANCELLED, EVENT_STATUS_DONE
from .services import (
    PLATFORM_CALENDAR_EVENT_TYPES,
    build_month_calendar_weeks,
    get_month_bounds,
    get_month_navigation,
    get_platform_calendar_items,
    group_calendar_items_by_day,
    normalize_month,
)


class PlatformAdminRequiredMixin(PlatformPermissionRequiredMixin):
    platform_module_name = PLATFORM_CALENDAR


class PlatformCalendarView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    platform_permission_required = PERMISSION_VIEW
    model = PlatformCalendarEvent
    template_name = "platform_calendar/list.html"
    context_object_name = "manual_events"
    login_url = "/login/"

    def get_queryset(self):
        first_day, last_day = get_month_bounds(
            self.request.GET.get("year"),
            self.request.GET.get("month"),
        )

        return (
            PlatformCalendarEvent.objects.select_related(
                "id_company",
                "id_subscription",
                "created_by",
            )
            .filter(
                start_date__gte=first_day,
                start_date__lte=last_day,
            )
            .order_by("start_date", "start_time", "title")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        year, month = normalize_month(
            self.request.GET.get("year"),
            self.request.GET.get("month"),
        )
        event_type = self.request.GET.get("type", "").strip()
        q = self.request.GET.get("q", "").strip()

        first_day, last_day = get_month_bounds(year, month)
        navigation = get_month_navigation(year, month)

        calendar_items = get_platform_calendar_items(
            first_day,
            last_day,
            event_type=event_type or None,
            q=q or None,
        )

        grouped_items = group_calendar_items_by_day(calendar_items)
        calendar_weeks = build_month_calendar_weeks(
            year,
            month,
            grouped_items,
        )

        context["page_title"] = "Platform Calendar"
        context["year"] = year
        context["month"] = month
        context["month_label"] = date_format(first_day, "F Y")
        context["first_day"] = first_day
        context["last_day"] = last_day
        context["navigation"] = navigation
        context["calendar_items"] = calendar_items
        context["grouped_items"] = grouped_items
        context["calendar_weeks"] = calendar_weeks
        context["week_days"] = [ui(day) for day in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]]
        context["event_type_filter"] = event_type
        context["q"] = q
        context["event_type_choices"] = PLATFORM_CALENDAR_EVENT_TYPES

        context["total_events"] = len(calendar_items)
        context["renewal_events"] = len([item for item in calendar_items if item.get("event_type") == "renewal"])
        context["payment_events"] = len([item for item in calendar_items if item.get("event_type") == "payment"])
        context["document_events"] = len([item for item in calendar_items if item.get("event_type") == "document"])
        context["notification_events"] = len([item for item in calendar_items if item.get("event_type") == "notification"])
        context["company_events"] = len([item for item in calendar_items if item.get("event_type") == "company"])
        context["manual_events_count"] = len([item for item in calendar_items if item.get("source") == "manual"])
        context["high_priority_events"] = len([item for item in calendar_items if item.get("priority") == "high"])

        context["can_create_platform_calendar"] = user_can_platform_action(
            self.request.user,
            PLATFORM_CALENDAR,
            "create",
        )
        context["can_edit_platform_calendar"] = user_can_platform_action(
            self.request.user,
            PLATFORM_CALENDAR,
            PERMISSION_EDIT,
        )
        context["can_delete_platform_calendar"] = user_can_platform_action(
            self.request.user,
            PLATFORM_CALENDAR,
            PERMISSION_DELETE,
        )

        return context


class PlatformCalendarEventDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    platform_permission_required = PERMISSION_VIEW
    model = PlatformCalendarEvent
    template_name = "platform_calendar/detail.html"
    context_object_name = "event"
    pk_url_kwarg = "id_event"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformCalendarEvent.objects.select_related(
            "id_company",
            "id_subscription",
            "id_subscription__id_plan",
            "created_by",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = self.object.title
        context["can_edit_platform_calendar"] = user_can_platform_action(
            self.request.user,
            PLATFORM_CALENDAR,
            PERMISSION_EDIT,
        )
        context["can_delete_platform_calendar"] = user_can_platform_action(
            self.request.user,
            PLATFORM_CALENDAR,
            PERMISSION_DELETE,
        )
        context["is_done"] = self.object.status == EVENT_STATUS_DONE
        context["is_cancelled"] = self.object.status == EVENT_STATUS_CANCELLED

        return context


class PlatformCalendarEventCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    platform_permission_required = "create"
    model = PlatformCalendarEvent
    form_class = PlatformCalendarEventForm
    template_name = "platform_calendar/form.html"
    login_url = "/login/"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Platform calendar event created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_calendar:detail",
            kwargs={"id_event": self.object.id_event},
        )


class PlatformCalendarEventUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    platform_permission_required = PERMISSION_EDIT
    model = PlatformCalendarEvent
    form_class = PlatformCalendarEventForm
    template_name = "platform_calendar/form.html"
    context_object_name = "event"
    pk_url_kwarg = "id_event"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformCalendarEvent.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        )

    def form_valid(self, form):
        messages.success(self.request, "Platform calendar event updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_calendar:detail",
            kwargs={"id_event": self.object.id_event},
        )


@require_POST
def platform_calendar_event_done_view(request, id_event):
    require_platform_action(
        request.user,
        PLATFORM_CALENDAR,
        PERMISSION_EDIT,
    )

    event = get_object_or_404(
        PlatformCalendarEvent,
        id_event=id_event,
    )

    event.status = EVENT_STATUS_DONE
    event.save(update_fields=["status", "updated_at"])

    messages.success(request, "Platform calendar event marked as done.")

    return redirect(
        "platform_calendar:detail",
        id_event=event.id_event,
    )


@require_POST
def platform_calendar_event_cancel_view(request, id_event):
    require_platform_action(
        request.user,
        PLATFORM_CALENDAR,
        PERMISSION_DELETE,
    )

    event = get_object_or_404(
        PlatformCalendarEvent,
        id_event=id_event,
    )

    event.status = EVENT_STATUS_CANCELLED
    event.save(update_fields=["status", "updated_at"])

    messages.success(request, "Platform calendar event cancelled.")

    return redirect(
        "platform_calendar:detail",
        id_event=event.id_event,
    )