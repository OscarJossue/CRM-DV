from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClientCreateView,
    ClientDetailView,
    ClientListView,
    ClientUpdateView,
    ClientViewSet,
    client_delete_view,
)

app_name = "clients"

router = DefaultRouter()
router.register(r"clients", ClientViewSet, basename="clients_api")

urlpatterns = [
    path("", ClientListView.as_view(), name="client_list"),
    path("create/", ClientCreateView.as_view(), name="client_create"),
    path("<int:id_client>/", ClientDetailView.as_view(), name="client_detail"),
    path("<int:id_client>/edit/", ClientUpdateView.as_view(), name="client_update"),
    path("<int:id_client>/delete/", client_delete_view, name="client_delete"),
    path("api/", include(router.urls)),
    
]