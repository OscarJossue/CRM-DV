from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.mixins import TenantModelViewSet
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_CREATE,
    PERMISSION_DELETE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    require_module_action_or_403,
    user_can_module_action,
)
from apps.projects.selectors import project_list_for_user

from .forms import CalendarEventForm
from .models import CalendarEvent
from .permissions import user_can_access_calendar_event
from .selectors import CALENDAR_EVENT_SELECT_RELATED, calendar_event_list_for_user
from .serializers import CalendarEventSerializer
from .services import (
    CALENDAR_EVENT_TYPES,
    build_month_calendar_weeks,
    calendar_event_cancel,
    calendar_event_complete,
    get_company_calendar_items,
    get_month_bounds,
    get_month_navigation,
    group_calendar_items_by_day,
    normalize_month,
)


def get_active_company(request):
    current_company = getattr(request, "current_company", None)
    if current_company:
        return current_company
    return getattr(request.user, "id_company", None)


def get_company_slug_from_request(request, company_slug=None):
    if company_slug:
        return company_slug

    company = get_active_company(request)
    if company and getattr(company, "slug", None):
        return company.slug

    return None


def redirect_to_company_calendar_list(request, company_slug=None):
    active_slug = get_company_slug_from_request(request, company_slug)

    if active_slug:
        return redirect(f"/{active_slug}/calendar/")

    return redirect("calendar_events:calendar_event_list")


def redirect_to_company_calendar_detail(request, calendar_event, company_slug=None):
    active_slug = get_company_slug_from_request(request, company_slug)

    if active_slug:
        return redirect(f"/{active_slug}/calendar/{calendar_event.id_event}/")

    return redirect(
        "calendar_events:calendar_event_detail",
        id_event=calendar_event.id_event,
    )


def serialize_calendar_items(items):
    serialized = []

    for item in items:
        item_date = item.get("date")
        item_time = item.get("time")
        end_time = item.get("end_time")

        serialized.append(
            {
                "id": item.get("uid"),
                "title": item.get("title") or "Calendar item",
                "type": item.get("event_type_label") or "Calendar item",
                "eventType": item.get("event_type") or "manual",
                "date": item_date.strftime("%A, %B %d, %Y") if item_date else "No date",
                "dateIso": item_date.isoformat() if item_date else "",
                "time": item_time.strftime("%I:%M %p") if item_time else "All day",
                "endTime": end_time.strftime("%I:%M %p") if end_time else "",
                "status": item.get("status_label") or item.get("status") or "Not specified",
                "priority": (item.get("priority") or "normal").title(),
                "description": item.get("description") or "No additional description was provided.",
                "location": item.get("location") or "No location specified.",
                "assignedTo": item.get("assigned_to") or "Not assigned",
                "relatedLabel": item.get("related_label") or item.get("meta") or "No linked record",
                "meta": item.get("meta") or "",
                "url": item.get("url") or "#",
            }
        )

    return serialized


def get_calendar_event_related_info(calendar_event, company_slug):
    relation_map = {
        "project": (
            calendar_event.id_project,
            "Project",
            "projects",
            "id_project",
        ),
        "inspection": (
            calendar_event.id_inspection_assignment,
            "Inspection",
            "inspections",
            "id_assignment",
        ),
        "estimate": (
            calendar_event.id_estimate,
            "Estimate",
            "estimates",
            "id_estimate",
        ),
        "invoice": (
            calendar_event.id_invoice,
            "Invoice",
            "invoices",
            "id_invoice",
        ),
        "payment": (
            calendar_event.id_payment,
            "Payment",
            "payments",
            "id_payment",
        ),
        "client": (
            calendar_event.id_client,
            "Client",
            "clients",
            "id_client",
        ),
        "opportunity": (
            calendar_event.id_opportunity,
            "Opportunity",
            "opportunities",
            "id_lead",
        ),
    }

    record, label, path, id_field = relation_map.get(
        calendar_event.related_type,
        (None, "Linked record", "", ""),
    )

    if not record:
        return None

    record_id = getattr(record, id_field, None)
    url = f"/{company_slug}/{path}/{record_id}/" if company_slug and record_id else "#"

    return {
        "type": label,
        "label": str(record),
        "url": url,
    }


class CalendarEventListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "calendar_events"
    permission_required = PERMISSION_VIEW
    template_name = "calendar_events/list.html"
    context_object_name = "calendar_events"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        return calendar_event_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.localdate()
        company = get_active_company(self.request)

        year, month = normalize_month(
            self.request.GET.get("year"),
            self.request.GET.get("month"),
        )
        event_type = self.request.GET.get("type", "").strip()
        q = self.request.GET.get("q", "").strip()

        first_day, last_day = get_month_bounds(year, month)
        navigation = get_month_navigation(year, month)

        calendar_items = get_company_calendar_items(
            user=self.request.user,
            company=company,
            start_date=first_day,
            end_date=last_day,
            event_type=event_type or None,
            q=q or None,
        )

        grouped_items = group_calendar_items_by_day(calendar_items)
        calendar_weeks = build_month_calendar_weeks(
            year,
            month,
            grouped_items,
        )

        manual_events_count = sum(
            1 for item in calendar_items if item.get("event_type") == "manual"
        )
        notification_events_count = sum(
            1 for item in calendar_items if item.get("event_type") == "notification"
        )
        finance_events_count = sum(
            1
            for item in calendar_items
            if item.get("event_type") in ["payment", "invoice", "estimate"]
        )
        high_priority_events_count = sum(
            1
            for item in calendar_items
            if item.get("priority") in ["high", "urgent"]
        )

        context.update(
            {
                "page_title": "Calendar",
                "company": company,
                "month_label": first_day.strftime("%B %Y"),
                "year": year,
                "month": month,
                "today": today,
                "first_day": first_day,
                "last_day": last_day,
                "navigation": navigation,
                "week_days": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
                "calendar_items": calendar_items,
                "calendar_modal_items": serialize_calendar_items(calendar_items),
                "grouped_items": grouped_items,
                "calendar_weeks": calendar_weeks,
                "event_type_choices": CALENDAR_EVENT_TYPES,
                "event_type_filter": event_type,
                "q": q,
                "has_active_filters": bool(event_type or q),
                "total_events": len(calendar_items),
                "manual_events_count": manual_events_count,
                "notification_events_count": notification_events_count,
                "finance_events_count": finance_events_count,
                "high_priority_events_count": high_priority_events_count,
                "can_create_calendar_events": user_can_module_action(
                    self.request.user,
                    "calendar_events",
                    PERMISSION_CREATE,
                ),
                "can_edit_calendar_events": user_can_module_action(
                    self.request.user,
                    "calendar_events",
                    PERMISSION_EDIT,
                ),
                "can_delete_calendar_events": user_can_module_action(
                    self.request.user,
                    "calendar_events",
                    PERMISSION_DELETE,
                ),
            }
        )

        return context


class CalendarEventDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "calendar_events"
    permission_required = PERMISSION_VIEW
    model = CalendarEvent
    template_name = "calendar_events/detail.html"
    context_object_name = "calendar_event"
    pk_url_kwarg = "id_event"
    login_url = "/login/"

    def get_queryset(self):
        return calendar_event_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_slug = get_company_slug_from_request(
            self.request,
            self.kwargs.get("company_slug"),
        )
        context["page_title"] = "Calendar Event Details"
        context["company_slug"] = company_slug
        context["related_record"] = get_calendar_event_related_info(
            self.object,
            company_slug,
        )
        context["can_edit_calendar_events"] = user_can_module_action(
            self.request.user,
            "calendar_events",
            PERMISSION_EDIT,
        )
        context["can_delete_calendar_events"] = user_can_module_action(
            self.request.user,
            "calendar_events",
            PERMISSION_DELETE,
        )
        return context


class CalendarEventCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "calendar_events"
    permission_required = PERMISSION_CREATE
    model = CalendarEvent
    form_class = CalendarEventForm
    template_name = "calendar_events/form.html"
    success_url = reverse_lazy("calendar_events:calendar_event_list")
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.project = None
        id_project = self.kwargs.get("id_project")

        if id_project:
            self.project = get_object_or_404(
                project_list_for_user(request.user),
                id_project=id_project,
            )

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("date"):
            initial["event_date"] = self.request.GET.get("date")
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["company"] = get_active_company(self.request)
        kwargs["project"] = self.project
        kwargs["initial_related_type"] = self.request.GET.get("related_type")
        kwargs["initial_related_id"] = self.request.GET.get("related_id")
        return kwargs

    def get_success_url(self):
        active_slug = get_company_slug_from_request(
            self.request,
            self.kwargs.get("company_slug"),
        )

        if active_slug:
            return f"/{active_slug}/calendar/{self.object.id_event}/"

        return reverse_lazy(
            "calendar_events:calendar_event_detail",
            kwargs={"id_event": self.object.id_event},
        )

    def form_valid(self, form):
        messages.success(self.request, "Calendar event created successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the calendar event form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Calendar Event"
        context["form_title"] = "Create Calendar Event"
        context["submit_label"] = "Save Event"
        context["project"] = self.project
        context["company_slug"] = get_company_slug_from_request(
            self.request,
            self.kwargs.get("company_slug"),
        )
        return context


class CalendarEventUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "calendar_events"
    permission_required = PERMISSION_EDIT
    model = CalendarEvent
    form_class = CalendarEventForm
    template_name = "calendar_events/form.html"
    context_object_name = "calendar_event"
    pk_url_kwarg = "id_event"
    login_url = "/login/"

    def get_queryset(self):
        return calendar_event_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["company"] = self.object.id_company
        return kwargs

    def get_success_url(self):
        active_slug = get_company_slug_from_request(
            self.request,
            self.kwargs.get("company_slug"),
        )

        if active_slug:
            return f"/{active_slug}/calendar/{self.object.id_event}/"

        return reverse_lazy(
            "calendar_events:calendar_event_detail",
            kwargs={"id_event": self.object.id_event},
        )

    def form_valid(self, form):
        messages.success(self.request, "Calendar event updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please review the calendar event form.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Calendar Event"
        context["form_title"] = "Edit Calendar Event"
        context["submit_label"] = "Update Event"
        context["project"] = None
        context["company_slug"] = get_company_slug_from_request(
            self.request,
            self.kwargs.get("company_slug"),
        )
        return context


@require_POST
def calendar_event_complete_view(request, id_event, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "calendar_events",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    calendar_event = get_object_or_404(CalendarEvent, id_event=id_event)

    if not user_can_access_calendar_event(request.user, calendar_event):
        return HttpResponseForbidden("Permission denied.")

    calendar_event_complete(calendar_event)
    messages.success(request, "Calendar event completed successfully.")

    return redirect_to_company_calendar_detail(
        request,
        calendar_event,
        company_slug=company_slug,
    )


@require_POST
def calendar_event_cancel_view(request, id_event, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "calendar_events",
        PERMISSION_DELETE,
    )

    if permission_response:
        return permission_response

    calendar_event = get_object_or_404(CalendarEvent, id_event=id_event)

    if not user_can_access_calendar_event(request.user, calendar_event):
        return HttpResponseForbidden("Permission denied.")

    calendar_event_cancel(calendar_event)
    messages.success(request, "Calendar event cancelled successfully.")

    return redirect_to_company_calendar_detail(
        request,
        calendar_event,
        company_slug=company_slug,
    )


class CalendarEventViewSet(TenantModelViewSet):
    module_name = "calendar_events"
    queryset = CalendarEvent.objects.select_related(
        *CALENDAR_EVENT_SELECT_RELATED
    ).all()
    serializer_class = CalendarEventSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return calendar_event_list_for_user(self.request.user)

    @staticmethod
    def _record_company_id(record):
        if not record:
            return None

        company_id = getattr(record, "id_company_id", None)
        if company_id:
            return company_id

        company = getattr(record, "id_company", None)
        company_id = getattr(company, "id_company", None)
        if company_id:
            return company_id

        client = getattr(record, "client", None) or getattr(record, "id_client", None)
        client_company_id = getattr(client, "id_company_id", None)
        if client_company_id:
            return client_company_id

        project = getattr(record, "id_project", None)
        return getattr(project, "id_company_id", None)

    def perform_create(self, serializer):
        company = serializer.validated_data.get("id_company")
        assigned_user = serializer.validated_data.get("id_assigned_user")

        if not self.request.user.is_superuser:
            company = self.request.user.id_company

        if not company:
            raise PermissionDenied("Company is required.")

        if assigned_user and assigned_user.id_company_id != company.id_company:
            raise PermissionDenied("Assigned user must belong to the selected company.")

        for field_name in [
            "id_project",
            "id_inspection_assignment",
            "id_estimate",
            "id_invoice",
            "id_payment",
            "id_client",
            "id_opportunity",
        ]:
            record = serializer.validated_data.get(field_name)
            if record and self._record_company_id(record) != company.id_company:
                raise PermissionDenied("Linked records must belong to the selected company.")

        serializer.save(id_company=company)

    def perform_update(self, serializer):
        instance = self.get_object()

        if not user_can_access_calendar_event(self.request.user, instance):
            raise PermissionDenied("You can only update calendar events from your company.")

        company = serializer.validated_data.get("id_company", instance.id_company)
        if not self.request.user.is_superuser:
            company = self.request.user.id_company

        if not company:
            raise PermissionDenied("Company is required.")

        assigned_user = serializer.validated_data.get(
            "id_assigned_user",
            instance.id_assigned_user,
        )
        if assigned_user and assigned_user.id_company_id != company.id_company:
            raise PermissionDenied("Assigned user must belong to the selected company.")

        for field_name in [
            "id_project",
            "id_inspection_assignment",
            "id_estimate",
            "id_invoice",
            "id_payment",
            "id_client",
            "id_opportunity",
        ]:
            record = serializer.validated_data.get(field_name, getattr(instance, field_name))
            if record and self._record_company_id(record) != company.id_company:
                raise PermissionDenied("Linked records must belong to the selected company.")

        serializer.save(id_company=company)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        if not user_can_module_action(request.user, "calendar_events", PERMISSION_EDIT):
            raise PermissionDenied("You do not have permission to complete calendar events.")

        calendar_event = self.get_object()
        calendar_event_complete(calendar_event)

        return Response(
            {
                "detail": "Calendar event completed successfully.",
                "event_id": calendar_event.id_event,
                "status": calendar_event.status,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        if not user_can_module_action(request.user, "calendar_events", PERMISSION_DELETE):
            raise PermissionDenied("You do not have permission to cancel calendar events.")

        calendar_event = self.get_object()
        calendar_event_cancel(calendar_event)

        return Response(
            {
                "detail": "Calendar event cancelled successfully.",
                "event_id": calendar_event.id_event,
                "status": calendar_event.status,
            }
        )
