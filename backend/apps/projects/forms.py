from django import forms

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from .models import Project, ProjectNote

class ProjectForm(forms.ModelForm):
    """Administrative project form.

    Workflow status is intentionally not exposed as a select. New projects are
    saved as Draft or Pending from the two explicit submit buttons. Every later
    status is controlled by dates, contractor submission and audit actions.
    """

    class Meta:
        model = Project
        fields = [
            "id_client",
            "id_inspector",
            "name",
            "contract_amount",
            "start_date",
            "project_address",
            "google_maps_url",
            "description",
            "project_notes",
        ]
        widgets = {
            "id_client": forms.Select(attrs={"class": "crm_input"}),
            "id_inspector": forms.Select(attrs={"class": "crm_input"}),
            "name": forms.TextInput(
                attrs={"class": "crm_input", "placeholder": "Project name"}
            ),
            "contract_amount": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Contract amount",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "start_date": forms.DateInput(
                attrs={"class": "crm_input", "type": "date"}
            ),
            "project_address": forms.TextInput(
                attrs={"class": "crm_input", "placeholder": "Project address"}
            ),
            "google_maps_url": forms.URLInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Optional Google Maps link",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Project description",
                }
            ),
            "project_notes": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Internal project notes",
                }
            ),
        }

    def __init__(self, *args, user=None, opportunity=None, inspection=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        self.opportunity = opportunity
        self.inspection = inspection

        self.fields["id_client"].required = True
        self.fields["id_inspector"].required = False
        self.fields["name"].required = True
        self.fields["contract_amount"].required = False
        self.fields["start_date"].required = False
        self.fields["project_address"].required = False
        self.fields["google_maps_url"].required = False
        self.fields["description"].required = False
        self.fields["project_notes"].required = False

        def client_label(obj):
            code = obj.client_code or f"CL_{obj.id_client:06d}"
            name = obj.name or "No name"
            phone = obj.phone or "No phone"
            return f"{code} - {name} - {phone}"

        def user_label(obj):
            full_name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
            role_name = obj.id_role.name if obj.id_role else "No role"
            return f"{full_name or obj.email} - {obj.email} - {role_name}"

        self.fields["id_client"].label_from_instance = client_label
        self.fields["id_inspector"].label_from_instance = user_label

        if user and user.is_authenticated and user.id_company_id:
            company_id = user.id_company_id
            company_users = (
                UserAccount.objects.select_related("id_company", "id_role")
                .filter(id_company_id=company_id, is_active=True)
                .order_by("first_name", "last_name", "email")
            )
            self.fields["id_client"].queryset = Client.objects.filter(
                id_company_id=company_id
            ).order_by("name")
            self.fields["id_inspector"].queryset = company_users
        else:
            self.fields["id_client"].queryset = Client.objects.none()
            self.fields["id_inspector"].queryset = UserAccount.objects.none()

        if opportunity and opportunity.id_client:
            client = opportunity.id_client
            self.fields["id_client"].initial = client
            self.fields["id_client"].disabled = True
            self.fields["id_inspector"].initial = opportunity.id_assigned_user
            self.fields["name"].initial = (
                f"{opportunity.opportunity_code} - {client.name}"
                if opportunity.opportunity_code and client.name
                else opportunity.opportunity_code or client.name or ""
            )
            self.fields["project_address"].initial = client.address or ""
            self.fields["description"].initial = "\n\n".join(
                value
                for value in [opportunity.project_description, opportunity.notes]
                if value
            )
            self.fields["contract_amount"].initial = opportunity.approximate_value or 0

        if inspection and inspection.client_id:
            client = inspection.client
            self.fields["id_client"].initial = client
            self.fields["id_client"].disabled = True
            self.fields["id_inspector"].initial = inspection.inspector
            self.fields["name"].initial = f"Project - {client.name or 'Inspection'}"
            self.fields["project_address"].initial = client.address or ""
            self.fields["google_maps_url"].initial = inspection.google_maps_url or ""
            # Only textual source data is transferred. Inspection photos remain
            # attached to the inspection and are never copied into the project.
            self.fields["description"].initial = "\n\n".join(
                value for value in [inspection.notes, inspection.inspection_notes] if value
            )
            self.fields["project_notes"].initial = inspection.recommendations or ""

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Project name is required.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get("id_client")
        inspector = cleaned_data.get("id_inspector")

        if not self.request_user or not self.request_user.is_authenticated:
            raise forms.ValidationError("You must be logged in to manage projects.")
        if not self.request_user.id_company_id:
            raise forms.ValidationError("Your user does not have a company assigned.")

        company = self.request_user.id_company
        if self.opportunity:
            client = self.opportunity.id_client
            cleaned_data["id_client"] = client
        if self.inspection:
            client = self.inspection.client
            cleaned_data["id_client"] = client

        if not client:
            raise forms.ValidationError("Client is required.")
        if client.id_company_id != company.id_company:
            raise forms.ValidationError("Client must belong to your company.")
        if inspector and inspector.id_company_id != company.id_company:
            raise forms.ValidationError("Supervisor / inspector must belong to your company.")
        if self.opportunity and self.opportunity.id_company_id != company.id_company:
            raise forms.ValidationError("Opportunity must belong to your company.")
        if self.inspection and self.inspection.client.id_company_id != company.id_company:
            raise forms.ValidationError("Inspection must belong to your company.")
        return cleaned_data

    def save(self, commit=True):
        project = super().save(commit=False)
        project.id_company = self.request_user.id_company

        if self.inspection and self.inspection.client_id:
            project.id_client = self.inspection.client
            if not project.project_address:
                project.project_address = self.inspection.client.address or ""
            if not project.google_maps_url:
                project.google_maps_url = self.inspection.google_maps_url or ""
            if not project.id_inspector_id and self.inspection.inspector_id:
                project.id_inspector = self.inspection.inspector

        if self.opportunity and self.opportunity.id_client:
            client = self.opportunity.id_client
            project.id_opportunity = self.opportunity
            project.id_client = client
            if not project.project_address:
                project.project_address = client.address or ""
            if not project.name:
                project.name = (
                    f"{self.opportunity.opportunity_code} - {client.name}"
                    if self.opportunity.opportunity_code and client.name
                    else self.opportunity.opportunity_code or client.name or ""
                )
            if not project.description:
                project.description = "\n\n".join(
                    value
                    for value in [
                        self.opportunity.project_description,
                        self.opportunity.notes,
                    ]
                    if value
                )
            if not project.contract_amount:
                project.contract_amount = self.opportunity.approximate_value or 0
            if self.opportunity.id_assigned_user:
                project.id_inspector = self.opportunity.id_assigned_user

        if self.request_user and self.request_user.is_authenticated:
            if not project.pk:
                project.created_by = self.request_user
            project.updated_by = self.request_user

        if commit:
            project.save()
        return project



class ProjectNoteForm(forms.ModelForm):
    class Meta:
        model = ProjectNote
        fields = ["note"]
        widgets = {
            "note": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                    "placeholder": "Write an internal project note",
                }
            )
        }
