from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from apps.platform_subscriptions.models import PlatformSubscription

from .models import PlatformDocument, PlatformDocumentItem


class PlatformDocumentForm(forms.ModelForm):
    class Meta:
        model = PlatformDocument
        fields = [
            "id_company",
            "id_subscription",
            "document_type",
            "status",
            "issue_date",
            "due_date",
            "tax_rate",
            "discount_amount",
            "notes",
            "terms",
            "footer",
        ]
        labels = {
            "id_company": "Company",
            "id_subscription": "Subscription",
            "document_type": "Document Type",
            "status": "Status",
            "issue_date": "Issue Date",
            "due_date": "Due Date",
            "tax_rate": "Tax Rate (%)",
            "discount_amount": "Discount Amount",
            "notes": "Internal Notes",
            "terms": "Terms",
            "footer": "Footer",
        }
        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_subscription": forms.Select(attrs={"class": "crm_input"}),
            "document_type": forms.Select(attrs={"class": "crm_input"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "issue_date": forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
            "due_date": forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
            "tax_rate": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),
            "discount_amount": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                    "placeholder": "Internal notes for CEO MARKETING team.",
                }
            ),
            "terms": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                    "placeholder": "Payment terms, renewal conditions or SaaS agreement notes.",
                }
            ),
            "footer": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                    "placeholder": "Footer message displayed on the document.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["issue_date"].initial = timezone.localdate()

        company_id = None

        if self.data.get("id_company"):
            company_id = self.data.get("id_company")
        elif self.instance and self.instance.pk and self.instance.id_company_id:
            company_id = self.instance.id_company_id

        if company_id:
            self.fields["id_subscription"].queryset = PlatformSubscription.objects.filter(
                id_company_id=company_id
            ).select_related("id_company", "id_plan")
        else:
            self.fields["id_subscription"].queryset = PlatformSubscription.objects.select_related(
                "id_company",
                "id_plan",
            ).all()

        self.fields["id_subscription"].required = False

    def clean(self):
        cleaned_data = super().clean()

        issue_date = cleaned_data.get("issue_date")
        due_date = cleaned_data.get("due_date")
        company = cleaned_data.get("id_company")
        subscription = cleaned_data.get("id_subscription")

        if due_date and issue_date and due_date < issue_date:
            self.add_error("due_date", "Due date cannot be before issue date.")

        if company and subscription and subscription.id_company_id != company.id_company:
            self.add_error("id_subscription", "The selected subscription does not belong to this company.")

        return cleaned_data


class PlatformDocumentItemForm(forms.ModelForm):
    class Meta:
        model = PlatformDocumentItem
        fields = [
            "description",
            "quantity",
            "unit_price",
        ]
        labels = {
            "description": "Description",
            "quantity": "Quantity",
            "unit_price": "Unit Price",
        }
        widgets = {
            "description": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "CRM monthly subscription, setup fee, renewal fee",
                }
            ),
            "quantity": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "1",
                }
            ),
            "unit_price": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "99.00",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["description"].required = False
        self.fields["quantity"].required = False
        self.fields["unit_price"].required = False

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("DELETE"):
            return cleaned_data

        description = (cleaned_data.get("description") or "").strip()
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")

        is_empty_row = not description and quantity is None and unit_price is None

        if is_empty_row:
            return cleaned_data

        if not description:
            self.add_error("description", "Description is required.")

        if quantity is None:
            self.add_error("quantity", "Quantity is required.")
        elif quantity <= 0:
            self.add_error("quantity", "Quantity must be greater than zero.")

        if unit_price is None:
            self.add_error("unit_price", "Unit price is required.")
        elif unit_price < 0:
            self.add_error("unit_price", "Unit price cannot be negative.")

        cleaned_data["description"] = description

        return cleaned_data


PlatformDocumentItemFormSet = inlineformset_factory(
    PlatformDocument,
    PlatformDocumentItem,
    form=PlatformDocumentItemForm,
    extra=1,
    can_delete=True,
    can_delete_extra=True,
    min_num=0,
    validate_min=False,
)

class PlatformDocumentEmailForm(forms.Form):
    recipient_email = forms.EmailField(
        label="Recipient Email",
        widget=forms.EmailInput(
            attrs={
                "class": "crm_input",
                "placeholder": "owner@company.com",
            }
        ),
    )

    subject = forms.CharField(
        label="Subject",
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "crm_input",
                "placeholder": "CEO Marketing USA document",
            }
        ),
    )

    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 6,
                "placeholder": "Write the message that will appear before the document summary.",
            }
        ),
    )