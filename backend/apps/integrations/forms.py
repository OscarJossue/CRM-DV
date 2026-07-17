from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import (
    GoogleAdsLead,
    GoogleAdsLeadReply,
    GoogleCalendarEventLink,
    GoogleDriveUpload,
    GoogleIntegrationConnection,
    GoogleSheetExport,
)
from .models.choices import (
    GOOGLE_LEAD_CRM_STATUS_CHOICES,
    REPLY_CHANNEL_CHOICES,
    REPLY_CHANNEL_CRM_NOTE,
    SHEET_EXPORT_SOURCE_CHOICES,
)


COMMON_INPUT_CLASS = "form-control"


class GoogleOAuthCredentialsForm(forms.ModelForm):
    oauth_client_id = forms.CharField(
        label="Google OAuth Client ID",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Paste the Google OAuth Client ID",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text="Encrypted at rest and stored only for this company.",
    )
    oauth_client_secret = forms.CharField(
        label="Google OAuth Client Secret",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Paste the client secret or leave blank to keep the current one",
                "autocomplete": "new-password",
                "spellcheck": "false",
            },
            render_value=False,
        ),
        help_text="For security, the saved secret is never displayed again.",
    )

    class Meta:
        model = GoogleIntegrationConnection
        fields = [
            "calendar_id",
            "drive_folder_id",
            "analytics_property_id",
        ]
        labels = {
            "calendar_id": "Google Calendar ID",
            "drive_folder_id": "Google Drive Folder ID",
            "analytics_property_id": "Google Analytics Property ID",
        }
        widgets = {
            "calendar_id": forms.TextInput(attrs={"placeholder": "primary", "autocomplete": "off"}),
            "drive_folder_id": forms.TextInput(
                attrs={"placeholder": "Optional Drive folder ID", "autocomplete": "off", "spellcheck": "false"}
            ),
            "analytics_property_id": forms.TextInput(
                attrs={"placeholder": "GA4 numeric Property ID, for example 123456789", "autocomplete": "off", "inputmode": "numeric"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["oauth_client_id"].initial = self.instance.get_oauth_client_id()
            if not self.instance.get_oauth_client_secret():
                self.fields["oauth_client_secret"].required = True

        help_texts = {
            "calendar_id": "Use primary for the connected Google account, unless you need a specific calendar ID.",
            "drive_folder_id": "Optional. When empty, uploads go to the connected account's Drive area.",
            "analytics_property_id": "Use the numeric GA4 Property ID, not the G- Measurement ID.",
        }
        for name, help_text in help_texts.items():
            self.fields[name].help_text = help_text

        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {COMMON_INPUT_CLASS}".strip()

    def clean_oauth_client_secret(self):
        secret = self.cleaned_data.get("oauth_client_secret", "")
        if not secret and not (self.instance and self.instance.get_oauth_client_secret()):
            raise forms.ValidationError("Google OAuth Client Secret is required for the first configuration.")
        return secret

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.set_oauth_client_id(self.cleaned_data.get("oauth_client_id"))
        secret = self.cleaned_data.get("oauth_client_secret")
        if secret:
            instance.set_oauth_client_secret(secret)
        if commit:
            instance.save()
        return instance


class GoogleConnectionSettingsForm(forms.ModelForm):
    class Meta:
        model = GoogleIntegrationConnection
        fields = [
            "calendar_id",
            "drive_folder_id",
            "analytics_property_id",
        ]
        labels = {
            "calendar_id": "Google Calendar ID",
            "drive_folder_id": "Google Drive Folder ID",
            "analytics_property_id": "Google Analytics Property ID",
        }
        widgets = {
            "calendar_id": forms.TextInput(attrs={"placeholder": "primary", "autocomplete": "off"}),
            "drive_folder_id": forms.TextInput(
                attrs={"placeholder": "Optional Drive folder ID", "autocomplete": "off", "spellcheck": "false"}
            ),
            "analytics_property_id": forms.TextInput(
                attrs={"placeholder": "GA4 numeric Property ID", "autocomplete": "off", "inputmode": "numeric"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        help_texts = {
            "calendar_id": "Use primary for the connected Google account.",
            "drive_folder_id": "Optional destination folder for CRM uploads.",
            "analytics_property_id": "Numeric GA4 Property ID used by Analytics reports.",
        }
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {COMMON_INPUT_CLASS}".strip()
            field.help_text = help_texts.get(name, field.help_text)


class CalendarEventForm(forms.ModelForm):
    class Meta:
        model = GoogleCalendarEventLink
        fields = ["title", "description", "start_at", "end_at", "attendees"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Meeting title"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Internal notes or meeting agenda"}),
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "attendees": forms.Textarea(attrs={"rows": 3, "placeholder": "client@email.com, team@email.com"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["end_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if not self.initial.get("start_at") and not getattr(self.instance, "pk", None):
            start = timezone.now() + timedelta(days=1)
            self.initial["start_at"] = start.strftime("%Y-%m-%dT%H:%M")
            self.initial["end_at"] = (start + timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M")
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {COMMON_INPUT_CLASS}".strip()

    def clean(self):
        cleaned = super().clean()
        start_at = cleaned.get("start_at")
        end_at = cleaned.get("end_at")
        if start_at and end_at and end_at <= start_at:
            self.add_error("end_at", "End time must be after start time.")
        return cleaned


class DriveUploadForm(forms.ModelForm):
    class Meta:
        model = GoogleDriveUpload
        fields = ["title", "file", "source_module"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "File title in CRM"}),
            "source_module": forms.TextInput(attrs={"placeholder": "Invoices, Estimates, Evidence, etc."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {COMMON_INPUT_CLASS}".strip()


class SheetExportForm(forms.ModelForm):
    export_source = forms.ChoiceField(choices=SHEET_EXPORT_SOURCE_CHOICES, required=True)

    class Meta:
        model = GoogleSheetExport
        fields = ["export_source", "spreadsheet_id", "sheet_name"]
        widgets = {
            "spreadsheet_id": forms.TextInput(attrs={"placeholder": "Google Spreadsheet ID"}),
            "sheet_name": forms.TextInput(attrs={"placeholder": "Sheet tab name"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} {COMMON_INPUT_CLASS}".strip()


class DateRangeReportForm(forms.Form):
    date_from = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": COMMON_INPUT_CLASS}), required=True)
    date_to = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": COMMON_INPUT_CLASS}), required=True)

    def __init__(self, *args, **kwargs):
        default_days = kwargs.pop("default_days", 30)
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.initial.setdefault("date_to", today)
        self.initial.setdefault("date_from", today - timedelta(days=default_days))

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_to < date_from:
            self.add_error("date_to", "End date must be after start date.")
        return cleaned


class GoogleAdsLeadSyncForm(DateRangeReportForm):
    sync_source = forms.ChoiceField(
        label="Lead Source",
        required=True,
        choices=[
            ("local_services", "Google Guaranteed / Local Services Ads"),
            ("lead_forms", "Google Ads Lead Form Submissions"),
        ],
        widget=forms.Select(attrs={"class": COMMON_INPUT_CLASS}),
    )


class GoogleAdsLeadStatusForm(forms.ModelForm):
    class Meta:
        model = GoogleAdsLead
        fields = ["crm_status"]
        widgets = {"crm_status": forms.Select(attrs={"class": COMMON_INPUT_CLASS})}


class GoogleAdsLeadReplyForm(forms.ModelForm):
    class Meta:
        model = GoogleAdsLeadReply
        fields = ["channel", "subject", "message"]
        widgets = {
            "channel": forms.Select(attrs={"class": COMMON_INPUT_CLASS}),
            "subject": forms.TextInput(attrs={"class": COMMON_INPUT_CLASS, "placeholder": "Optional subject"}),
            "message": forms.Textarea(attrs={"class": COMMON_INPUT_CLASS, "rows": 5, "placeholder": "Write the response or follow-up note"}),
        }

    def __init__(self, *args, **kwargs):
        lead = kwargs.pop("lead", None)
        super().__init__(*args, **kwargs)
        self.fields["channel"].choices = REPLY_CHANNEL_CHOICES
        if lead and not self.initial.get("message"):
            name = lead.customer_name or "there"
            self.initial["message"] = f"Hi {name}, thanks for contacting us. We received your request and will follow up shortly."
