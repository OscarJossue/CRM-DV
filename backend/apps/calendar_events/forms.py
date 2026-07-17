from django import forms

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.companies.models import Company
from apps.estimates.models import Estimate
from apps.inspections.models import InspectionAssignment
from apps.invoices.models import Invoice
from apps.opportunities.models import Lead
from apps.payments.models import Payment
from apps.projects.models import Project

from .models import CalendarEvent
from .models.choices import (
    EVENT_CATEGORY_CHOICES,
    EVENT_CATEGORY_TASK,
    EVENT_PRIORITY_CHOICES,
    EVENT_PRIORITY_NORMAL,
    EVENT_STATUS_CHOICES,
    EVENT_STATUS_SCHEDULED,
    RELATED_TYPE_CHOICES,
    RELATED_TYPE_CLIENT,
    RELATED_TYPE_ESTIMATE,
    RELATED_TYPE_INSPECTION,
    RELATED_TYPE_INVOICE,
    RELATED_TYPE_OPPORTUNITY,
    RELATED_TYPE_PAYMENT,
    RELATED_TYPE_PROJECT,
)


RELATION_FIELD_BY_TYPE = {
    RELATED_TYPE_PROJECT: "id_project",
    RELATED_TYPE_INSPECTION: "id_inspection_assignment",
    RELATED_TYPE_ESTIMATE: "id_estimate",
    RELATED_TYPE_INVOICE: "id_invoice",
    RELATED_TYPE_PAYMENT: "id_payment",
    RELATED_TYPE_CLIENT: "id_client",
    RELATED_TYPE_OPPORTUNITY: "id_opportunity",
}


