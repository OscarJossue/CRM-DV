from django import forms

from apps.accounts.models.choices import TENANT_MODULE_CHOICES
from apps.companies.models import Company

from .models import CompanyModule


class CompanyModuleForm(forms.ModelForm):
    class Meta:
        model = CompanyModule
        fields = [
            "id_company",
            "module",
            "is_enabled",
        ]
        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "module": forms.Select(attrs={"class": "crm_input"}),
            "is_enabled": forms.CheckboxInput(attrs={"class": "crm_checkbox"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["id_company"].queryset = Company.objects.all().order_by("name")
        self.fields["module"].choices = TENANT_MODULE_CHOICES

    def clean(self):
        cleaned_data = super().clean()

        company = cleaned_data.get("id_company")
        module = cleaned_data.get("module")

        if company and module:
            queryset = CompanyModule.objects.filter(
                id_company=company,
                module=module,
            )

            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise forms.ValidationError(
                    "This company already has a configuration for this module."
                )

        return cleaned_data
