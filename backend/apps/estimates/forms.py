from decimal import Decimal, InvalidOperation

from django import forms
from django.forms import inlineformset_factory

from apps.clients.models import Client
from apps.companies.models import Company
from apps.inspections.models import InspectionAssignment
from apps.projects.models import Project

from .models import Estimate, EstimateItem


def format_client_label(client):
    code = getattr(client, "client_code", None) or f"CL_{getattr(client, 'id_client', 0):06d}"
    name = getattr(client, "name", "") or "No client name"
    phone = getattr(client, "phone", "") or ""
    return " - ".join([part for part in [code, name, phone] if part])


def clean_decimal_value(value, default="0.00"):
    if value in [None, ""]:
        return Decimal(default)

    if isinstance(value, Decimal):
        return value

    value = str(value).strip().replace(",", ".")

    try:
        return Decimal(value)
    except InvalidOperation:
        raise forms.ValidationError("Enter a valid number.")


class EstimateForm(forms.ModelForm):
    project_name = forms.CharField(
        required=False,
        label="Project Name",
        widget=forms.TextInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Project name or job name",
            }
        ),
    )

    project_address = forms.CharField(
        required=False,
        label="Project Address",
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 2,
                "placeholder": "Project address",
            }
        ),
    )

    client_billing_address = forms.CharField(
        required=False,
        label="Client Billing Address",
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 2,
                "placeholder": "Client billing address",
            }
        ),
    )

    description = forms.CharField(
        required=False,
        label="Estimate Description",
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 3,
                "placeholder": "Brief estimate description, scope or notes",
            }
        ),
    )

    class Meta:
        model = Estimate
        fields = [
            "id_company",
            "id_client",
            "id_project",
            "client_billing_name",
            "client_billing_email",
            "client_billing_phone",
            "client_billing_address",
            "project_name",
            "project_address",
            "description",
            "pdf_header_dark",
            "validity_days",
            "tax_enabled",
            "tax_rate",
            "discount_amount",
        ]

        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_client": forms.Select(attrs={"class": "crm_input"}),
            "id_project": forms.Select(attrs={"class": "crm_input"}),
            "client_billing_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Client or billing name",
                }
            ),
            "client_billing_email": forms.EmailInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "billing@example.com",
                }
            ),
            "client_billing_phone": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Numbers only",
                    "inputmode": "numeric",
                    "pattern": "[0-9]*",
                    "title": "Only numbers are allowed.",
                    "autocomplete": "tel",
                }
            ),
            "pdf_header_dark": forms.CheckboxInput(),
            "validity_days": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "min": "1",
                    "step": "1",
                }
            ),
            "tax_enabled": forms.CheckboxInput(),
            "tax_rate": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "inputmode": "decimal",
                    "placeholder": "0.00",
                }
            ),
            "discount_amount": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "inputmode": "decimal",
                    "placeholder": "0.00",
                }
            ),
        }

    def __init__(self, *args, user=None, project=None, inspection=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user
        self.project = project
        self.inspection = inspection

        self.fields["client_billing_name"].required = False
        self.fields["client_billing_email"].required = False
        self.fields["client_billing_phone"].required = False
        self.fields["client_billing_address"].required = False
        self.fields["id_client"].label_from_instance = format_client_label
        self.fields["id_project"].required = False
        self.fields["id_project"].empty_label = "No existing project"

        def project_label(obj):
            code = obj.project_code or f"P_{obj.id_project:05d}"
            name = obj.name or "No project name"
            return f"{code} - {name}"

        self.fields["id_project"].label_from_instance = project_label

        if inspection:
            client = inspection.client
            company = client.id_company
            self.fields["id_company"].queryset = Company.objects.filter(pk=company.pk)
            self.fields["id_company"].initial = company
            self.fields["id_company"].disabled = True

            self.fields["id_client"].queryset = Client.objects.filter(pk=client.pk)
            self.fields["id_client"].initial = client
            self.fields["id_client"].disabled = True

            self.fields["id_project"].queryset = Project.objects.none()
            self.fields["id_project"].required = False
            self.fields["id_project"].disabled = True

            if not self.is_bound:
                self.fields["client_billing_name"].initial = client.name or ""
                self.fields["client_billing_email"].initial = client.email or ""
                self.fields["client_billing_phone"].initial = client.phone or ""
                self.fields["client_billing_address"].initial = client.address or ""
                self.fields["project_name"].initial = f"Inspection - {client.name}"
                self.fields["project_address"].initial = client.address or ""
                inspection_notes = (inspection.inspection_notes or inspection.notes or "").strip()
                self.fields["description"].initial = inspection_notes

        def selected_client_id():
            if self.is_bound:
                raw_client_id = self.data.get(self.add_prefix("id_client"))
                if raw_client_id:
                    return raw_client_id

            if self.instance and getattr(self.instance, "id_client_id", None):
                return self.instance.id_client_id

            if project and getattr(project, "id_client_id", None):
                return project.id_client_id

            return None

        if inspection:
            return

        if project:
            self.fields["id_company"].queryset = Company.objects.filter(
                id_company=project.id_company_id
            )
            self.fields["id_company"].initial = project.id_company
            self.fields["id_company"].disabled = True

            self.fields["id_client"].queryset = Client.objects.filter(
                id_client=project.id_client_id
            )
            self.fields["id_client"].initial = project.id_client
            self.fields["id_client"].disabled = True

            self.fields["id_project"].queryset = Project.objects.filter(
                id_project=project.id_project
            )
            self.fields["id_project"].initial = project
            self.fields["id_project"].disabled = True

            self.fields["project_name"].initial = getattr(project, "name", "") or ""
            self.fields["project_name"].widget.attrs["readonly"] = "readonly"
            self.fields["project_name"].widget.attrs["data-project-locked"] = "1"

            if not self.initial.get("project_address"):
                self.fields["project_address"].initial = getattr(project, "project_address", "") or ""

            if not self.initial.get("description"):
                self.fields["description"].initial = getattr(project, "description", "") or ""

            return

        if user and getattr(user, "id_company_id", None):
            company_id = user.id_company_id

            self.fields["id_company"].queryset = Company.objects.filter(
                id_company=company_id
            )
            self.fields["id_company"].initial = user.id_company
            self.fields["id_company"].disabled = True

            self.fields["id_client"].queryset = Client.objects.filter(
                id_company=company_id
            ).order_by("name")

            client_id = selected_client_id()

            if client_id:
                self.fields["id_project"].queryset = Project.objects.filter(
                    id_company=company_id,
                    id_client_id=client_id,
                ).order_by("-created_at")
            else:
                self.fields["id_project"].queryset = Project.objects.none()
        else:
            self.fields["id_company"].queryset = Company.objects.none()
            self.fields["id_client"].queryset = Client.objects.none()
            self.fields["id_project"].queryset = Project.objects.none()

        current_project = None

        if self.instance and getattr(self.instance, "id_project_id", None):
            current_project = self.instance.id_project
        elif self.is_bound:
            raw_project_id = self.data.get(self.add_prefix("id_project"))
            if raw_project_id:
                try:
                    current_project = Project.objects.get(
                        id_project=raw_project_id,
                        id_company_id=getattr(user, "id_company_id", None),
                    )
                except (Project.DoesNotExist, ValueError, TypeError):
                    current_project = None

        if current_project:
            self.fields["project_name"].widget.attrs["readonly"] = "readonly"
            self.fields["project_name"].widget.attrs["data-project-locked"] = "1"

            if not self.is_bound:
                self.fields["project_name"].initial = current_project.name or ""

                if not self.initial.get("project_address"):
                    self.fields["project_address"].initial = current_project.project_address or ""

                if not self.initial.get("description"):
                    self.fields["description"].initial = current_project.description or ""

    def clean_discount_amount(self):
        discount_amount = clean_decimal_value(
            self.cleaned_data.get("discount_amount"),
            default="0.00",
        )

        if discount_amount < Decimal("0.00"):
            raise forms.ValidationError("Discount amount cannot be negative.")

        return discount_amount

    def clean_tax_rate(self):
        tax_rate = clean_decimal_value(
            self.cleaned_data.get("tax_rate"),
            default="0.00",
        )

        if tax_rate < Decimal("0.00"):
            raise forms.ValidationError("Tax rate cannot be negative.")

        if tax_rate > Decimal("100.00"):
            raise forms.ValidationError("Tax rate cannot be greater than 100%.")

        return tax_rate

    def clean_client_billing_email(self):
        email = (self.cleaned_data.get("client_billing_email") or "").strip()

        if not email:
            return ""

        return email.lower()

    def clean_client_billing_phone(self):
        phone = (self.cleaned_data.get("client_billing_phone") or "").strip()

        if not phone:
            return ""

        if not phone.isdigit():
            raise forms.ValidationError("Billing phone must contain numbers only.")

        return phone

    def clean_validity_days(self):
        validity_days = self.cleaned_data.get("validity_days") or 15

        if validity_days <= 0:
            raise forms.ValidationError("Validity days must be greater than 0.")

        return validity_days

    def clean_project_name(self):
        project_name = (self.cleaned_data.get("project_name") or "").strip()

        if project_name:
            return project_name

        if self.project:
            return getattr(self.project, "name", "") or ""

        if self.inspection:
            return f"Inspection - {self.inspection.client_name}"

        raw_project_id = self.data.get(self.add_prefix("id_project")) if self.is_bound else None

        if raw_project_id:
            return ""

        return project_name

    def clean(self):
        cleaned_data = super().clean()

        company = cleaned_data.get("id_company")
        client = cleaned_data.get("id_client")
        project = cleaned_data.get("id_project") or self.project

        if self.inspection:
            cleaned_data["id_company"] = self.inspection.id_company
            cleaned_data["id_client"] = self.inspection.client
            cleaned_data["id_project"] = None
            company = self.inspection.id_company
            client = self.inspection.client
            project = None

        if self.project:
            cleaned_data["id_company"] = self.project.id_company
            cleaned_data["id_client"] = self.project.id_client
            cleaned_data["id_project"] = self.project

            company = self.project.id_company
            client = self.project.id_client
            project = self.project

        if self.request_user and getattr(self.request_user, "id_company_id", None):
            cleaned_data["id_company"] = self.request_user.id_company
            company = self.request_user.id_company

        if not company:
            raise forms.ValidationError("Company is required for this estimate.")

        if not client:
            raise forms.ValidationError("Client is required for this estimate.")

        if client and company and client.id_company_id != company.id_company:
            raise forms.ValidationError("Client must belong to the selected company.")

        if project and company and project.id_company_id != company.id_company:
            raise forms.ValidationError("Project must belong to the selected company.")

        if project and client and project.id_client_id != client.id_client:
            raise forms.ValidationError("Project must belong to the selected client.")

        if project:
            # Existing project selected: keep the official project name locked,
            # but allow the estimate snapshot fields below to be edited so the
            # user can later apply only those changes back to the project.
            cleaned_data["project_name"] = project.name or cleaned_data.get("project_name")

            if not (cleaned_data.get("project_address") or "").strip():
                cleaned_data["project_address"] = project.project_address or ""

            if not (cleaned_data.get("description") or "").strip() and project.description:
                cleaned_data["description"] = project.description
        elif not (cleaned_data.get("project_name") or "").strip():
            raise forms.ValidationError("Project name is required when no existing project is selected.")

        return cleaned_data

    def save(self, commit=True):
        estimate = super().save(commit=False)

        if self.inspection:
            estimate.id_company = self.inspection.id_company
            estimate.id_client = self.inspection.client
            estimate.id_project = None
            estimate.id_inspection_assignment = self.inspection

        if self.project:
            estimate.id_company = self.project.id_company
            estimate.id_client = self.project.id_client
            estimate.id_project = self.project

        if self.request_user and getattr(self.request_user, "id_company_id", None):
            estimate.id_company = self.request_user.id_company

        if commit:
            estimate.save()

        return estimate


class EstimateItemForm(forms.ModelForm):
    class Meta:
        model = EstimateItem
        fields = [
            "description",
            "photo",
            "quantity",
            "unit_price",
        ]

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 2,
                    "class": "crm_input item-description",
                    "placeholder": "Service, material or labor description",
                }
            ),
            "photo": forms.ClearableFileInput(
                attrs={
                    "class": "crm_input item-photo",
                    "accept": "image/*",
                }
            ),
            "quantity": forms.TextInput(
                attrs={
                    "class": "crm_input qty-field",
                    "inputmode": "decimal",
                    "placeholder": "1.00",
                }
            ),
            "unit_price": forms.TextInput(
                attrs={
                    "class": "crm_input price-field",
                    "inputmode": "decimal",
                    "placeholder": "0.00",
                }
            ),
        }

    def clean_quantity(self):
        quantity = clean_decimal_value(
            self.cleaned_data.get("quantity"),
            default="0.00",
        )

        if quantity <= Decimal("0.00"):
            raise forms.ValidationError("Quantity must be greater than 0.")

        return quantity

    def clean_unit_price(self):
        unit_price = clean_decimal_value(
            self.cleaned_data.get("unit_price"),
            default="0.00",
        )

        if unit_price < Decimal("0.00"):
            raise forms.ValidationError("Unit price cannot be negative.")

        return unit_price


EstimateItemFormSet = inlineformset_factory(
    Estimate,
    EstimateItem,
    form=EstimateItemForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class EstimateSendEmailForm(forms.Form):
    recipient_email = forms.EmailField(
        label="Recipient Email",
        widget=forms.EmailInput(
            attrs={
                "class": "crm_input",
                "placeholder": "client@example.com",
            }
        ),
    )

    subject = forms.CharField(
        required=False,
        label="Subject",
        widget=forms.TextInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Estimate subject",
            }
        ),
    )

    message = forms.CharField(
        required=False,
        label="Message",
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 5,
                "placeholder": "Optional message for the client",
            }
        ),
    )
