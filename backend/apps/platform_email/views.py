from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView

from apps.core.platform_permissions import (
    PERMISSION_CREATE,
    PERMISSION_VIEW,
    PlatformPermissionRequiredMixin,
)
from apps.platform_users.constants import PLATFORM_MODULE_EMAIL

from .forms import PlatformEmailComposeForm
from .models import PlatformEmailLog
from .services import send_platform_email


class PlatformEmailLogListView(LoginRequiredMixin, PlatformPermissionRequiredMixin, ListView):
    platform_module_name = PLATFORM_MODULE_EMAIL
    platform_permission_required = PERMISSION_VIEW

    model = PlatformEmailLog
    template_name = "platform_email/list.html"
    context_object_name = "email_logs"
    login_url = "/login/"
    paginate_by = 20

    def get_queryset(self):
        return PlatformEmailLog.objects.select_related("id_company").all().order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        backend = getattr(
            settings,
            "PLATFORM_EMAIL_BACKEND",
            "django.core.mail.backends.console.EmailBackend",
        )

        context["page_title"] = "Platform Email"
        context["platform_email_backend"] = backend
        context["platform_from_email"] = getattr(settings, "PLATFORM_DEFAULT_FROM_EMAIL", "")
        context["is_console_backend"] = "console.EmailBackend" in backend

        return context


class PlatformEmailComposeView(LoginRequiredMixin, PlatformPermissionRequiredMixin, FormView):
    platform_module_name = PLATFORM_MODULE_EMAIL
    platform_permission_required = PERMISSION_CREATE

    template_name = "platform_email/compose.html"
    form_class = PlatformEmailComposeForm
    success_url = reverse_lazy("platform_email:list")
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        backend = getattr(
            settings,
            "PLATFORM_EMAIL_BACKEND",
            "django.core.mail.backends.console.EmailBackend",
        )

        context["page_title"] = "Compose Platform Email"
        context["platform_email_backend"] = backend
        context["platform_from_email"] = getattr(settings, "PLATFORM_DEFAULT_FROM_EMAIL", "")
        context["is_console_backend"] = "console.EmailBackend" in backend

        return context

    def form_valid(self, form):
        email_log = send_platform_email(
            recipient_email=form.cleaned_data["recipient_email"],
            subject=form.cleaned_data["subject"],
            message=form.cleaned_data["message"],
        )

        if email_log.status == "sent":
            messages.success(self.request, "Platform email sent successfully.")
        else:
            messages.error(self.request, "Platform email failed. Check platform email logs.")

        return super().form_valid(form)