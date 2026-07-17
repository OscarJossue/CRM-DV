import json
import hmac
import mimetypes
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from django.apps import apps
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..models import (
    GoogleAdsLead,
    GoogleAdsLeadReply,
    GoogleAdsSnapshot,
    GoogleAnalyticsSnapshot,
    GoogleIntegrationConnection,
    IntegrationLog,
)
from ..models.choices import (
    LOG_ERROR,
    LOG_SUCCESS,
    REPLY_CHANNEL_CRM_NOTE,
    REPLY_CHANNEL_GOOGLE_MESSAGE,
    REPLY_STATUS_ERROR,
    REPLY_STATUS_LOGGED,
    REPLY_STATUS_SENT,
    STATUS_CONNECTED,
    STATUS_ERROR,
    STATUS_EXPIRED,
    STATUS_REVOKED,
    TOOL_ADS,
    TOOL_ADS_LEADS,
    TOOL_ANALYTICS,
    TOOL_CALENDAR,
    TOOL_DRIVE,
    TOOL_OAUTH,
    TOOL_SHEETS,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
GOOGLE_DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink,name"
GOOGLE_SHEETS_APPEND_URL = "https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}:append"
GOOGLE_ANALYTICS_RUN_REPORT_URL = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
GOOGLE_ADS_SEARCH_STREAM_URL = "https://googleads.googleapis.com/v24/customers/{customer_id}/googleAds:searchStream"
GOOGLE_LSA_APPEND_CONVERSATION_URL = "https://googleads.googleapis.com/v24/customers/{customer_id}/localServices:appendLeadConversation"

# Least-privilege scopes for the tools currently enabled in the CRM.
# Google Sheets and Google Ads are intentionally deferred and therefore are
# not requested during OAuth authorization.
GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def get_google_client_id(connection=None):
    """Return OAuth Client ID for this company connection.

    Company-level encrypted credentials are preferred. Environment variables are
    kept as an optional fallback for local/platform-wide testing.
    """
    if connection is not None and hasattr(connection, "get_oauth_client_id"):
        value = connection.get_oauth_client_id()
        if value:
            return value
    return os.getenv("GOOGLE_OAUTH_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID", "")


def get_google_client_secret(connection=None):
    if connection is not None and hasattr(connection, "get_oauth_client_secret"):
        value = connection.get_oauth_client_secret()
        if value:
            return value
    return os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET", "")


def _json_request(url, method="GET", access_token=None, payload=None, headers=None, timeout=45):
    headers = headers or {}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw
        raise RuntimeError(f"Google API error {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Google API connection error: {exc.reason}") from exc


_LOG_SECRET_KEYS = {"authorization", "access_token", "refresh_token", "token", "secret", "client_secret", "developer_token", "google_key", "googlekey", "key", "api_key", "password", "credential"}


def _redact_log_payload(value, depth=0):
    if depth > 8:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lowered = str(key).lower().replace("-", "_")
            clean[str(key)[:120]] = "[REDACTED]" if any(secret in lowered for secret in _LOG_SECRET_KEYS) else _redact_log_payload(item, depth + 1)
        return clean
    if isinstance(value, list):
        return [_redact_log_payload(item, depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return value[:2000]
    return value


def create_log(company, connection, tool, action, status, message="", request_payload=None, response_payload=None, external_id=None, user=None):
    return IntegrationLog.objects.create(
        id_company=company,
        connection=connection,
        tool=tool,
        action=(action or "")[:160],
        status=status,
        message=(message or "")[:2000],
        request_payload=_redact_log_payload(request_payload or {}),
        response_payload=_redact_log_payload(response_payload or {}),
        external_id=(str(external_id)[:255] if external_id else None),
        created_by=user,
        finished_at=timezone.now(),
    )


def build_google_authorization_url(request, connection, company_slug=None):
    client_id = get_google_client_id(connection)
    if not client_id or not get_google_client_secret(connection):
        raise RuntimeError("Google OAuth credentials are missing for this company. Configure them from Integrations > Connections > Configure Google App.")

    state = uuid.uuid4().hex
    request.session["google_oauth_state"] = state
    request.session["google_oauth_company_slug"] = company_slug or ""
    request.session["google_oauth_connection_id"] = connection.pk

    redirect_uri = request.build_absolute_uri(reverse("integrations:google_callback"))
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "false",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(request, connection, code):
    client_id = get_google_client_id(connection)
    client_secret = get_google_client_secret(connection)
    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth credentials are missing for this company. Configure Google App before connecting.")

    redirect_uri = request.build_absolute_uri(reverse("integrations:google_callback"))
    payload = urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode("utf-8")
    request_obj = Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request_obj, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Google OAuth token exchange failed: {raw}") from exc


def fetch_google_userinfo(access_token):
    return _json_request(GOOGLE_USERINFO_URL, access_token=access_token)


def apply_token_response(connection, token_response, user=None):
    now = timezone.now()
    expires_in = int(token_response.get("expires_in") or 3600)
    access_token = token_response.get("access_token", "")
    refresh_token = token_response.get("refresh_token")

    connection.set_token_data(token_response)
    if refresh_token:
        connection.set_refresh_token(refresh_token)

    connection.scopes = (token_response.get("scope") or "").split()
    connection.access_token_expires_at = now + timedelta(seconds=max(expires_in - 60, 60))
    connection.status = STATUS_CONNECTED
    connection.last_error = ""
    if user:
        connection.updated_by = user
    connection.save()

    return access_token


def refresh_access_token(connection):
    refresh_token = connection.get_refresh_token()
    if not refresh_token:
        connection.status = STATUS_EXPIRED
        connection.last_error = "Refresh token is missing. Reconnect Google."
        connection.save(update_fields=["status", "last_error", "updated_at"])
        raise RuntimeError("Refresh token is missing. Reconnect Google.")

    payload = urlencode({
        "client_id": get_google_client_id(connection),
        "client_secret": get_google_client_secret(connection),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    request_obj = Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request_obj, timeout=45) as response:
            token_response = json.loads(response.read().decode("utf-8"))
            current = connection.get_token_data()
            current.update(token_response)
            if refresh_token:
                current["refresh_token"] = refresh_token
            return apply_token_response(connection, current)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        connection.status = STATUS_ERROR
        connection.last_error = raw
        connection.save(update_fields=["status", "last_error", "updated_at"])
        raise RuntimeError(f"Unable to refresh Google access token: {raw}") from exc


def get_valid_access_token(connection):
    token_data = connection.get_token_data()
    access_token = token_data.get("access_token", "")
    if not access_token or connection.token_is_expired:
        return refresh_access_token(connection)
    return access_token


def disconnect_google(connection, user=None):
    token_data = connection.get_token_data()
    token = token_data.get("access_token") or connection.get_refresh_token()
    if token:
        try:
            request_obj = Request(f"{GOOGLE_REVOKE_URL}?{urlencode({'token': token})}", method="POST")
            urlopen(request_obj, timeout=25).read()
        except Exception as exc:
            create_log(connection.id_company, connection, TOOL_OAUTH, "Token revoke", LOG_ERROR, str(exc), user=user)
    connection.status = STATUS_REVOKED
    connection.last_error = "Disconnected from CRM."
    connection.save(update_fields=["status", "last_error", "updated_at"])
    create_log(connection.id_company, connection, TOOL_OAUTH, "Google disconnected", LOG_SUCCESS, "Connection revoked locally.", user=user)


def create_google_calendar_event(calendar_event, user=None):
    connection = calendar_event.connection
    access_token = get_valid_access_token(connection)
    calendar_id = connection.calendar_id or "primary"
    attendees = []
    for email in (calendar_event.attendees or "").replace(";", ",").split(","):
        email = email.strip()
        if email:
            attendees.append({"email": email})
    payload = {
        "summary": calendar_event.title,
        "description": calendar_event.description or "Created from CRM CEO MARKETING.",
        "start": {"dateTime": calendar_event.start_at.isoformat()},
        "end": {"dateTime": calendar_event.end_at.isoformat()},
        "attendees": attendees,
        "conferenceData": {
            "createRequest": {
                "requestId": f"crm-{calendar_event.id_calendar_event}-{uuid.uuid4().hex[:10]}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    url = GOOGLE_CALENDAR_EVENTS_URL.format(calendar_id=calendar_id) + "?conferenceDataVersion=1&sendUpdates=all"
    try:
        response = _json_request(url, method="POST", access_token=access_token, payload=payload)
        calendar_event.external_event_id = response.get("id")
        calendar_event.meet_url = (response.get("hangoutLink") or "")[:700]
        calendar_event.calendar_html_link = (response.get("htmlLink") or "")[:700]
        calendar_event.status = "synced"
        calendar_event.error_message = ""
        calendar_event.save()
        connection.last_sync_at = timezone.now()
        connection.save(update_fields=["last_sync_at", "updated_at"])
        create_log(connection.id_company, connection, TOOL_CALENDAR, "Create Calendar / Meet event", LOG_SUCCESS, "Event created successfully.", request_payload=payload, response_payload=response, external_id=calendar_event.external_event_id, user=user)
        return response
    except Exception as exc:
        calendar_event.status = "error"
        calendar_event.error_message = str(exc)
        calendar_event.save(update_fields=["status", "error_message", "updated_at"])
        create_log(connection.id_company, connection, TOOL_CALENDAR, "Create Calendar / Meet event", LOG_ERROR, str(exc), request_payload=payload, user=user)
        raise


def upload_file_to_drive(upload, user=None):
    connection = upload.connection
    access_token = get_valid_access_token(connection)
    metadata = {"name": upload.title or os.path.basename(upload.file.name)}
    if connection.drive_folder_id:
        metadata["parents"] = [connection.drive_folder_id]
    content_type = mimetypes.guess_type(upload.file.name)[0] or "application/octet-stream"
    boundary = f"crmBoundary{uuid.uuid4().hex}"
    upload.file.open("rb")
    file_bytes = upload.file.read()
    upload.file.close()
    body = b"\r\n".join([
        f"--{boundary}".encode(),
        b"Content-Type: application/json; charset=UTF-8",
        b"",
        json.dumps(metadata).encode(),
        f"--{boundary}".encode(),
        f"Content-Type: {content_type}".encode(),
        b"",
        file_bytes,
        f"--{boundary}--".encode(),
    ])
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    }
    request = Request(GOOGLE_DRIVE_UPLOAD_URL, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
        upload.external_file_id = data.get("id")
        upload.drive_url = data.get("webViewLink")
        upload.status = "completed"
        upload.error_message = ""
        upload.save(update_fields=["external_file_id", "drive_url", "status", "error_message"])
        connection.last_sync_at = timezone.now()
        connection.save(update_fields=["last_sync_at", "updated_at"])
        create_log(connection.id_company, connection, TOOL_DRIVE, "Upload file to Drive", LOG_SUCCESS, "File uploaded successfully.", response_payload=data, external_id=upload.external_file_id, user=user)
        return data
    except Exception as exc:
        upload.status = "error"
        upload.error_message = str(exc)
        upload.save(update_fields=["status", "error_message"])
        create_log(connection.id_company, connection, TOOL_DRIVE, "Upload file to Drive", LOG_ERROR, str(exc), user=user)
        raise


def _model_rows_for_export(company, export_source):
    rows = []
    if export_source == "clients":
        Model = apps.get_model("clients", "Client")
        rows.append(["Name", "Email", "Phone", "Status", "Created"])
        for obj in Model.objects.filter(id_company=company).order_by("-created_at")[:500]:
            rows.append([getattr(obj, "name", "") or str(obj), getattr(obj, "email", "") or "", getattr(obj, "phone", "") or "", getattr(obj, "status", "") or "", str(getattr(obj, "created_at", "") or "")])
    elif export_source == "leads":
        Model = apps.get_model("leads", "Lead")
        rows.append(["Lead", "Email", "Phone", "Status", "Created"])
        for obj in Model.objects.filter(id_company=company).order_by("-created_at")[:500]:
            rows.append([getattr(obj, "name", "") or getattr(obj, "full_name", "") or str(obj), getattr(obj, "email", "") or "", getattr(obj, "phone", "") or "", getattr(obj, "status", "") or "", str(getattr(obj, "created_at", "") or "")])
    elif export_source == "invoices":
        Model = apps.get_model("invoices", "Invoice")
        rows.append(["Invoice", "Client", "Status", "Total", "Paid", "Balance"])
        for obj in Model.objects.filter(id_company=company).order_by("-created_at")[:500]:
            rows.append([getattr(obj, "invoice_number", "") or str(obj.pk), str(getattr(obj, "client", "") or getattr(obj, "id_client", "") or ""), getattr(obj, "status", "") or "", str(getattr(obj, "total", "") or ""), str(getattr(obj, "paid_amount", "") or ""), str(getattr(obj, "balance_due", "") or "")])
    elif export_source == "payments":
        Model = apps.get_model("payments", "Payment")
        rows.append(["Payment", "Client", "Status", "Amount", "Date"])
        for obj in Model.objects.filter(id_company=company).order_by("-created_at")[:500]:
            rows.append([getattr(obj, "payment_number", "") or getattr(obj, "reference", "") or str(obj.pk), str(getattr(obj, "client", "") or getattr(obj, "id_client", "") or ""), getattr(obj, "status", "") or "", str(getattr(obj, "amount", "") or ""), str(getattr(obj, "payment_date", "") or getattr(obj, "created_at", "") or "")])
    elif export_source == "suppliers":
        Model = apps.get_model("suppliers", "Supplier")
        rows.append(["Supplier", "Phone", "Email", "Status", "Locality"])
        for obj in Model.objects.filter(id_company=company).order_by("name")[:500]:
            rows.append([getattr(obj, "name", "") or str(obj), getattr(obj, "phone", "") or "", getattr(obj, "email", "") or "", getattr(obj, "status", "") or "", getattr(obj, "locality", "") or getattr(obj, "city", "") or ""])
    elif export_source == "supplier_purchases":
        Model = apps.get_model("suppliers", "SupplierPurchase")
        rows.append(["Purchase", "Supplier", "Status", "Total", "Paid", "Balance"])
        for obj in Model.objects.filter(id_company=company).order_by("-purchase_date")[:500]:
            rows.append([getattr(obj, "purchase_number", "") or str(obj.pk), str(getattr(obj, "supplier", "") or ""), getattr(obj, "status", "") or "", str(getattr(obj, "total", "") or ""), str(getattr(obj, "paid_amount", "") or ""), str(getattr(obj, "balance_due", "") or "")])
    elif export_source == "analytics":
        Snapshot = apps.get_model("integrations", "GoogleAnalyticsSnapshot")
        rows.append(["Property", "Date From", "Date To", "Active Users", "Sessions", "Conversions", "Revenue"])
        for obj in Snapshot.objects.filter(id_company=company).order_by("-created_at")[:200]:
            rows.append([obj.property_id, str(obj.date_from), str(obj.date_to), obj.active_users, obj.sessions, obj.conversions, str(obj.total_revenue)])
    elif export_source == "ads":
        Snapshot = apps.get_model("integrations", "GoogleAdsSnapshot")
        rows.append(["Customer", "Date From", "Date To", "Cost", "Clicks", "Impressions", "Conversions"])
        for obj in Snapshot.objects.filter(id_company=company).order_by("-created_at")[:200]:
            rows.append([obj.customer_id, str(obj.date_from), str(obj.date_to), str(obj.cost), obj.clicks, obj.impressions, str(obj.conversions)])
    elif export_source == "google_ads_leads":
        Lead = apps.get_model("integrations", "GoogleAdsLead")
        rows.append(["Source", "Name", "Phone", "Email", "Service", "Status", "Received", "CRM Lead"])
        for obj in Lead.objects.filter(id_company=company).order_by("-received_at", "-created_at")[:500]:
            rows.append([obj.get_source_display(), obj.customer_name or "", obj.phone or "", obj.email or "", obj.service_interest or obj.category_id or "", obj.crm_status, str(obj.received_at or obj.created_at), str(obj.crm_lead_id or "")])
    if len(rows) == 1:
        rows.append(["No data found"])
    return rows


def append_rows_to_sheet(sheet_export, user=None):
    connection = sheet_export.connection
    access_token = get_valid_access_token(connection)
    rows = _model_rows_for_export(sheet_export.id_company, sheet_export.export_source)
    range_name = f"{sheet_export.sheet_name}!A1"
    payload = {"values": rows}
    url = GOOGLE_SHEETS_APPEND_URL.format(
        spreadsheet_id=sheet_export.spreadsheet_id,
        range_name=range_name,
    ) + "?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
    try:
        response = _json_request(url, method="POST", access_token=access_token, payload=payload)
        sheet_export.rows_exported = max(len(rows) - 1, 0)
        sheet_export.status = "completed"
        sheet_export.error_message = ""
        sheet_export.save(update_fields=["rows_exported", "status", "error_message"])
        connection.last_sync_at = timezone.now()
        connection.save(update_fields=["last_sync_at", "updated_at"])
        create_log(connection.id_company, connection, TOOL_SHEETS, "Export CRM data to Google Sheets", LOG_SUCCESS, "Rows appended successfully.", request_payload={"source": sheet_export.export_source, "rows": len(rows)}, response_payload=response, user=user)
        return response
    except Exception as exc:
        sheet_export.status = "error"
        sheet_export.error_message = str(exc)
        sheet_export.save(update_fields=["status", "error_message"])
        create_log(connection.id_company, connection, TOOL_SHEETS, "Export CRM data to Google Sheets", LOG_ERROR, str(exc), request_payload={"source": sheet_export.export_source}, user=user)
        raise


def run_analytics_report(connection, date_from, date_to, user=None):
    """Run an accurate GA4 summary plus a daily series for CRM charts.

    The first request returns period totals. The second request adds the date
    dimension, allowing the UI to render local charts without a third-party
    JavaScript dependency. Both responses are stored in the existing JSON
    snapshot field, so no migration is required.
    """
    access_token = get_valid_access_token(connection)
    property_id = (connection.analytics_property_id or "").strip()
    if not property_id:
        raise RuntimeError("Analytics Property ID is missing in integration settings.")

    metrics = [
        {"name": "activeUsers"},
        {"name": "sessions"},
        {"name": "conversions"},
        {"name": "totalRevenue"},
    ]
    summary_payload = {
        "dateRanges": [{"startDate": str(date_from), "endDate": str(date_to)}],
        "metrics": metrics,
    }
    series_payload = {
        "dateRanges": [{"startDate": str(date_from), "endDate": str(date_to)}],
        "dimensions": [{"name": "date"}],
        "metrics": metrics,
        "orderBys": [{"dimension": {"dimensionName": "date"}}],
        "limit": "366",
    }
    url = GOOGLE_ANALYTICS_RUN_REPORT_URL.format(property_id=property_id)

    try:
        summary_response = _json_request(
            url,
            method="POST",
            access_token=access_token,
            payload=summary_payload,
        )
        series_response = _json_request(
            url,
            method="POST",
            access_token=access_token,
            payload=series_payload,
        )

        values = ["0", "0", "0", "0"]
        summary_rows = summary_response.get("rows") or []
        if summary_rows:
            metric_values = summary_rows[0].get("metricValues", [])
            for index, metric in enumerate(metric_values[:4]):
                values[index] = metric.get("value", "0")

        snapshot = GoogleAnalyticsSnapshot.objects.create(
            id_company=connection.id_company,
            connection=connection,
            property_id=property_id,
            date_from=date_from,
            date_to=date_to,
            active_users=int(float(values[0] or 0)),
            sessions=int(float(values[1] or 0)),
            conversions=int(float(values[2] or 0)),
            total_revenue=Decimal(str(values[3] or "0")),
            raw_response={
                "summary": summary_response,
                "series": series_response,
            },
            created_by=user,
        )
        connection.last_sync_at = timezone.now()
        connection.save(update_fields=["last_sync_at", "updated_at"])
        create_log(
            connection.id_company,
            connection,
            TOOL_ANALYTICS,
            "Run GA4 report",
            LOG_SUCCESS,
            "Analytics summary and chart series saved.",
            request_payload={"summary": summary_payload, "series": series_payload},
            response_payload={
                "snapshot_id": snapshot.id_snapshot,
                "series_rows": len(series_response.get("rows") or []),
            },
            external_id=str(snapshot.id_snapshot),
            user=user,
        )
        return snapshot
    except Exception as exc:
        create_log(
            connection.id_company,
            connection,
            TOOL_ANALYTICS,
            "Run GA4 report",
            LOG_ERROR,
            str(exc),
            request_payload={"summary": summary_payload, "series": series_payload},
            user=user,
        )
        raise


def run_ads_report(connection, date_from, date_to, user=None):
    access_token = get_valid_access_token(connection)
    customer_id = (connection.ads_customer_id or "").replace("-", "")
    if not customer_id:
        raise RuntimeError("Google Ads Customer ID is missing in integration settings.")
    developer_token = connection.get_developer_token() or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    if not developer_token:
        raise RuntimeError("Google Ads developer token is missing.")
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          metrics.cost_micros,
          metrics.clicks,
          metrics.impressions,
          metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY metrics.cost_micros DESC
        LIMIT 100
    """
    headers = {"developer-token": developer_token}
    login_customer_id = (connection.ads_login_customer_id or "").replace("-", "")
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id
    payload = {"query": " ".join(query.split())}
    url = GOOGLE_ADS_SEARCH_STREAM_URL.format(customer_id=customer_id)
    try:
        response = _json_request(url, method="POST", access_token=access_token, payload=payload, headers=headers)
        raw_rows = []
        if isinstance(response, list):
            for chunk in response:
                raw_rows.extend(chunk.get("results", []))
        else:
            raw_rows = response.get("results", [])
        cost = Decimal("0.00")
        clicks = 0
        impressions = 0
        conversions = Decimal("0.00")
        campaign_rows = []
        for row in raw_rows:
            campaign = row.get("campaign", {})
            metrics = row.get("metrics", {})
            micros = Decimal(str(metrics.get("costMicros") or 0))
            row_cost = micros / Decimal("1000000")
            row_clicks = int(metrics.get("clicks") or 0)
            row_impressions = int(metrics.get("impressions") or 0)
            row_conversions = Decimal(str(metrics.get("conversions") or 0))
            cost += row_cost
            clicks += row_clicks
            impressions += row_impressions
            conversions += row_conversions
            campaign_rows.append({
                "id": campaign.get("id"),
                "name": campaign.get("name"),
                "status": campaign.get("status"),
                "cost": str(row_cost.quantize(Decimal("0.01"))),
                "clicks": row_clicks,
                "impressions": row_impressions,
                "conversions": str(row_conversions),
            })
        snapshot = GoogleAdsSnapshot.objects.create(
            id_company=connection.id_company,
            connection=connection,
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
            cost=cost.quantize(Decimal("0.01")),
            clicks=clicks,
            impressions=impressions,
            conversions=conversions,
            campaign_rows=campaign_rows,
            raw_response={"response": response},
            created_by=user,
        )
        connection.last_sync_at = timezone.now()
        connection.save(update_fields=["last_sync_at", "updated_at"])
        create_log(connection.id_company, connection, TOOL_ADS, "Run Google Ads report", LOG_SUCCESS, "Google Ads report saved.", request_payload=payload, response_payload={"rows": campaign_rows[:10]}, external_id=str(snapshot.id_snapshot), user=user)
        return snapshot
    except Exception as exc:
        create_log(connection.id_company, connection, TOOL_ADS, "Run Google Ads report", LOG_ERROR, str(exc), request_payload=payload, user=user)
        raise


def _normalize_ads_customer_id(value):
    return (value or "").replace("-", "").replace(" ", "").strip()


def _ads_headers(connection):
    developer_token = connection.get_developer_token() or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    if not developer_token:
        raise RuntimeError("Google Ads Developer Token is missing. Add it encrypted in Integrations > Connections > Settings.")
    headers = {"developer-token": developer_token}
    login_customer_id = _normalize_ads_customer_id(connection.ads_login_customer_id)
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id
    return headers


def _ads_search_stream(connection, query):
    access_token = get_valid_access_token(connection)
    customer_id = _normalize_ads_customer_id(connection.ads_customer_id)
    if not customer_id:
        raise RuntimeError("Google Ads Customer ID is missing in integration settings.")
    payload = {"query": " ".join(query.split())}
    url = GOOGLE_ADS_SEARCH_STREAM_URL.format(customer_id=customer_id)
    response = _json_request(url, method="POST", access_token=access_token, payload=payload, headers=_ads_headers(connection))
    rows = []
    if isinstance(response, list):
        for chunk in response:
            rows.extend(chunk.get("results", []))
    else:
        rows = response.get("results", [])
    return rows, response


def _safe_get(data, *paths):
    for path in paths:
        current = data or {}
        ok = True
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current.get(part)
            else:
                ok = False
                break
        if ok and current not in (None, "", []):
            return current
    return ""


def _lead_received_at(value):
    if not value:
        return timezone.now()
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    value = str(value).strip()
    parsed = parse_datetime(value.replace(" ", "T", 1))
    if parsed:
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return timezone.make_aware(parsed)
    except Exception:
        return timezone.now()


def _column_value_map(user_column_data):
    mapped = {}
    for item in user_column_data or []:
        column_id = (item.get("column_id") or item.get("columnId") or item.get("column_name") or item.get("columnName") or "").upper()
        value = item.get("string_value") or item.get("stringValue") or item.get("value") or ""
        if column_id:
            mapped[column_id] = value
    return mapped


def _create_or_update_crm_lead(ads_lead, user=None):
    Lead = apps.get_model("leads", "Lead")
    name = ads_lead.customer_name or ads_lead.email or ads_lead.phone or "Google Lead"
    notes = [
        f"Source: {ads_lead.get_source_display()}",
        f"Google Lead ID: {ads_lead.external_lead_id or ads_lead.external_resource_name or ''}",
    ]
    if ads_lead.service_interest or ads_lead.category_id:
        notes.append(f"Service: {ads_lead.service_interest or ads_lead.category_id}")
    if ads_lead.message:
        notes.append(f"Message: {ads_lead.message}")
    if ads_lead.conversation_text:
        notes.append(f"Conversation: {ads_lead.conversation_text}")
    if ads_lead.crm_lead_id:
        lead = ads_lead.crm_lead
        changed = False
        for attr, value in [("name", name), ("phone", ads_lead.phone), ("email", ads_lead.email), ("address", ads_lead.address)]:
            if value and not getattr(lead, attr, None):
                setattr(lead, attr, value)
                changed = True
        if changed:
            lead.save()
        return lead
    existing = None
    if ads_lead.phone:
        existing = Lead.objects.filter(id_company=ads_lead.id_company, phone=ads_lead.phone).order_by("-created_at").first()
    if not existing and ads_lead.email:
        existing = Lead.objects.filter(id_company=ads_lead.id_company, email=ads_lead.email).order_by("-created_at").first()
    if existing:
        ads_lead.crm_lead = existing
        ads_lead.save(update_fields=["crm_lead", "updated_at"])
        return existing
    lead = Lead.objects.create(
        id_company=ads_lead.id_company,
        name=name,
        phone=ads_lead.phone or None,
        email=ads_lead.email or None,
        source="Google Ads / Google Guaranteed",
        address=ads_lead.address or None,
        status="new",
        notes="\n".join(notes),
    )
    ads_lead.crm_lead = lead
    ads_lead.save(update_fields=["crm_lead", "updated_at"])
    return lead


def _log_default_reply(ads_lead, user=None):
    connection = ads_lead.connection
    if not connection or not connection.auto_reply_enabled or not connection.auto_reply_message:
        return None
    if ads_lead.replies.exists():
        return None
    reply = GoogleAdsLeadReply.objects.create(
        id_company=ads_lead.id_company,
        ads_lead=ads_lead,
        channel=REPLY_CHANNEL_CRM_NOTE,
        status=REPLY_STATUS_LOGGED,
        subject="Default Google lead follow-up",
        message=connection.auto_reply_message,
        created_by=user,
    )
    ads_lead.last_reply_message = reply.message
    ads_lead.last_reply_at = timezone.now()
    ads_lead.save(update_fields=["last_reply_message", "last_reply_at", "updated_at"])
    return reply


def process_google_ads_webhook(company, payload, connection=None, user=None):
    connection = connection or GoogleIntegrationConnection.objects.filter(id_company=company, provider="google").first()
    expected_key = connection.get_lead_webhook_key() if connection else ""
    received_key = payload.get("google_key") or payload.get("googleKey") or payload.get("key") or ""
    if not expected_key:
        raise PermissionError("Webhook is not configured.")
    if not hmac.compare_digest(str(received_key), str(expected_key)):
        raise PermissionError("Invalid webhook authentication.")
    payload = dict(payload)
    for secret_key in ("google_key", "googleKey", "key"):
        payload.pop(secret_key, None)
    columns = _column_value_map(payload.get("user_column_data") or payload.get("userColumnData") or [])
    full_name = columns.get("FULL_NAME") or " ".join([columns.get("FIRST_NAME", ""), columns.get("LAST_NAME", "")]).strip()
    email = columns.get("EMAIL") or columns.get("WORK_EMAIL")
    phone = columns.get("PHONE_NUMBER") or columns.get("WORK_PHONE")
    address = columns.get("STREET_ADDRESS")
    city = columns.get("CITY")
    region = columns.get("REGION")
    postal_code = columns.get("POSTAL_CODE")
    country = columns.get("COUNTRY")
    service = columns.get("SERVICE") or columns.get("PRODUCT") or columns.get("CATEGORY") or columns.get("OFFER")
    message_parts = []
    for key, value in columns.items():
        if key not in {"FULL_NAME", "FIRST_NAME", "LAST_NAME", "EMAIL", "WORK_EMAIL", "PHONE_NUMBER", "WORK_PHONE", "STREET_ADDRESS", "CITY", "REGION", "POSTAL_CODE", "COUNTRY"} and value:
            message_parts.append(f"{key}: {value}")
    external_id = str(payload.get("lead_id") or payload.get("leadId") or payload.get("gcl_id") or payload.get("gclId") or uuid.uuid4().hex)
    ads_lead, created = GoogleAdsLead.objects.update_or_create(
        id_company=company,
        source="google_ads_webhook",
        external_lead_id=external_id,
        defaults={
            "connection": connection,
            "customer_id": _normalize_ads_customer_id(getattr(connection, "ads_customer_id", "")),
            "campaign_id": str(payload.get("campaign_id") or payload.get("campaignId") or ""),
            "adgroup_id": str(payload.get("adgroup_id") or payload.get("adgroupId") or ""),
            "form_id": str(payload.get("form_id") or payload.get("formId") or ""),
            "gcl_id": payload.get("gcl_id") or payload.get("gclId") or "",
            "lead_type": payload.get("lead_source") or payload.get("leadSource") or "LEAD_FORM",
            "lead_status": payload.get("lead_stage") or payload.get("leadStage") or "NEW",
            "customer_name": full_name or None,
            "phone": phone or None,
            "email": email or None,
            "address": address or None,
            "city": city or None,
            "state": region or None,
            "postal_code": postal_code or None,
            "country": country or None,
            "service_interest": service or None,
            "message": "\n".join(message_parts),
            "is_test": bool(payload.get("is_test") or payload.get("isTest")),
            "received_at": _lead_received_at(payload.get("lead_submit_time") or payload.get("leadSubmitTime")),
            "raw_payload": payload,
            "synced_at": timezone.now(),
            "updated_by": user,
        },
    )
    if created:
        ads_lead.created_by = user
        ads_lead.save(update_fields=["created_by"])
    if connection and connection.auto_create_crm_leads:
        _create_or_update_crm_lead(ads_lead, user=user)
    if created:
        _log_default_reply(ads_lead, user=user)
    create_log(company, connection, TOOL_ADS_LEADS, "Google Ads lead webhook received", LOG_SUCCESS, "Lead received from Google Ads webhook.", request_payload={"lead_id": external_id}, external_id=external_id, user=user)
    return ads_lead, created


def sync_local_services_leads(connection, date_from, date_to, user=None):
    query = f"""
        SELECT
          local_services_lead.resource_name,
          local_services_lead.id,
          local_services_lead.category_id,
          local_services_lead.contact_details,
          local_services_lead.creation_date_time,
          local_services_lead.lead_type,
          local_services_lead.lead_status,
          local_services_lead.lead_charged,
          local_services_lead.lead_feedback_submitted
        FROM local_services_lead
        WHERE local_services_lead.creation_date_time >= '{date_from} 00:00:00'
          AND local_services_lead.creation_date_time <= '{date_to} 23:59:59'
        ORDER BY local_services_lead.creation_date_time DESC
        LIMIT 200
    """
    rows, response = _ads_search_stream(connection, query)
    created_count = 0
    updated_count = 0
    for row in rows:
        data = row.get("localServicesLead", {}) or row.get("local_services_lead", {}) or {}
        contact = data.get("contactDetails") or data.get("contact_details") or {}
        name = _safe_get(contact, "consumerName", "customerName", "name", "fullName")
        phone = _safe_get(contact, "phoneNumber", "consumerPhoneNumber", "phone")
        email = _safe_get(contact, "email", "consumerEmail")
        external_resource = data.get("resourceName") or data.get("resource_name") or ""
        external_id = str(data.get("id") or external_resource.rsplit("/", 1)[-1] or uuid.uuid4().hex)
        ads_lead, created = GoogleAdsLead.objects.update_or_create(
            id_company=connection.id_company,
            source="google_local_services",
            external_lead_id=external_id,
            defaults={
                "connection": connection,
                "customer_id": _normalize_ads_customer_id(connection.ads_customer_id),
                "external_resource_name": external_resource,
                "category_id": data.get("categoryId") or data.get("category_id") or "",
                "lead_type": data.get("leadType") or data.get("lead_type") or "",
                "lead_status": data.get("leadStatus") or data.get("lead_status") or "",
                "customer_name": name or None,
                "phone": phone or None,
                "email": email or None,
                "message": "",
                "lead_charged": bool(data.get("leadCharged") or data.get("lead_charged")),
                "lead_feedback_submitted": bool(data.get("leadFeedbackSubmitted") or data.get("lead_feedback_submitted")),
                "received_at": _lead_received_at(data.get("creationDateTime") or data.get("creation_date_time")),
                "raw_payload": row,
                "synced_at": timezone.now(),
                "updated_by": user,
            },
        )
        if created:
            ads_lead.created_by = user
            ads_lead.save(update_fields=["created_by"])
            created_count += 1
        else:
            updated_count += 1
        if connection.auto_create_crm_leads_from_lsa:
            _create_or_update_crm_lead(ads_lead, user=user)
    sync_local_services_conversations(connection, date_from, date_to, user=user)
    connection.last_ads_lead_sync_at = timezone.now()
    connection.last_sync_at = timezone.now()
    connection.save(update_fields=["last_ads_lead_sync_at", "last_sync_at", "updated_at"])
    create_log(connection.id_company, connection, TOOL_ADS_LEADS, "Sync Google Guaranteed / LSA leads", LOG_SUCCESS, f"{created_count} created, {updated_count} updated.", request_payload={"date_from": str(date_from), "date_to": str(date_to)}, response_payload={"rows": len(rows)}, user=user)
    return {"created": created_count, "updated": updated_count, "rows": len(rows), "raw": response}


def sync_local_services_conversations(connection, date_from, date_to, user=None):
    query = f"""
        SELECT
          local_services_lead_conversation.resource_name,
          local_services_lead_conversation.id,
          local_services_lead_conversation.lead,
          local_services_lead_conversation.conversation_channel,
          local_services_lead_conversation.event_date_time,
          local_services_lead_conversation.participant_type,
          local_services_lead_conversation.message_details.text,
          local_services_lead_conversation.message_details.attachment_urls,
          local_services_lead_conversation.phone_call_details.call_duration_millis,
          local_services_lead_conversation.phone_call_details.call_recording_url
        FROM local_services_lead_conversation
        WHERE local_services_lead_conversation.event_date_time >= '{date_from} 00:00:00'
          AND local_services_lead_conversation.event_date_time <= '{date_to} 23:59:59'
        ORDER BY local_services_lead_conversation.event_date_time DESC
        LIMIT 500
    """
    try:
        rows, response = _ads_search_stream(connection, query)
    except Exception as exc:
        create_log(connection.id_company, connection, TOOL_ADS_LEADS, "Sync Google Guaranteed conversations", LOG_ERROR, str(exc), user=user)
        return {"rows": 0, "error": str(exc)}
    by_lead = {}
    for row in rows:
        conv = row.get("localServicesLeadConversation", {}) or row.get("local_services_lead_conversation", {}) or {}
        lead_resource = conv.get("lead") or ""
        if not lead_resource:
            continue
        by_lead.setdefault(lead_resource, []).append(conv)
    for resource, conversations in by_lead.items():
        ads_lead = GoogleAdsLead.objects.filter(id_company=connection.id_company, external_resource_name=resource).first()
        if not ads_lead:
            continue
        lines = []
        for conv in sorted(conversations, key=lambda c: c.get("eventDateTime") or c.get("event_date_time") or ""):
            participant = conv.get("participantType") or conv.get("participant_type") or ""
            channel = conv.get("conversationChannel") or conv.get("conversation_channel") or ""
            text = _safe_get(conv, "messageDetails.text", "message_details.text")
            duration = _safe_get(conv, "phoneCallDetails.callDurationMillis", "phone_call_details.call_duration_millis")
            when = conv.get("eventDateTime") or conv.get("event_date_time") or ""
            if text:
                lines.append(f"[{when}] {participant}/{channel}: {text}")
            elif duration:
                lines.append(f"[{when}] {participant}/{channel}: Phone call duration {duration} ms")
        ads_lead.raw_conversations = conversations
        ads_lead.conversation_text = "\n".join(lines)
        ads_lead.save(update_fields=["raw_conversations", "conversation_text", "updated_at"])
    return {"rows": len(rows), "raw": response}


def sync_google_lead_form_submissions(connection, date_from, date_to, user=None):
    query = f"""
        SELECT
          lead_form_submission_data.resource_name,
          lead_form_submission_data.id,
          lead_form_submission_data.asset,
          lead_form_submission_data.campaign,
          lead_form_submission_data.ad_group,
          lead_form_submission_data.gclid,
          lead_form_submission_data.submission_date_time,
          lead_form_submission_data.custom_lead_form_submission_fields
        FROM lead_form_submission_data
        WHERE lead_form_submission_data.submission_date_time >= '{date_from} 00:00:00'
          AND lead_form_submission_data.submission_date_time <= '{date_to} 23:59:59'
        ORDER BY lead_form_submission_data.submission_date_time DESC
        LIMIT 200
    """
    rows, response = _ads_search_stream(connection, query)
    created_count = 0
    updated_count = 0
    for row in rows:
        data = row.get("leadFormSubmissionData", {}) or row.get("lead_form_submission_data", {}) or {}
        fields = data.get("customLeadFormSubmissionFields") or data.get("custom_lead_form_submission_fields") or []
        columns = {}
        for item in fields:
            key = (item.get("fieldName") or item.get("field_name") or item.get("columnName") or item.get("column_name") or "").upper()
            value = item.get("fieldValue") or item.get("field_value") or item.get("stringValue") or item.get("string_value") or ""
            if key:
                columns[key] = value
        external_resource = data.get("resourceName") or data.get("resource_name") or ""
        external_id = str(data.get("id") or external_resource.rsplit("/", 1)[-1] or uuid.uuid4().hex)
        ads_lead, created = GoogleAdsLead.objects.update_or_create(
            id_company=connection.id_company,
            source="google_lead_form_api",
            external_lead_id=external_id,
            defaults={
                "connection": connection,
                "customer_id": _normalize_ads_customer_id(connection.ads_customer_id),
                "external_resource_name": external_resource,
                "campaign_id": str(data.get("campaign") or "").rsplit("/", 1)[-1],
                "adgroup_id": str(data.get("adGroup") or data.get("ad_group") or "").rsplit("/", 1)[-1],
                "form_id": str(data.get("asset") or "").rsplit("/", 1)[-1],
                "gcl_id": data.get("gclid") or "",
                "lead_type": "LEAD_FORM",
                "lead_status": "NEW",
                "customer_name": columns.get("FULL_NAME") or columns.get("NAME") or None,
                "phone": columns.get("PHONE_NUMBER") or columns.get("PHONE") or None,
                "email": columns.get("EMAIL") or columns.get("WORK_EMAIL") or None,
                "service_interest": columns.get("SERVICE") or columns.get("PRODUCT") or columns.get("CATEGORY") or None,
                "message": "\n".join([f"{k}: {v}" for k, v in columns.items() if v]),
                "received_at": _lead_received_at(data.get("submissionDateTime") or data.get("submission_date_time")),
                "raw_payload": row,
                "synced_at": timezone.now(),
                "updated_by": user,
            },
        )
        if created:
            ads_lead.created_by = user
            ads_lead.save(update_fields=["created_by"])
            created_count += 1
        else:
            updated_count += 1
        if connection.auto_create_crm_leads:
            _create_or_update_crm_lead(ads_lead, user=user)
    create_log(connection.id_company, connection, TOOL_ADS_LEADS, "Sync Google Ads Lead Form submissions", LOG_SUCCESS, f"{created_count} created, {updated_count} updated.", request_payload={"date_from": str(date_from), "date_to": str(date_to)}, response_payload={"rows": len(rows)}, user=user)
    return {"created": created_count, "updated": updated_count, "rows": len(rows), "raw": response}


def append_lsa_lead_conversation(ads_lead, message, user=None):
    if not ads_lead.connection:
        raise RuntimeError("Google connection is required to send a Google Guaranteed message.")
    if ads_lead.source != "google_local_services" or not ads_lead.external_resource_name:
        raise RuntimeError("Google Message can only be sent for Google Guaranteed / Local Services leads.")
    access_token = get_valid_access_token(ads_lead.connection)
    customer_id = _normalize_ads_customer_id(ads_lead.connection.ads_customer_id or ads_lead.customer_id)
    headers = _ads_headers(ads_lead.connection)
    payload = {
        "conversations": [
            {
                "localServicesLead": ads_lead.external_resource_name,
                "text": message,
            }
        ]
    }
    url = GOOGLE_LSA_APPEND_CONVERSATION_URL.format(customer_id=customer_id)
    response = _json_request(url, method="POST", access_token=access_token, headers=headers, payload=payload, timeout=60)
    create_log(ads_lead.id_company, ads_lead.connection, TOOL_ADS_LEADS, "Google Guaranteed response sent", LOG_SUCCESS, "Message appended to the Local Services lead conversation.", request_payload={"lead": ads_lead.external_resource_name}, response_payload=response, external_id=ads_lead.external_lead_id, user=user)
    return response


def log_google_lead_reply(ads_lead, channel, message, subject="", user=None):
    status = REPLY_STATUS_LOGGED
    external_response_id = ""
    error_message = ""
    if channel == REPLY_CHANNEL_GOOGLE_MESSAGE:
        try:
            response = append_lsa_lead_conversation(ads_lead, message, user=user)
            status = REPLY_STATUS_SENT
            responses = response.get("responses") or []
            if responses:
                external_response_id = responses[0].get("localServicesLeadConversation") or ""
        except Exception as exc:
            status = REPLY_STATUS_ERROR
            error_message = str(exc)
            create_log(ads_lead.id_company, ads_lead.connection, TOOL_ADS_LEADS, "Google Guaranteed response failed", LOG_ERROR, error_message, request_payload={"channel": channel}, external_id=ads_lead.external_lead_id, user=user)
    reply = GoogleAdsLeadReply.objects.create(
        id_company=ads_lead.id_company,
        ads_lead=ads_lead,
        channel=channel,
        status=status,
        subject=subject or "Google lead follow-up",
        message=message,
        external_response_id=external_response_id or None,
        error_message=error_message or None,
        created_by=user,
    )
    ads_lead.last_reply_message = message
    ads_lead.last_reply_at = timezone.now()
    ads_lead.crm_status = "contacted"
    ads_lead.updated_by = user
    ads_lead.save(update_fields=["last_reply_message", "last_reply_at", "crm_status", "updated_by", "updated_at"])
    if status == REPLY_STATUS_ERROR:
        return reply
    create_log(ads_lead.id_company, ads_lead.connection, TOOL_ADS_LEADS, "Google lead response logged", LOG_SUCCESS, "Response saved in CRM." if channel != REPLY_CHANNEL_GOOGLE_MESSAGE else "Response sent to Google Guaranteed conversation.", request_payload={"channel": channel}, external_id=ads_lead.external_lead_id, user=user)
    return reply
