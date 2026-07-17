from django import forms
from django.utils.text import slugify

from .models import PlatformPlan
from .models.choices import BILLING_CUSTOM


class PlatformPlanForm(forms.ModelForm):
    class Meta:
        model = PlatformPlan
        fields = [
            "name",
            "code",
            "description",
            "price",
            "billing_cycle",
            "custom_cycle_count",
            "custom_cycle_unit",
            "max_users",
            "status",
        ]
        labels = {
            "name": "Plan Name",
            "code": "Plan Code",
            "description": "Description",
            "price": "Price",
            "billing_cycle": "Billing Cycle",
            "custom_cycle_count": "Custom Cycle Number",
            "custom_cycle_unit": "Custom Cycle Unit",
            "max_users": "Maximum Users",
            "status": "Status",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Business Monthly",
                    "autocomplete": "off",
                }
            ),
            "code": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "business-monthly",
                    "readonly": "readonly",
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Short internal description for this SaaS plan.",
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "99.00",
                }
            ),
            "billing_cycle": forms.Select(
                attrs={
                    "class": "crm_input",
                }
            ),
            "custom_cycle_count": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "min": "1",
                    "placeholder": "Example: 15, 45, 6",
                }
            ),
            "custom_cycle_unit": forms.Select(
                attrs={
                    "class": "crm_input",
                }
            ),
            "max_users": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "min": "1",
                    "placeholder": "5",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "crm_input",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["code"].required = False
        self.fields["code"].help_text = "Generated automatically from the plan name."

        if self.instance and self.instance.pk and self.instance.name:
            self.fields["code"].initial = slugify(self.instance.name)

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()

        if not name:
            raise forms.ValidationError("Plan name is required.")

        queryset = PlatformPlan.objects.filter(name__iexact=name)

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError("A plan with this name already exists.")

        return name

    def clean_code(self):
        name = self.cleaned_data.get("name", "").strip()
        code = self.cleaned_data.get("code", "").strip()

        if not code:
            code = name

        code = slugify(code)

        if not code:
            raise forms.ValidationError("Plan code could not be generated. Enter a valid plan name.")

        queryset = PlatformPlan.objects.filter(code=code)

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError("A plan with this generated code already exists.")

        return code

    def clean_max_users(self):
        max_users = self.cleaned_data.get("max_users")

        if max_users is None or max_users < 1:
            raise forms.ValidationError("Maximum users must be greater than zero.")

        return max_users

    def clean(self):
        cleaned_data = super().clean()

        billing_cycle = cleaned_data.get("billing_cycle")
        custom_cycle_count = cleaned_data.get("custom_cycle_count")
        custom_cycle_unit = cleaned_data.get("custom_cycle_unit")

        if billing_cycle == BILLING_CUSTOM:
            if not custom_cycle_count:
                self.add_error(
                    "custom_cycle_count",
                    "Enter the custom billing cycle number.",
                )

            if custom_cycle_count and custom_cycle_count < 1:
                self.add_error(
                    "custom_cycle_count",
                    "Custom cycle number must be greater than zero.",
                )

            if not custom_cycle_unit:
                self.add_error(
                    "custom_cycle_unit",
                    "Select the custom billing cycle unit.",
                )
        else:
            cleaned_data["custom_cycle_count"] = None
            cleaned_data["custom_cycle_unit"] = None

        return cleaned_data