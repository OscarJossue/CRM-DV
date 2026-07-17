from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View


class LegacyHistoryRedirectView(LoginRequiredMixin, View):
    """Keep old bookmarks working after User Activity was unified into History."""

    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        company = getattr(request, "current_company", None) or getattr(request.user, "id_company", None)
        if company and getattr(company, "slug", None):
            return redirect(f"/{company.slug}/system-logs/")
        return redirect("audit:system_log_list")


class UserActivitiesListView(LegacyHistoryRedirectView):
    pass


class UserActivitiesDashboardView(LegacyHistoryRedirectView):
    pass
