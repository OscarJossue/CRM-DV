from django.urls import path

from .views import PlatformLanguageView

app_name = "platform_languages"

urlpatterns = [
    path("", PlatformLanguageView.as_view(), name="settings"),
]
