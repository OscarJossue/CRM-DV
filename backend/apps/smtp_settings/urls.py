from django.urls import path

from .views import SmtpSettingUpdateView, SmtpTestView

app_name = "smtp_settings"

urlpatterns = [
    path("", SmtpSettingUpdateView.as_view(), name="form"),
    path("test/", SmtpTestView.as_view(), name="test"),
]