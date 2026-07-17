from django import forms
from django.db.models import Q

from apps.accounts.models import UserAccount
from apps.inspections.models import InspectionAssignment
from apps.projects.models import Project

from .models import Supervision


class SupervisionForm(forms.ModelForm):
    class Meta:
        model = Supervision
        fields = [
            "id_project",
            "id_inspection_assignment",
            "id_supervisor",
            "observations",
        ]
        widgets = {
            "id_project": forms.Select(attrs={"class": "crm_input"}),
            "id_inspection_assignment": forms.Select(attrs={"class": "crm_input"}),
            "id_supervisor": forms.Select(attrs={"class": "crm_input"}),
            "observations": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 5,
                    "placeholder": "Audit observations, corrections or final notes",
                }
            ),
        }

    def __init__(self, *args, user=None, project=None, inspection=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        self.project = project
        self.inspection = inspection

        self.fields["id_project"].required = False
        self.fields["id_inspection_assignment"].required = False
        self.fields["id_supervisor"].required = False

        company_id = None
        if project:
            company_id = project.id_company_id
            self.fields["id_project"].queryset = Project.objects.filter(pk=project.pk)
            self.fields["id_project"].initial = project
            self.fields["id_project"].disabled = True
            self.fields["id_inspection_assignment"].queryset = InspectionAssignment.objects.none()
            self.fields["id_inspection_assignment"].disabled = True
        elif inspection:
            company_id = inspection.id_company_id
            self.fields["id_inspection_assignment"].queryset = InspectionAssignment.objects.filter(pk=inspection.pk)
            self.fields["id_inspection_assignment"].initial = inspection
            self.fields["id_inspection_assignment"].disabled = True
            self.fields["id_project"].queryset = Project.objects.none()
            self.fields["id_project"].disabled = True
        elif self.instance and self.instance.pk:
            company_id = self.instance.company_id
            if self.instance.id_project_id:
                self.fields["id_project"].queryset = Project.objects.filter(pk=self.instance.id_project_id)
                self.fields["id_project"].disabled = True
                self.fields["id_inspection_assignment"].queryset = InspectionAssignment.objects.none()
                self.fields["id_inspection_assignment"].disabled = True
            else:
                self.fields["id_inspection_assignment"].queryset = InspectionAssignment.objects.filter(
                    pk=self.instance.id_inspection_assignment_id
                )
                self.fields["id_inspection_assignment"].disabled = True
                self.fields["id_project"].queryset = Project.objects.none()
                self.fields["id_project"].disabled = True
        elif user and not user.is_superuser:
            company_id = user.id_company_id
            self.fields["id_project"].queryset = Project.objects.filter(
                id_company_id=company_id, status="audit"
            ).order_by("-created_at")
            self.fields["id_inspection_assignment"].queryset = InspectionAssignment.objects.filter(
                client__id_company_id=company_id, status="audit"
            ).select_related("client").order_by("-created_at")
        else:
            self.fields["id_project"].queryset = Project.objects.select_related("id_company", "id_client")
            self.fields["id_inspection_assignment"].queryset = InspectionAssignment.objects.select_related(
                "client", "client__id_company"
            )

        supervisors = UserAccount.objects.select_related("id_role").filter(is_active=True)
        if company_id:
            supervisors = supervisors.filter(id_company_id=company_id)
        supervisors = supervisors.filter(Q(id_role__is_contractor_only=False) | Q(id_role__isnull=True))
        self.fields["id_supervisor"].queryset = supervisors.order_by("first_name", "last_name", "email")
        self.fields["id_supervisor"].empty_label = "Unassigned audit"

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("id_project") or self.project
        inspection = cleaned_data.get("id_inspection_assignment") or self.inspection
        supervisor = cleaned_data.get("id_supervisor")

        if bool(project) == bool(inspection):
            raise forms.ValidationError("Select exactly one project or inspection for this audit.")

        company_id = project.id_company_id if project else inspection.id_company_id
        target_status = project.status if project else inspection.status
        if not self.instance.pk and target_status != "audit":
            raise forms.ValidationError("Only work submitted to Audit can enter the review queue.")

        if self.request_user and not self.request_user.is_superuser:
            if company_id != self.request_user.id_company_id:
                raise forms.ValidationError("You can only manage audits for your company.")

        if supervisor and supervisor.id_company_id != company_id:
            raise forms.ValidationError("Supervisor must belong to the same company as the audited record.")

        if supervisor and getattr(getattr(supervisor, "id_role", None), "is_contractor_only", False):
            self.add_error("id_supervisor", "A contractor-only user cannot audit their own field work.")

        cleaned_data["id_project"] = project
        cleaned_data["id_inspection_assignment"] = inspection
        return cleaned_data

    def save(self, commit=True):
        supervision = super().save(commit=False)
        if self.project:
            supervision.id_project = self.project
            supervision.id_inspection_assignment = None
        elif self.inspection:
            supervision.id_inspection_assignment = self.inspection
            supervision.id_project = None
        if commit:
            supervision.full_clean()
            supervision.save()
        return supervision
