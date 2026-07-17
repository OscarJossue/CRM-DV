import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_CREATE,
    PERMISSION_DELETE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    user_can_module_action,
)
from apps.core.tenant import filter_queryset_for_user, get_user_company

from .forms import (
    CalendarEventForm,
    DateRangeReportForm,
    GoogleAdsLeadReplyForm,
    GoogleAdsLeadStatusForm,
    GoogleAdsLeadSyncForm,
    DriveUploadForm,
    GoogleConnectionSettingsForm,
    GoogleOAuthCredentialsForm,
    SheetExportForm,
)
from .models import (
    GoogleAdsLead,
    GoogleAdsLeadReply,
    GoogleAdsSnapshot,
    GoogleAnalyticsSnapshot,
    GoogleCalendarEventLink,
    GoogleDriveUpload,
    GoogleIntegrationConnection,
    GoogleSheetExport,
    IntegrationLog,
)
from .models.choices import LOG_ERROR, LOG_SUCCESS, STATUS_CONNECTED, STATUS_DISCONNECTED, TOOL_OAUTH
from .selectors import (
    ads_snapshots_for_user,
    analytics_snapshots_for_user,
    calendar_events_for_user,
    connection_for_user,
    connections_for_user,
    drive_uploads_for_user,
    google_ads_leads_for_user,
    logs_for_user,
    sheet_exports_for_user,
)
from .services.google_api import (
    append_rows_to_sheet,
    apply_token_response,
    build_google_authorization_url,
    create_google_calendar_event,
    create_log,
    disconnect_google,
    exchange_code_for_tokens,
    fetch_google_userinfo,
    log_google_lead_reply,
    process_google_ads_webhook,
    run_ads_report,
    run_analytics_report,
    sync_google_lead_form_submissions,
    sync_local_services_leads,
    upload_file_to_drive,
)

MODULE_NAME = "integrations"


class SensitiveResponseMixin:
    """Prevent browser/proxy caching and framing of integration secrets."""
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "no-referrer"
        return response


def _company_or_403(request):
    company = get_user_company(request.user)
    if not company:
        return None
    return company


def _get_connection_or_message(request):
    connection = connection_for_user(request.user)
    if not connection:
        messages.warning(request, "Connect Google first before using this tool.")
    return connection


def _analytics_chart_data(snapshots):
    """Build JSON-safe chart data from the newest GA4 daily series.

    Older snapshots created before daily-series support are still visualized
    by using their period totals as historical points.
    """
    snapshots = list(snapshots)
    if not snapshots:
        return {
            "labels": [],
            "active_users": [],
            "sessions": [],
            "conversions": [],
            "revenue": [],
        }

    latest = snapshots[0]
    raw = latest.raw_response if isinstance(latest.raw_response, dict) else {}
    series_response = raw.get("series") if isinstance(raw.get("series"), dict) else {}
    rows = series_response.get("rows") or []

    labels = []
    active_users = []
    sessions = []
    conversions = []
    revenue = []

    for row in rows:
        dimensions = row.get("dimensionValues") or []
        metrics = row.get("metricValues") or []
        raw_date = dimensions[0].get("value", "") if dimensions else ""
        try:
            label = datetime.strptime(raw_date, "%Y%m%d").strftime("%b %d")
        except (TypeError, ValueError):
            label = raw_date or "—"

        def metric(index, cast=float):
            try:
                value = metrics[index].get("value", "0")
                return cast(float(value or 0))
            except (IndexError, TypeError, ValueError, AttributeError):
                return cast(0)

        labels.append(label)
        active_users.append(metric(0, int))
        sessions.append(metric(1, int))
        conversions.append(metric(2, int))
        revenue.append(round(metric(3, float), 2))

    if labels:
        return {
            "labels": labels,
            "active_users": active_users,
            "sessions": sessions,
            "conversions": conversions,
            "revenue": revenue,
        }

    # Backward-compatible fallback for snapshots created before daily series.
    for snapshot in reversed(snapshots[:12]):
        labels.append(snapshot.date_to.strftime("%b %d"))
        active_users.append(int(snapshot.active_users or 0))
        sessions.append(int(snapshot.sessions or 0))
        conversions.append(int(snapshot.conversions or 0))
        revenue.append(float(snapshot.total_revenue or 0))

    return {
        "labels": labels,
        "active_users": active_users,
        "sessions": sessions,
        "conversions": conversions,
        "revenue": revenue,
    }


