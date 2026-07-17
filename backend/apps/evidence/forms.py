from django import forms

from apps.projects.models import Project

from .models import EvidenceFile
from .models.choices import EVIDENCE_TYPE_CHOICES


class EvidenceFileForm(forms.ModelForm):
    file_type = forms.ChoiceField(
        choices=[("", "Select file type")] + EVIDENCE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    file_upload = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "crm_input"}),
        help_text="Upload a local file. The system will save the file path automatically.",
    )

    file_url = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "crm_input",
                "placeholder": "External file URL or saved file path",
            }
        ),
    )

    class Meta:
        model = EvidenceFile
        fields = [
            "id_project",
            "file_type",
            "file_url",
            "description",
        ]
        widgets = {
            "id_project": forms.Select(attrs={"class": "crm_input"}),
            "description": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Evidence description",
                }
            ),
        }

    def __init__(self, *args, user=None, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user
        self.project = project

        if project:
            self.fields["id_project"].queryset = Project.objects.filter(
                id_project=project.id_project
            )
            self.fields["id_project"].initial = project
            self.fields["id_project"].disabled = True
            return

        if user and not user.is_superuser:
            self.fields["id_project"].queryset = Project.objects.filter(
                id_company=user.id_company_id
            ).order_by("-created_at")
        else:
            self.fields["id_project"].queryset = Project.objects.select_related(
                "id_company",
                "id_client",
            ).all().order_by("-created_at")

    def clean(self):
        cleaned_data = super().clean()

        project = cleaned_data.get("id_project") or self.project

        if (
            self.request_user
            and not self.request_user.is_superuser
            and project
            and project.id_company_id != self.request_user.id_company_id
        ):
            raise forms.ValidationError("You can only manage evidence for your company.")

        if not cleaned_data.get("file_upload") and not (cleaned_data.get("file_url") or "").strip():
            raise forms.ValidationError("Upload a file or provide a file URL.")

        return cleaned_data
