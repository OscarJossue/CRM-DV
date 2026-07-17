from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_tokens import CRMTokenObtainPairView, CRMTokenRefreshView
from .views import MeView, RolePermissionViewSet, RoleViewSet, UserAccountViewSet

router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"role-permissions", RolePermissionViewSet, basename="role-permission")
router.register(r"users", UserAccountViewSet, basename="user-account")

urlpatterns = [
    path("auth/login/", CRMTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", CRMTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="auth_me"),
    path("", include(router.urls)),
]
