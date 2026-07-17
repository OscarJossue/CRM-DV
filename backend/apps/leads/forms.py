from django import forms

from apps.accounts.models import UserAccount
from apps.companies.models import Company

from .models import Lead
from .models.choices import LEAD_SOURCE_CHOICES, LEAD_STATUS_CHOICES, LEAD_STATUS_NEW


class LeadForm(forms.ModelForm):
    source = forms.ChoiceField(
        choices=[("", "Select source")] + LEAD_SOURCE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    status = forms.ChoiceField(
        choices=LEAD_STATUS_CHOICES,
        initial=LEAD_STATUS_NEW,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    class Meta:
        model = Lead
        fields = [
            "id_company",
            "id_assigned_user",
            "name",
            "phone",
            "email",
            "source",
            "address",
            "status",
            "notes",
        ]
        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_assigned_user": forms.Select(attrs={"class": "crm_input"}),
            "name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Lead name",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Phone",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Email",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                    "placeholder": "Address",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Internal notes",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user

        if user and not user.is_superuser:
            self.fields["id_company"].queryset = Company.objects.filter(
                id_company=user.id_company_id
            )
            self.fields["id_company"].initial = user.id_company_id
            self.fields["id_company"].disabled = True

            self.fields["id_assigned_user"].queryset = UserAccount.objects.filter(
                id_company=user.id_company_id,
                is_active=True,
            ).order_by("first_name", "last_name", "email")
        else:
            self.fields["id_company"].queryset = Company.objects.all().order_by("name")
            self.fields["id_assigned_user"].queryset = UserAccount.objects.select_related(
                "id_company"
            ).filter(is_active=True).order_by("id_company__name", "first_name", "email")

        self.fields["id_assigned_user"].required = False

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()

        if not name:
            raise forms.ValidationError("Lead name is required.")

        return name

    def clean(self):
        cleaned_data = super().clean()

        company = cleaned_data.get("id_company")
        assigned_user = cleaned_data.get("id_assigned_user")

        if (
            self.request_user
            and not self.request_user.is_superuser
            and company
            and company.id_company != self.request_user.id_company_id
        ):
            raise forms.ValidationError("You can only manage leads for your company.")

        if assigned_user and company and assigned_user.id_company_id != company.id_company:
            raise forms.ValidationError("Assigned user must belong to the same company.")

        return cleaned_data

    def save(self, commit=True):
        lead = super().save(commit=False)

        if self.request_user and not self.request_user.is_superuser:
            lead.id_company = self.request_user.id_company

        if commit:
            lead.save()

        return lead
