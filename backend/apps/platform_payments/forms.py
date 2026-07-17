from django import forms
from django.utils import timezone

from apps.platform_subscriptions.models import PlatformSubscription

from .models import PlatformPayment

def get_company_latest_subscription(company):
    if not company:
        return None

    return (
        PlatformSubscription.objects.select_related(
            "id_company",
            "id_plan",
        )
        .filter(id_company=company)
        .order_by("-created_at", "-id_subscription")
        .first()
    )

def get_latest_company_subscription(company):
    if not company:
        return None

    return (
        PlatformSubscription.objects.select_related("id_company", "id_plan")
        .filter(id_company=company)
        .order_by("-created_at", "-id_subscription")
        .first()
    )


class PlatformPaymentForm(forms.ModelForm):
    class Meta:
        model = PlatformPayment
        fields = [
            "id_company",
            "id_subscription",
            "amount",
            "payment_date",
            "status",
            "method",
            "reference",
            "notes",
        ]
        labels = {
            "id_company": "Company",
            "id_subscription": "Subscription",
            "amount": "Amount",
            "payment_date": "Payment Date",
            "status": "Payment Status",
            "method": "Payment Method",
            "reference": "Reference",
            "notes": "Internal Notes",
        }
        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_subscription": forms.Select(attrs={"class": "crm_input"}),
            "amount": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "99.00",
                }
            ),
            "payment_date": forms.DateInput(
                attrs={
                    "class": "crm_input",
                    "type": "date",
                }
            ),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "method": forms.Select(attrs={"class": "crm_input"}),
            "reference": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Bank reference, transaction ID or internal note",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Internal payment notes for CEO MARKETING team.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["payment_date"].initial = timezone.localdate()

        company_id = None

        if self.data.get("id_company"):
            company_id = self.data.get("id_company")
        elif self.instance and self.instance.pk and self.instance.id_company_id:
            company_id = self.instance.id_company_id

        if company_id:
            self.fields["id_subscription"].queryset = (
                PlatformSubscription.objects.filter(id_company_id=company_id)
                .select_related("id_company", "id_plan")
                .order_by("-created_at", "-id_subscription")
            )
        else:
            self.fields["id_subscription"].queryset = (
                PlatformSubscription.objects.select_related(
                    "id_company",
                    "id_plan",
                )
                .all()
                .order_by("-created_at", "-id_subscription")
            )

        self.fields["id_subscription"].required = False
        self.fields["id_subscription"].empty_label = "Use latest company subscription automatically"

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")

        if amount is None or amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")

        return amount

    def clean(self):
        cleaned_data = super().clean()

        company = cleaned_data.get("id_company")
        subscription = cleaned_data.get("id_subscription")

        if company and not subscription:
            subscription = get_company_latest_subscription(company)

            if not subscription:
                self.add_error(
                    "id_subscription",
                    "This company does not have an active subscription.",
                )
                return cleaned_data

            cleaned_data["id_subscription"] = subscription

        if company and subscription:
            if subscription.id_company_id != company.id_company:
                self.add_error(
                    "id_subscription",
                    "The selected subscription does not belong to this company.",
                )

            if (
                cleaned_data.get("amount") in [None, 0]
                and subscription.id_plan
            ):
                cleaned_data["amount"] = subscription.id_plan.price

        return cleaned_data