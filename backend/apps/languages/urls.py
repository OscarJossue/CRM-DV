from django.urls import path

from .views import CompanyLanguageView

app_name = "languages"

urlpatterns = [
    path("", CompanyLanguageView.as_view(), name="settings"),
]
