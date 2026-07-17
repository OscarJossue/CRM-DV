from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyModuleCreateView,
    CompanyModuleDetailView,
    CompanyModuleListView,
    CompanyModuleManageView,
    CompanyModuleUpdateView,
    CompanyModuleViewSet,
    company_module_sync_view,
)

app_name = "company_modules"

router = DefaultRouter()
router.register(r"company-modules", CompanyModuleViewSet, basename="company_modules_api")

urlpatterns = [
    path("", CompanyModuleListView.as_view(), name="company_module_list"),
    path("create/", CompanyModuleCreateView.as_view(), name="company_module_create"),
    path(
        "companies/<int:id_company>/manage/",
        CompanyModuleManageView.as_view(),
        name="company_module_manage",
    ),
    path(
        "companies/<int:id_company>/sync/",
        company_module_sync_view,
        name="company_module_sync",
    ),
    path(
        "<int:id_company_module>/",
        CompanyModuleDetailView.as_view(),
        name="company_module_detail",
    ),
    path(
        "<int:id_company_module>/edit/",
        CompanyModuleUpdateView.as_view(),
        name="company_module_update",
    ),
    path("api/", include(router.urls)),
]
