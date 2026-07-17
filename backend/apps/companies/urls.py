from django.urls import path

from .views import (
    CompanyCreateView,
    CompanyDetailView,
    CompanyListView,
    CompanyUpdateView,
    company_activate_view,
    company_deactivate_view,
)

app_name = "companies"

urlpatterns = [
    path("", CompanyListView.as_view(), name="company_list"),
    # Kept only so old bookmarks do not break. Both routes now use the same
    # company + administrator provisioning process.
    path("onboarding/", CompanyCreateView.as_view(), name="company_onboarding"),
    path("create/", CompanyCreateView.as_view(), name="company_create"),
    path("<int:id_company>/", CompanyDetailView.as_view(), name="company_detail"),
    path("<int:id_company>/edit/", CompanyUpdateView.as_view(), name="company_update"),
    path("<int:id_company>/activate/", company_activate_view, name="company_activate"),
    path("<int:id_company>/deactivate/", company_deactivate_view, name="company_deactivate"),
]