def _analytics_report_context(user, form, connection=None):
    snapshots = list(analytics_snapshots_for_user(user)[:20])
    return {
        "form": form,
        "connection": connection if connection is not None else connection_for_user(user),
        "snapshots": snapshots,
        "latest_snapshot": snapshots[0] if snapshots else None,
        "analytics_chart_data": _analytics_chart_data(snapshots),
        "can_sync_integrations": user_can_module_action(user, MODULE_NAME, PERMISSION_EDIT),
    }


def _get_or_create_company_google_connection(request):
    company = _company_or_403(request)
    if not company:
        return None
    connection, created = GoogleIntegrationConnection.objects.get_or_create(
        id_company=company,
        provider="google",
        defaults={"created_by": request.user, "updated_by": request.user},
    )
    if not created and not connection.updated_by:
        connection.updated_by = request.user
        connection.save(update_fields=["updated_by", "updated_at"])
    return connection


class IntegrationDashboardView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, TemplateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        connection = connection_for_user(self.request.user)
        logs_queryset = logs_for_user(self.request.user)
        context.update({
            "connection": connection,
            "recent_logs": logs_queryset[:8],
            "calendar_count": calendar_events_for_user(self.request.user).count(),
            "drive_count": drive_uploads_for_user(self.request.user).count(),
            "analytics_count": analytics_snapshots_for_user(self.request.user).count(),
            "log_count": logs_queryset.count(),
            "can_manage_integrations": user_can_module_action(self.request.user, MODULE_NAME, PERMISSION_EDIT),
        })
        return context


class ConnectionListView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/connection_list.html"
    context_object_name = "connections"

    def get_queryset(self):
        return connections_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage_integrations"] = user_can_module_action(self.request.user, MODULE_NAME, PERMISSION_EDIT)
        context["company_connection"] = connection_for_user(self.request.user)
        return context


class ConnectionDetailView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/connection_detail.html"
    context_object_name = "connection"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return connections_for_user(self.request.user)


class ConnectionSettingsView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT
    template_name = "integrations/settings_form.html"
    form_class = GoogleConnectionSettingsForm
    context_object_name = "connection"

    def get_object(self, queryset=None):
        return get_object_or_404(connections_for_user(self.request.user), pk=self.kwargs.get("pk"))

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, "Integration settings updated correctly.")
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path.replace("settings/", "")


class GoogleCredentialsSetupView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT
    template_name = "integrations/google_credentials_form.html"
    form_class = GoogleOAuthCredentialsForm
    context_object_name = "connection"

    def get_object(self, queryset=None):
        connection = _get_or_create_company_google_connection(self.request)
        if not connection:
            raise PermissionError("User does not have a company assigned.")
        return connection

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Google app credentials saved encrypted for this company.")
        return response

    def get_success_url(self):
        return reverse("integrations:dashboard")


class GoogleConnectStartView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT

    def post(self, request, *args, **kwargs):
        company = _company_or_403(request)
        if not company:
            return HttpResponseForbidden("User does not have a company assigned.")
        connection = _get_or_create_company_google_connection(request)
        if not connection.has_google_app_credentials:
            messages.warning(request, "First configure the Google App credentials for this company. They are saved encrypted and are not global.")
            return redirect("integrations:google_credentials_setup")
        try:
            url = build_google_authorization_url(request, connection, getattr(company, "slug", None))
            return redirect(url)
        except Exception as exc:
            messages.error(request, str(exc))
            return redirect("integrations:dashboard")


