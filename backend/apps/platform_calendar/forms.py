from django import forms
from django.utils import timezone

from .models import PlatformCalendarEvent


class PlatformCalendarEventForm(forms.ModelForm):
    class Meta:
        model = PlatformCalendarEvent
        fields = [
            "title",
            "event_type",
            "id_company",
            "id_subscription",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "status",
            "priority",
            "description",
        ]
        labels = {
            "title": "Event Title",
            "event_type": "Event Type",
            "id_company": "Company",
            "id_subscription": "Subscription",
            "start_date": "Start Date",
            "start_time": "Start Time",
            "end_date": "End Date",
            "end_time": "End Time",
            "status": "Status",
            "priority": "Priority",
            "description": "Description",
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Call company owner, review payment, renewal follow up",
                }
            ),
            "event_type": forms.Select(attrs={"class": "crm_input"}),
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_subscription": forms.Select(attrs={"class": "crm_input"}),
            "start_date": forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
            "start_time": forms.TimeInput(attrs={"class": "crm_input", "type": "time"}),
            "end_date": forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
            "end_time": forms.TimeInput(attrs={"class": "crm_input", "type": "time"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "priority": forms.Select(attrs={"class": "crm_input"}),
            "description": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 5,
                    "placeholder": "Internal notes for CEO MARKETING team.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["start_date"].initial = timezone.localdate()

        self.fields["id_company"].required = False
        self.fields["id_subscription"].required = False
        self.fields["start_time"].required = False
        self.fields["end_date"].required = False
        self.fields["end_time"].required = False
        self.fields["description"].required = False

        company_id = None

        if self.data.get("id_company"):
            company_id = self.data.get("id_company")
        elif self.instance and self.instance.pk and self.instance.id_company_id:
            company_id = self.instance.id_company_id

        if company_id:
            self.fields["id_subscription"].queryset = self.fields["id_subscription"].queryset.filter(
                id_company_id=company_id
            )

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        company = cleaned_data.get("id_company")
        subscription = cleaned_data.get("id_subscription")

        if end_date and start_date and end_date < start_date:
            self.add_error("end_date", "End date cannot be before start date.")

        if company and subscription and subscription.id_company_id != company.id_company:
            self.add_error("id_subscription", "The selected subscription does not belong to this company.")

        return cleaned_data