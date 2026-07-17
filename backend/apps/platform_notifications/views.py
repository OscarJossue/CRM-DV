from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from apps.core.platform_permissions import (
    PERMISSION_APPROVE,
    PERMISSION_VIEW,
    PlatformPermissionRequiredMixin,
    user_can_platform_action,
)
from apps.platform_users.constants import PLATFORM_MODULE_NOTIFICATIONS

from .models import PlatformNotificationLog
from .services import send_due_subscription_notifications


class PlatformNotificationListView(LoginRequiredMixin, PlatformPermissionRequiredMixin, ListView):
    platform_module_name = PLATFORM_MODULE_NOTIFICATIONS
    platform_permission_required = PERMISSION_VIEW

    model = PlatformNotificationLog
    template_name = "platform_notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 25
    login_url = "/login/"

    def get_queryset(self):
        queryset = (
            PlatformNotificationLog.objects.select_related(
                "id_company",
                "id_subscription",
                "created_by",
            )
            .all()
            .order_by("-created_at")
        )

        status = self.request.GET.get("status", "").strip()
        notification_type = self.request.GET.get("type", "").strip()
        q = self.request.GET.get("q", "").strip()

        if status:
            queryset = queryset.filter(status=status)

        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        if q:
            queryset = queryset.filter(id_company__name__icontains=q)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Platform Notifications"
        context["status_filter"] = self.request.GET.get("status", "").strip()
        context["type_filter"] = self.request.GET.get("type", "").strip()
        context["q"] = self.request.GET.get("q", "").strip()

        context["can_send_notifications"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_NOTIFICATIONS,
            PERMISSION_APPROVE,
        )

        context["total_notifications"] = PlatformNotificationLog.objects.count()
        context["sent_notifications"] = PlatformNotificationLog.objects.filter(status="sent").count()
        context["failed_notifications"] = PlatformNotificationLog.objects.filter(status="failed").count()
        context["pending_notifications"] = PlatformNotificationLog.objects.filter(status="pending").count()

        return context


class PlatformNotificationDetailView(LoginRequiredMixin, PlatformPermissionRequiredMixin, DetailView):
    platform_module_name = PLATFORM_MODULE_NOTIFICATIONS
    platform_permission_required = PERMISSION_VIEW

    model = PlatformNotificationLog
    template_name = "platform_notifications/detail.html"
    context_object_name = "notification"
    pk_url_kwarg = "id_notification"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformNotificationLog.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        )


@require_POST
def send_due_notifications_view(request):
    if not user_can_platform_action(
        request.user,
        PLATFORM_MODULE_NOTIFICATIONS,
        PERMISSION_APPROVE,
    ):
        raise PermissionDenied("You do not have permission to send platform notifications.")

    result = send_due_subscription_notifications(
        days_before=5,
        created_by=request.user,
        force=False,
    )

    messages.success(
        request,
        f"Notifications processed. Sent: {result['sent']}. Skipped: {result['skipped']}. Failed: {result['failed']}.",
    )

    return redirect("platform_notifications:list")