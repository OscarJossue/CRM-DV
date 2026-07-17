from apps.core.tenant import filter_queryset_for_user, get_user_company, user_is_global_admin

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


def connection_for_user(user):
    company = get_user_company(user)
    if not company and not user_is_global_admin(user):
        return None
    queryset = GoogleIntegrationConnection.objects.select_related("id_company", "created_by")
    if user_is_global_admin(user):
        return queryset.first()
    return queryset.filter(id_company=company).first()


def connections_for_user(user):
    queryset = GoogleIntegrationConnection.objects.select_related("id_company", "created_by", "updated_by")
    return filter_queryset_for_user(queryset, user, "id_company")


def logs_for_user(user):
    queryset = IntegrationLog.objects.select_related("id_company", "connection", "created_by")
    return filter_queryset_for_user(queryset, user, "id_company")


def calendar_events_for_user(user):
    queryset = GoogleCalendarEventLink.objects.select_related("id_company", "connection", "created_by")
    return filter_queryset_for_user(queryset, user, "id_company")


def drive_uploads_for_user(user):
    queryset = GoogleDriveUpload.objects.select_related("id_company", "connection", "created_by")
    return filter_queryset_for_user(queryset, user, "id_company")


def sheet_exports_for_user(user):
    queryset = GoogleSheetExport.objects.select_related("id_company", "connection", "created_by")
    return filter_queryset_for_user(queryset, user, "id_company")


def analytics_snapshots_for_user(user):
    queryset = GoogleAnalyticsSnapshot.objects.select_related("id_company", "connection", "created_by")
    return filter_queryset_for_user(queryset, user, "id_company")


def ads_snapshots_for_user(user):
    queryset = GoogleAdsSnapshot.objects.select_related("id_company", "connection", "created_by")
    return filter_queryset_for_user(queryset, user, "id_company")


def google_ads_leads_for_user(user):
    queryset = GoogleAdsLead.objects.select_related("id_company", "connection", "crm_lead", "created_by", "updated_by")
    return filter_queryset_for_user(queryset, user, "id_company")


def google_ads_replies_for_user(user):
    queryset = GoogleAdsLeadReply.objects.select_related("id_company", "ads_lead", "created_by")
    return filter_queryset_for_user(queryset, user, "id_company")
