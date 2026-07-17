from django import forms

from apps.accounts.models import UserAccount
from apps.companies.models import Company
from apps.projects.models import Project

from .models import CalendarEvent
from .models.choices import EVENT_STATUS_CHOICES, EVENT_STATUS_SCHEDULED


class CalendarEventForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=EVENT_STATUS_CHOICES,
        initial=EVENT_STATUS_SCHEDULED,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    class Meta:
        model = CalendarEvent
        fields = [
            "id_company",
            "id_project",
            "id_assigned_user",
            "title",
            "event_date",
            "start_time",
            "end_time",
            "location",
            "status",
        ]
        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_project": forms.Select(attrs={"class": "crm_input"}),
            "id_assigned_user": forms.Select(attrs={"class": "crm_input"}),
            "title": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Event title",
                }
            ),
            "event_date": forms.DateInput(
                attrs={
                    "class": "crm_input",
                    "type": "date",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={
                    "class": "crm_input",
                    "type": "time",
                }
            ),
            "end_time": forms.TimeInput(
                attrs={
                    "class": "crm_input",
                    "type": "time",
                }
            ),
            "location": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                    "placeholder": "Event location or meeting notes",
                }
            ),
        }

    def __init__(self, *args, user=None, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user
        self.project = project

        if project:
            self.fields["id_company"].queryset = Company.objects.filter(
                id_company=project.id_company_id
            )
            self.fields["id_company"].initial = project.id_company
            self.fields["id_company"].disabled = True

            self.fields["id_project"].queryset = Project.objects.filter(
                id_project=project.id_project
            )
            self.fields["id_project"].initial = project
            self.fields["id_project"].disabled = True

            self.fields["id_assigned_user"].queryset = UserAccount.objects.filter(
                id_company=project.id_company_id,
                is_active=True,
            ).order_by("first_name", "last_name", "email")
            return

        if user and not user.is_superuser:
            self.fields["id_company"].queryset = Company.objects.filter(
                id_company=user.id_company_id
            )
            self.fields["id_company"].initial = user.id_company
            self.fields["id_company"].disabled = True

            self.fields["id_project"].queryset = Project.objects.filter(
                id_company=user.id_company_id
            ).order_by("-created_at")

            self.fields["id_assigned_user"].queryset = UserAccount.objects.filter(
                id_company=user.id_company_id,
                is_active=True,
            ).order_by("first_name", "last_name", "email")
        else:
            self.fields["id_company"].queryset = Company.objects.all().order_by("name")

            self.fields["id_project"].queryset = Project.objects.select_related(
                "id_company",
                "id_client",
            ).all().order_by("-created_at")

            self.fields["id_assigned_user"].queryset = UserAccount.objects.select_related(
                "id_company"
            ).filter(is_active=True).order_by("id_company__name", "first_name", "email")

    def clean(self):
        cleaned_data = super().clean()

        company = cleaned_data.get("id_company")
        project = cleaned_data.get("id_project") or self.project
        assigned_user = cleaned_data.get("id_assigned_user")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if self.project:
            cleaned_data["id_company"] = self.project.id_company
            cleaned_data["id_project"] = self.project
            company = self.project.id_company
            project = self.project

        if (
            self.request_user
            and not self.request_user.is_superuser
            and company
            and company.id_company != self.request_user.id_company_id
        ):
            raise forms.ValidationError("You can only manage calendar events for your company.")

        if project and company and project.id_company_id != company.id_company:
            raise forms.ValidationError("Project must belong to the selected company.")

        if assigned_user and company and assigned_user.id_company_id != company.id_company:
            raise forms.ValidationError("Assigned user must belong to the selected company.")

        if start_time and end_time and end_time <= start_time:
            raise forms.ValidationError("End time must be greater than start time.")

        return cleaned_data

    def save(self, commit=True):
        event = super().save(commit=False)

        if self.project:
            event.id_company = self.project.id_company
            event.id_project = self.project

        if self.request_user and not self.request_user.is_superuser:
            event.id_company = self.request_user.id_company

        if commit:
            event.save()

        return event
