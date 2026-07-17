from django import forms
from django.utils import timezone

from apps.companies.models import Company
from apps.platform_plans.models import PlatformPlan
from apps.platform_plans.models.choices import PLAN_STATUS_ACTIVE

from .models import PlatformSubscription
from .models.choices import SUBSCRIPTION_ACTIVE, SUBSCRIPTION_TRIAL


class PlatformSubscriptionForm(forms.ModelForm):
    class Meta:
        model = PlatformSubscription
        fields = [
            "id_company",
            "id_plan",
            "status",
            "start_date",
            "renewal_date",
            "end_date",
            "notes",
        ]
        labels = {
            "id_company": "Company",
            "id_plan": "Plan",
            "status": "Subscription Status",
            "start_date": "Start Date",
            "renewal_date": "Renewal Date",
            "end_date": "End Date",
            "notes": "Internal Notes",
        }
        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_plan": forms.Select(attrs={"class": "crm_input"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "start_date": forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
            "renewal_date": forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Internal subscription notes, renewal agreement, payment reference or support details.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["id_company"].queryset = Company.objects.all().order_by("name")

        plan_queryset = PlatformPlan.objects.filter(status=PLAN_STATUS_ACTIVE)
        if self.instance and self.instance.pk and self.instance.id_plan_id:
            plan_queryset = PlatformPlan.objects.filter(
                status=PLAN_STATUS_ACTIVE
            ) | PlatformPlan.objects.filter(id_plan=self.instance.id_plan_id)
        self.fields["id_plan"].queryset = plan_queryset.distinct().order_by("price", "name")

        if not self.instance or not self.instance.pk:
            today = timezone.localdate()
            self.fields["start_date"].initial = today
            self.fields["status"].initial = SUBSCRIPTION_ACTIVE
        else:
            self.fields["id_company"].disabled = True
            self.fields["id_company"].help_text = (
                "Company cannot be changed after subscription creation. Create a new subscription if needed."
            )

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        renewal_date = cleaned_data.get("renewal_date")
        end_date = cleaned_data.get("end_date")
        status = cleaned_data.get("status")
        today = timezone.localdate()

        if renewal_date and start_date and renewal_date < start_date:
            self.add_error("renewal_date", "Renewal date cannot be before the start date.")

        if end_date and start_date and end_date < start_date:
            self.add_error("end_date", "End date cannot be before the start date.")

        if status in [SUBSCRIPTION_ACTIVE, SUBSCRIPTION_TRIAL]:
            if not renewal_date:
                self.add_error("renewal_date", "Active or trial subscriptions need a renewal date.")
            elif renewal_date < today:
                self.add_error(
                    "renewal_date",
                    "The renewal date is already expired. Use a future renewal date or use Reactivate to create a new billing cycle.",
                )

            if end_date and end_date < today:
                self.add_error("end_date", "Active subscriptions cannot have an expired end date.")

        return cleaned_data