class GoogleCallbackView(SensitiveResponseMixin, LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        company = _company_or_403(request)
        if not company:
            return HttpResponseForbidden("User does not have a company assigned.")

        state = request.GET.get("state") or ""
        expected_state = request.session.pop("google_oauth_state", "")
        expected_company_slug = request.session.pop("google_oauth_company_slug", "")
        connection_id = request.session.pop("google_oauth_connection_id", None)
        if not state or not expected_state or state != expected_state:
            messages.error(request, "Google OAuth session is invalid or expired. Try connecting again.")
            return redirect("integrations:dashboard")
        if expected_company_slug and expected_company_slug != getattr(company, "slug", ""):
            messages.error(request, "Google OAuth company scope is invalid.")
            return redirect("integrations:dashboard")

        error = request.GET.get("error")
        if error:
            messages.error(request, f"Google connection was cancelled or rejected: {error}")
            return redirect("integrations:dashboard")

        code = request.GET.get("code")
        if not code:
            messages.error(request, "Google did not return an authorization code.")
            return redirect("integrations:dashboard")

        if connection_id:
            connection = get_object_or_404(GoogleIntegrationConnection.objects.filter(id_company=company, provider="google"), pk=connection_id)
        else:
            connection = _get_or_create_company_google_connection(request)
        try:
            token_response = exchange_code_for_tokens(request, connection, code)
            access_token = apply_token_response(connection, token_response, user=request.user)
            userinfo = fetch_google_userinfo(access_token)
            connection.connected_email = userinfo.get("email") or connection.connected_email
            connection.display_name = userinfo.get("name") or connection.display_name
            connection.status = STATUS_CONNECTED
            connection.last_error = ""
            connection.updated_by = request.user
            connection.save()
            create_log(company, connection, TOOL_OAUTH, "Google connected", LOG_SUCCESS, "Google account connected successfully.", response_payload={"email": connection.connected_email}, user=request.user)
            messages.success(request, "Google account connected successfully.")
        except Exception as exc:
            connection.status = "error"
            connection.last_error = str(exc)
            connection.save(update_fields=["status", "last_error", "updated_at"])
            create_log(company, connection, TOOL_OAUTH, "Google connection failed", LOG_ERROR, str(exc), user=request.user)
            messages.error(request, "Google could not be connected. Review the integration log or try again.")
        return redirect("integrations:dashboard")


class GoogleDisconnectView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT

    def post(self, request, pk, *args, **kwargs):
        connection = get_object_or_404(connections_for_user(request.user), pk=pk)
        disconnect_google(connection, user=request.user)
        messages.success(request, "Google connection disconnected.")
        return redirect("integrations:dashboard")


class CalendarEventListView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/calendar_list.html"
    context_object_name = "calendar_events"

    def get_queryset(self):
        return calendar_events_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["connection"] = connection_for_user(self.request.user)
        context["can_create_integrations"] = user_can_module_action(self.request.user, MODULE_NAME, PERMISSION_CREATE)
        return context


class CalendarEventCreateView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_CREATE
    template_name = "integrations/calendar_form.html"
    form_class = CalendarEventForm

    def form_valid(self, form):
        connection = _get_connection_or_message(self.request)
        company = _company_or_403(self.request)
        if not connection or not company:
            return redirect("integrations:calendar_list")
        form.instance.id_company = company
        form.instance.connection = connection
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        try:
            create_google_calendar_event(self.object, user=self.request.user)
            messages.success(self.request, "Calendar event and Google Meet link created successfully.")
        except Exception as exc:
            messages.error(self.request, str(exc))
        return response

    def get_success_url(self):
        return self.request.path.rsplit("new/", 1)[0]


class DriveUploadListView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/drive_list.html"
    context_object_name = "uploads"

    def get_queryset(self):
        return drive_uploads_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["connection"] = connection_for_user(self.request.user)
        context["can_create_integrations"] = user_can_module_action(self.request.user, MODULE_NAME, PERMISSION_CREATE)
        return context


class DriveUploadCreateView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_CREATE
    template_name = "integrations/drive_upload_form.html"
    form_class = DriveUploadForm

    def form_valid(self, form):
        connection = _get_connection_or_message(self.request)
        company = _company_or_403(self.request)
        if not connection or not company:
            return redirect("integrations:drive_list")
        form.instance.id_company = company
        form.instance.connection = connection
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        try:
            upload_file_to_drive(self.object, user=self.request.user)
            messages.success(self.request, "File uploaded to Google Drive successfully.")
        except Exception as exc:
            messages.error(self.request, str(exc))
        return response

    def get_success_url(self):
        return self.request.path.rsplit("upload/", 1)[0]


class SheetExportListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/sheets_list.html"
    context_object_name = "exports"

    def get_queryset(self):
        return sheet_exports_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["connection"] = connection_for_user(self.request.user)
        context["can_create_integrations"] = user_can_module_action(self.request.user, MODULE_NAME, PERMISSION_CREATE)
        return context


class SheetExportCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_CREATE
    template_name = "integrations/sheets_export_form.html"
    form_class = SheetExportForm

    def get_initial(self):
        initial = super().get_initial()
        connection = connection_for_user(self.request.user)
        if connection and connection.default_spreadsheet_id:
            initial["spreadsheet_id"] = connection.default_spreadsheet_id
        return initial

    def form_valid(self, form):
        connection = _get_connection_or_message(self.request)
        company = _company_or_403(self.request)
        if not connection or not company:
            return redirect("integrations:sheets_list")
        form.instance.id_company = company
        form.instance.connection = connection
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        try:
            append_rows_to_sheet(self.object, user=self.request.user)
            messages.success(self.request, "CRM data exported to Google Sheets successfully.")
        except Exception as exc:
            messages.error(self.request, str(exc))
        return response

    def get_success_url(self):
        return self.request.path.rsplit("export/", 1)[0]


class AnalyticsReportView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/analytics_report.html"

    def get(self, request, *args, **kwargs):
        form = DateRangeReportForm(default_days=30)
        return render(
            request,
            self.template_name,
            _analytics_report_context(request.user, form),
        )

    def post(self, request, *args, **kwargs):
        if not user_can_module_action(request.user, MODULE_NAME, PERMISSION_EDIT):
            return HttpResponseForbidden("Permission denied.")

        form = DateRangeReportForm(request.POST, default_days=30)
        connection = _get_connection_or_message(request)
        if form.is_valid() and connection:
            try:
                run_analytics_report(
                    connection,
                    form.cleaned_data["date_from"],
                    form.cleaned_data["date_to"],
                    user=request.user,
                )
                messages.success(request, "Analytics report and charts synchronized successfully.")
                return redirect("integrations:analytics_report")
            except Exception as exc:
                messages.error(request, str(exc))

        return render(
            request,
            self.template_name,
            _analytics_report_context(request.user, form, connection=connection),
        )


class AdsReportView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/ads_report.html"

    def get(self, request, *args, **kwargs):
        form = DateRangeReportForm(default_days=30)
        return render(request, self.template_name, {
            "form": form,
            "connection": connection_for_user(request.user),
            "snapshots": ads_snapshots_for_user(request.user)[:20],
            "can_sync_integrations": user_can_module_action(request.user, MODULE_NAME, PERMISSION_EDIT),
        })

    def post(self, request, *args, **kwargs):
        if not user_can_module_action(request.user, MODULE_NAME, PERMISSION_EDIT):
            return HttpResponseForbidden("Permission denied.")
        form = DateRangeReportForm(request.POST, default_days=30)
        connection = _get_connection_or_message(request)
        if form.is_valid() and connection:
            try:
                run_ads_report(connection, form.cleaned_data["date_from"], form.cleaned_data["date_to"], user=request.user)
                messages.success(request, "Google Ads report synchronized successfully.")
                return redirect("integrations:ads_report")
            except Exception as exc:
                messages.error(request, str(exc))
        return render(request, self.template_name, {
            "form": form,
            "connection": connection,
            "snapshots": ads_snapshots_for_user(request.user)[:20],
            "can_sync_integrations": user_can_module_action(request.user, MODULE_NAME, PERMISSION_EDIT),
        })


class GoogleAdsLeadListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/google_ads_lead_list.html"
    context_object_name = "ads_leads"
    paginate_by = 40

    def get_queryset(self):
        queryset = google_ads_leads_for_user(self.request.user)
        status = self.request.GET.get("status")
        source = self.request.GET.get("source")
        q = (self.request.GET.get("q") or "").strip()
        if status:
            queryset = queryset.filter(crm_status=status)
        if source:
            queryset = queryset.filter(source=source)
        if q:
            queryset = queryset.filter(customer_name__icontains=q) | queryset.filter(phone__icontains=q) | queryset.filter(email__icontains=q)
        return queryset.order_by("-received_at", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        connection = connection_for_user(self.request.user)
        context.update({
            "connection": connection,
            "sync_form": GoogleAdsLeadSyncForm(default_days=7),
            "can_sync_integrations": user_can_module_action(self.request.user, MODULE_NAME, PERMISSION_EDIT),
            "can_create_integrations": user_can_module_action(self.request.user, MODULE_NAME, PERMISSION_CREATE),
        })
        if connection:
            company_slug = getattr(connection.id_company, "slug", "")
            context["webhook_url"] = self.request.build_absolute_uri(reverse("integrations:google_ads_webhook", kwargs={"company_slug": company_slug}))
            context["webhook_key_masked"] = connection.lead_webhook_key_masked
        return context


class GoogleAdsLeadSyncView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT

    def post(self, request, *args, **kwargs):
        connection = _get_connection_or_message(request)
        form = GoogleAdsLeadSyncForm(request.POST, default_days=7)
        if not connection:
            return redirect("integrations:ads_leads")
        if form.is_valid():
            try:
                source = form.cleaned_data["sync_source"]
                if source == "local_services":
                    result = sync_local_services_leads(connection, form.cleaned_data["date_from"], form.cleaned_data["date_to"], user=request.user)
                    messages.success(request, f"Google Guaranteed leads synced: {result['created']} new, {result['updated']} updated.")
                else:
                    result = sync_google_lead_form_submissions(connection, form.cleaned_data["date_from"], form.cleaned_data["date_to"], user=request.user)
                    messages.success(request, f"Google Ads lead forms synced: {result['created']} new, {result['updated']} updated.")
            except Exception as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Check the sync form dates and source.")
        return redirect("integrations:ads_leads")


class GoogleAdsLeadDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/google_ads_lead_detail.html"
    context_object_name = "ads_lead"
    pk_url_kwarg = "pk"

    def get_queryset(self):
        return google_ads_leads_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reply_form"] = GoogleAdsLeadReplyForm(lead=self.object)
        context["status_form"] = GoogleAdsLeadStatusForm(instance=self.object)
        context["can_manage_integrations"] = user_can_module_action(self.request.user, MODULE_NAME, PERMISSION_EDIT)
        return context


class GoogleAdsLeadStatusUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT

    def post(self, request, pk, *args, **kwargs):
        ads_lead = get_object_or_404(google_ads_leads_for_user(request.user), pk=pk)
        form = GoogleAdsLeadStatusForm(request.POST, instance=ads_lead)
        if form.is_valid():
            form.instance.updated_by = request.user
            form.save()
            messages.success(request, "Google lead status updated.")
        else:
            messages.error(request, "Could not update status.")
        return redirect("integrations:ads_lead_detail", pk=ads_lead.pk)


class GoogleAdsLeadCreateCrmLeadView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT

    def post(self, request, pk, *args, **kwargs):
        ads_lead = get_object_or_404(google_ads_leads_for_user(request.user), pk=pk)
        from .services.google_api import _create_or_update_crm_lead
        crm_lead = _create_or_update_crm_lead(ads_lead, user=request.user)
        messages.success(request, f"CRM lead linked: {crm_lead.name}.")
        return redirect("integrations:ads_lead_detail", pk=ads_lead.pk)


class GoogleAdsLeadReplyCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT

    def post(self, request, pk, *args, **kwargs):
        ads_lead = get_object_or_404(google_ads_leads_for_user(request.user), pk=pk)
        form = GoogleAdsLeadReplyForm(request.POST, lead=ads_lead)
        if form.is_valid():
            reply = log_google_lead_reply(
                ads_lead,
                form.cleaned_data["channel"],
                form.cleaned_data["message"],
                subject=form.cleaned_data.get("subject") or "",
                user=request.user,
            )
            if reply.status == "error":
                messages.error(request, reply.error_message or "The response was saved, but Google rejected the send attempt.")
            else:
                messages.success(request, "Response saved. If Google Message was selected for a Google Guaranteed lead, it was sent/appended to the Google conversation.")
        else:
            messages.error(request, "Could not save the response.")
        return redirect("integrations:ads_lead_detail", pk=ads_lead.pk)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleAdsLeadWebhookView(View):
    def post(self, request, company_slug, *args, **kwargs):
        try:
            content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            return JsonResponse({"message": "Invalid request"}, status=400)
        if content_length > 524288 or len(request.body) > 524288:
            return JsonResponse({"message": "Payload too large"}, status=413)
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return JsonResponse({"message": "Invalid JSON payload"}, status=400)
        Company = GoogleIntegrationConnection._meta.get_field("id_company").remote_field.model
        try:
            company = Company.objects.get(slug=company_slug)
        except Company.DoesNotExist:
            return JsonResponse({"message": "Company not found"}, status=404)
        connection = GoogleIntegrationConnection.objects.filter(id_company=company, provider="google").first()
        try:
            ads_lead, created = process_google_ads_webhook(company, payload, connection=connection)
            return JsonResponse({"status": "ok", "created": created, "lead_id": ads_lead.external_lead_id})
        except PermissionError as exc:
            return JsonResponse({"message": "Webhook authentication failed"}, status=403)
        except Exception as exc:
            return JsonResponse({"message": "Webhook processing failed"}, status=500)

    def get(self, request, company_slug, *args, **kwargs):
        return JsonResponse({"status": "ready"})


class SyncLogListView(SensitiveResponseMixin, LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "integrations/sync_logs.html"
    context_object_name = "logs"
    paginate_by = 50

    def get_queryset(self):
        queryset = logs_for_user(self.request.user)
        tool = self.request.GET.get("tool")
        status = self.request.GET.get("status")
        if tool:
            queryset = queryset.filter(tool=tool)
        if status:
            queryset = queryset.filter(status=status)
        return queryset