class CalendarEventForm(forms.ModelForm):
    related_type = forms.ChoiceField(
        choices=RELATED_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "crm_input", "data-related-type": "true"}),
    )

    status = forms.ChoiceField(
        choices=EVENT_STATUS_CHOICES,
        initial=EVENT_STATUS_SCHEDULED,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    category = forms.ChoiceField(
        choices=EVENT_CATEGORY_CHOICES,
        initial=EVENT_CATEGORY_TASK,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    priority = forms.ChoiceField(
        choices=EVENT_PRIORITY_CHOICES,
        initial=EVENT_PRIORITY_NORMAL,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    class Meta:
        model = CalendarEvent
        fields = [
            "id_company",
            "related_type",
            "id_project",
            "id_inspection_assignment",
            "id_estimate",
            "id_invoice",
            "id_payment",
            "id_client",
            "id_opportunity",
            "id_assigned_user",
            "title",
            "description",
            "category",
            "priority",
            "event_date",
            "start_time",
            "end_time",
            "location",
            "status",
        ]
        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_project": forms.Select(attrs={"class": "crm_input"}),
            "id_inspection_assignment": forms.Select(attrs={"class": "crm_input"}),
            "id_estimate": forms.Select(attrs={"class": "crm_input"}),
            "id_invoice": forms.Select(attrs={"class": "crm_input"}),
            "id_payment": forms.Select(attrs={"class": "crm_input"}),
            "id_client": forms.Select(attrs={"class": "crm_input"}),
            "id_opportunity": forms.Select(attrs={"class": "crm_input"}),
            "id_assigned_user": forms.Select(attrs={"class": "crm_input"}),
            "title": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Example: Review roof replacement proposal",
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Add the objective, instructions, preparation or follow-up required.",
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
                    "placeholder": "Address, meeting link or place where the activity occurs.",
                }
            ),
        }

    def __init__(
        self,
        *args,
        user=None,
        company=None,
        project=None,
        initial_related_type=None,
        initial_related_id=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.request_user = user
        self.bound_company = company or getattr(project, "id_company", None)
        self.project = project
        self.show_company_selector = False

        for field_name in RELATION_FIELD_BY_TYPE.values():
            self.fields[field_name].required = False
            self.fields[field_name].empty_label = "Select a record"
            self.fields[field_name].widget.attrs["data-related-field"] = field_name

        self.fields["id_assigned_user"].required = False
        self.fields["id_assigned_user"].empty_label = "Unassigned"
        self.fields["title"].required = True
        self.fields["event_date"].required = True

        if self.instance and self.instance.pk and not self.is_bound:
            self.initial["related_type"] = self.instance.related_type or self._infer_related_type()

        if initial_related_type and not self.is_bound:
            self.initial["related_type"] = initial_related_type
            relation_field = RELATION_FIELD_BY_TYPE.get(initial_related_type)
            if relation_field and initial_related_id:
                self.initial[relation_field] = initial_related_id

        if project:
            self.initial["related_type"] = RELATED_TYPE_PROJECT
            self.initial["id_project"] = project

        self._configure_company_field()
        self._configure_company_querysets()

    def _infer_related_type(self):
        for related_type, field_name in RELATION_FIELD_BY_TYPE.items():
            if getattr(self.instance, f"{field_name}_id", None):
                return related_type
        return ""

    def _configure_company_field(self):
        company = self.bound_company

        if not company and self.request_user and not self.request_user.is_superuser:
            company = getattr(self.request_user, "id_company", None)
            self.bound_company = company

        if company:
            self.fields["id_company"].queryset = Company.objects.filter(
                id_company=company.id_company
            )
            self.fields["id_company"].initial = company
            self.fields["id_company"].widget = forms.HiddenInput()
            return

        self.show_company_selector = True
        self.fields["id_company"].queryset = Company.objects.all().order_by("name")

    def _configure_company_querysets(self):
        company = self.bound_company

        if company:
            self.fields["id_project"].queryset = Project.objects.filter(
                id_company=company
            ).select_related("id_client").order_by("-created_at")

            self.fields["id_inspection_assignment"].queryset = (
                InspectionAssignment.objects.filter(client__id_company=company)
                .select_related("client", "inspector")
                .order_by("-inspection_date")
            )

            self.fields["id_estimate"].queryset = Estimate.objects.filter(
                id_company=company
            ).select_related("id_client", "id_project").order_by("-issue_date", "-id_estimate")

            self.fields["id_invoice"].queryset = Invoice.objects.filter(
                id_company=company
            ).select_related("id_client", "id_project").order_by("-issue_date", "-id_invoice")

            self.fields["id_payment"].queryset = Payment.objects.filter(
                id_company=company
            ).select_related("id_client", "id_project", "id_invoice").order_by("-payment_date", "-id_payment")

            self.fields["id_client"].queryset = Client.objects.filter(
                id_company=company
            ).order_by("name")

            self.fields["id_opportunity"].queryset = Lead.objects.filter(
                id_company=company
            ).select_related("id_client", "id_assigned_user").order_by("-created_at")

            self.fields["id_assigned_user"].queryset = UserAccount.objects.filter(
                id_company=company,
                is_active=True,
            ).order_by("first_name", "last_name", "email")
            return

        self.fields["id_project"].queryset = Project.objects.select_related(
            "id_company", "id_client"
        ).all().order_by("id_company__name", "-created_at")
        self.fields["id_inspection_assignment"].queryset = (
            InspectionAssignment.objects.select_related("client", "client__id_company", "inspector")
            .all()
            .order_by("client__id_company__name", "-inspection_date")
        )
        self.fields["id_estimate"].queryset = Estimate.objects.select_related(
            "id_company", "id_client", "id_project"
        ).all().order_by("id_company__name", "-issue_date")
        self.fields["id_invoice"].queryset = Invoice.objects.select_related(
            "id_company", "id_client", "id_project"
        ).all().order_by("id_company__name", "-issue_date")
        self.fields["id_payment"].queryset = Payment.objects.select_related(
            "id_company", "id_client", "id_project", "id_invoice"
        ).all().order_by("id_company__name", "-payment_date")
        self.fields["id_client"].queryset = Client.objects.select_related(
            "id_company"
        ).all().order_by("id_company__name", "name")
        self.fields["id_opportunity"].queryset = Lead.objects.select_related(
            "id_company", "id_client", "id_assigned_user"
        ).all().order_by("id_company__name", "-created_at")
        self.fields["id_assigned_user"].queryset = UserAccount.objects.select_related(
            "id_company"
        ).filter(is_active=True).order_by("id_company__name", "first_name", "email")

    @staticmethod
    def _record_company_id(record):
        if not record:
            return None

        company_id = getattr(record, "id_company_id", None)
        if company_id:
            return company_id

        company = getattr(record, "id_company", None)
        company_id = getattr(company, "id_company", None)
        if company_id:
            return company_id

        client = getattr(record, "client", None) or getattr(record, "id_client", None)
        client_company_id = getattr(client, "id_company_id", None)
        if client_company_id:
            return client_company_id

        project = getattr(record, "id_project", None)
        return getattr(project, "id_company_id", None)

    def clean(self):
        cleaned_data = super().clean()

        company = cleaned_data.get("id_company") or self.bound_company
        related_type = cleaned_data.get("related_type") or ""
        assigned_user = cleaned_data.get("id_assigned_user")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if self.project:
            company = self.project.id_company
            related_type = RELATED_TYPE_PROJECT
            cleaned_data["id_company"] = company
            cleaned_data["related_type"] = related_type
            cleaned_data["id_project"] = self.project

        if (
            self.request_user
            and not self.request_user.is_superuser
            and company
            and company.id_company != self.request_user.id_company_id
        ):
            raise forms.ValidationError("You can only manage calendar events for your company.")

        if not company:
            raise forms.ValidationError("A company is required for the calendar event.")

        if assigned_user and assigned_user.id_company_id != company.id_company:
            self.add_error("id_assigned_user", "Assigned user must belong to the event company.")

        selected_field = RELATION_FIELD_BY_TYPE.get(related_type)
        selected_record = cleaned_data.get(selected_field) if selected_field else None

        for field_name in RELATION_FIELD_BY_TYPE.values():
            if field_name != selected_field:
                cleaned_data[field_name] = None

        if selected_field and not selected_record:
            self.add_error(selected_field, "Select the record that this event should be linked to.")

        if selected_record:
            record_company_id = self._record_company_id(selected_record)
            if record_company_id != company.id_company:
                self.add_error(selected_field, "The linked record must belong to the event company.")

        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "End time must be later than start time.")

        cleaned_data["id_company"] = company
        cleaned_data["related_type"] = related_type
        return cleaned_data

    def save(self, commit=True):
        event = super().save(commit=False)

        event.id_company = self.cleaned_data["id_company"]
        event.related_type = self.cleaned_data.get("related_type") or ""

        for field_name in RELATION_FIELD_BY_TYPE.values():
            setattr(event, field_name, self.cleaned_data.get(field_name))

        linked_record = self.cleaned_data.get(
            RELATION_FIELD_BY_TYPE.get(event.related_type, "")
        )

        if event.related_type in {RELATED_TYPE_ESTIMATE, RELATED_TYPE_INVOICE, RELATED_TYPE_PAYMENT}:
            linked_project = getattr(linked_record, "id_project", None) if linked_record else None
            if linked_project:
                event.id_project = linked_project

        if event.related_type == RELATED_TYPE_OPPORTUNITY and linked_record:
            linked_project = getattr(linked_record, "id_converted_project", None)
            if linked_project:
                event.id_project = linked_project

        if self.project:
            event.related_type = RELATED_TYPE_PROJECT
            event.id_project = self.project

        if commit:
            event.full_clean()
            event.save()

        return event
