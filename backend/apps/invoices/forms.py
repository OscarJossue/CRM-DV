from decimal import Decimal, InvalidOperation

from django import forms
from django.forms import inlineformset_factory

from apps.clients.models import Client
from apps.companies.models import Company
from apps.estimates.models import Estimate
from apps.projects.models import Project

from .models import Invoice, InvoiceItem


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


def get_client_billing_name(client):
    if not client:
        return ""

    return getattr(client, "name", "") or ""


def get_client_billing_email(client):
    if not client:
        return ""

    for field_name in ["email", "client_email", "billing_email", "contact_email"]:
        value = getattr(client, field_name, None)

        if value:
            return value

    return ""


def get_client_billing_dni(client):
    if not client:
        return ""

    for field_name in ["dni", "tax_id", "identification_number", "document_number"]:
        value = getattr(client, field_name, None)
        if value:
            return str(value).strip()

    return ""


def get_client_billing_phone(client):
    if not client:
        return ""

    for field_name in ["phone", "client_phone", "billing_phone", "contact_phone"]:
        value = getattr(client, field_name, None)

        if value:
            return value

    return ""


def get_client_billing_address(client):
    if not client:
        return ""

    address_parts = []

    address = getattr(client, "address", None)
    city = getattr(client, "city", None)
    state = getattr(client, "state", None)

    if address:
        address_parts.append(str(address).strip())

    city_state = ", ".join(
        [str(value).strip() for value in [city, state] if value]
    )

    if city_state:
        address_parts.append(city_state)

    return "\n".join(address_parts)


def get_project_name(project):
    if not project:
        return ""

    for field_name in ["name", "project_name", "title"]:
        value = getattr(project, field_name, None)

        if value:
            return str(value).strip()

    return ""


def get_project_address(project):
    if not project:
        return ""

    for field_name in ["address", "project_address", "location"]:
        value = getattr(project, field_name, None)

        if value:
            return str(value).strip()

    return ""


def get_company_tax_enabled(company):
    if not company:
        return False

    for field_name in [
        "tax_enabled",
        "invoice_tax_enabled",
        "default_tax_enabled",
        "enable_tax",
    ]:
        if hasattr(company, field_name):
            return bool(getattr(company, field_name))

    return False


def get_company_tax_rate(company):
    if not company:
        return Decimal("0.00")

    for field_name in [
        "tax_rate",
        "invoice_tax_rate",
        "default_tax_rate",
    ]:
        if hasattr(company, field_name):
            value = getattr(company, field_name)

            if value not in [None, ""]:
                return clean_decimal_value(value, default="0.00")

    return Decimal("0.00")


class ClientSelect(forms.Select):
    """Client selector with safe billing metadata for instant form prefilling."""

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )

        try:
            client = value.instance
            option["attrs"]["data-billing-name"] = get_client_billing_name(client)
            option["attrs"]["data-billing-email"] = get_client_billing_email(client)
            option["attrs"]["data-billing-phone"] = get_client_billing_phone(client)
            option["attrs"]["data-billing-dni"] = get_client_billing_dni(client)
            option["attrs"]["data-billing-address"] = get_client_billing_address(client)
        except Exception:
            pass

        return option


class ProjectSelect(forms.Select):
    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )

        try:
            project = value.instance
            option["attrs"]["data-client"] = str(project.id_client_id or "")
            option["attrs"]["data-company"] = str(project.id_company_id or "")
            option["attrs"]["data-project-name"] = get_project_name(project)
            option["attrs"]["data-project-address"] = get_project_address(project)
            option["attrs"]["data-project-description"] = getattr(project, "description", "") or ""
            option["attrs"]["data-project-contract-amount"] = str(getattr(project, "contract_amount", "") or "0.00")
        except Exception:
            pass

        return option


class InvoiceForm(forms.ModelForm):
    description = forms.CharField(
        required=False,
        label="Invoice Description",
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 3,
                "placeholder": "Brief invoice description, scope or notes",
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


    class Meta:
        model = Invoice
        fields = [
            "id_company",
            "id_client",
            "id_project",
            "id_estimate",
            "client_billing_name",
            "client_billing_email",
            "client_billing_phone",
            "client_billing_dni",
            "client_billing_address",
            "description",
            "issue_date",
            "due_date",
            "tax_enabled",
            "tax_rate",
            "discount_amount",
        ]

        widgets = {
            "id_company": forms.Select(attrs={"class": "crm_input"}),
            "id_client": ClientSelect(attrs={"class": "crm_input"}),
            "id_project": ProjectSelect(attrs={"class": "crm_input"}),
            "id_estimate": forms.HiddenInput(),

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
                    "placeholder": "Client phone",
                }
            ),
            "client_billing_dni": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "DNI / Tax ID (optional)",
                    "autocomplete": "off",
                }
            ),
            "issue_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "crm_input invoice-date-input",
                    "type": "date",
                }
            ),
            "due_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "crm_input invoice-date-input",
                    "type": "date",
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

    def __init__(self, *args, user=None, project=None, estimate=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user
        self.project = project
        self.estimate = estimate

        self.fields["id_client"].label_from_instance = format_client_label
        self.fields["id_project"].required = True
        self.fields["id_project"].empty_label = "Select project"
        self.fields["id_estimate"].required = False
        self.fields["tax_enabled"].required = False
        self.fields["tax_rate"].required = False
        self.fields["client_billing_dni"].required = False
        self.fields["issue_date"].input_formats = ["%Y-%m-%d"]
        self.fields["due_date"].input_formats = ["%Y-%m-%d"]

        # Important: when the invoice comes from an estimate, client and project
        # must still be editable. They are only prefilled.
        self.fields["id_client"].disabled = False
        self.fields["id_project"].disabled = False
        self.fields["id_estimate"].disabled = False

        if estimate:
            self.fields["id_company"].queryset = Company.objects.filter(
                id_company=estimate.id_company_id
            )
            self.fields["id_company"].initial = estimate.id_company
            self.fields["id_company"].disabled = True

            self.fields["id_client"].queryset = Client.objects.filter(
                id_company=estimate.id_company_id
            ).order_by("name")
            self.fields["id_client"].initial = estimate.id_client
            self.fields["id_client"].disabled = False

            self.fields["id_project"].queryset = Project.objects.filter(
                id_company=estimate.id_company_id
            ).select_related(
                "id_client",
                "id_company",
            ).order_by("-created_at")
            self.filter_projects_by_selected_client()
            self.fields["id_project"].disabled = False

            if estimate.id_project_id:
                self.fields["id_project"].initial = estimate.id_project
            else:
                self.fields["id_project"].initial = None

            self.fields["id_estimate"].queryset = Estimate.objects.filter(
                id_estimate=estimate.id_estimate
            )
            self.fields["id_estimate"].initial = estimate
            self.fields["id_estimate"].disabled = False

            self.fields["tax_enabled"].initial = estimate.tax_enabled
            self.fields["tax_rate"].initial = estimate.tax_rate
            self.apply_client_billing_initials(estimate.id_client)

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

            self.fields["id_estimate"].queryset = Estimate.objects.none()

            self.fields["tax_enabled"].initial = get_company_tax_enabled(
                project.id_company
            )
            self.fields["tax_rate"].initial = get_company_tax_rate(project.id_company)
            self.apply_client_billing_initials(project.id_client)

            if not self.is_bound:
                if not self.initial.get("description"):
                    project_description = getattr(project, "description", None) or ""
                    if project_description:
                        self.initial["description"] = project_description
                        self.fields["description"].initial = project_description

            return

        if user and not user.is_superuser:
            self.fields["id_company"].queryset = Company.objects.filter(
                id_company=user.id_company_id
            )
            self.fields["id_company"].initial = user.id_company
            self.fields["id_company"].disabled = True

            self.fields["id_client"].queryset = Client.objects.filter(
                id_company=user.id_company_id
            ).order_by("name")
            self.fields["id_client"].disabled = False

            self.fields["id_project"].queryset = Project.objects.filter(
                id_company=user.id_company_id
            ).select_related(
                "id_client",
                "id_company",
            ).order_by("-created_at")
            self.filter_projects_by_selected_client()
            self.fields["id_project"].disabled = False

            self.fields["id_estimate"].queryset = Estimate.objects.filter(
                id_company=user.id_company_id,
                status="approved",
            ).order_by("-issue_date", "-id_estimate")

            self.fields["tax_enabled"].initial = get_company_tax_enabled(
                user.id_company
            )
            self.fields["tax_rate"].initial = get_company_tax_rate(user.id_company)

        else:
            self.fields["id_company"].queryset = Company.objects.all().order_by("name")

            self.fields["id_client"].queryset = Client.objects.select_related(
                "id_company"
            ).all().order_by("id_company__name", "name")
            self.fields["id_client"].disabled = False

            self.fields["id_project"].queryset = Project.objects.select_related(
                "id_company",
                "id_client",
            ).all().order_by("-created_at")
            self.filter_projects_by_selected_client()
            self.fields["id_project"].disabled = False

            self.fields["id_estimate"].queryset = Estimate.objects.select_related(
                "id_company",
                "id_client",
                "id_project",
            ).filter(status="approved").order_by("-issue_date", "-id_estimate")

        self.apply_client_billing_initials(self.get_selected_client_instance())

    def apply_client_billing_initials(self, client):
        """Prefill billing data on first render while keeping every field editable."""
        if self.is_bound or not client:
            return

        values = {
            "client_billing_name": get_client_billing_name(client),
            "client_billing_email": get_client_billing_email(client),
            "client_billing_phone": get_client_billing_phone(client),
            "client_billing_dni": get_client_billing_dni(client),
            "client_billing_address": get_client_billing_address(client),
        }

        for field_name, value in values.items():
            current_value = self.initial.get(field_name)
            if current_value in [None, ""]:
                self.initial[field_name] = value
                self.fields[field_name].initial = value

    def get_selected_client_instance(self):
        selected_client_id = self.get_selected_client_id()
        if not selected_client_id:
            return None

        try:
            return self.fields["id_client"].queryset.filter(
                id_client=selected_client_id,
            ).first()
        except Exception:
            return None

    def get_selected_client_id(self):
        if self.data:
            return self.data.get(self.add_prefix("id_client")) or self.data.get("id_client") or None

        if self.project:
            return self.project.id_client_id

        if self.estimate and self.estimate.id_client_id:
            return self.estimate.id_client_id

        if self.instance and self.instance.pk and self.instance.id_client_id:
            return self.instance.id_client_id

        initial_client = self.initial.get("id_client") if self.initial else None
        return getattr(initial_client, "id_client", initial_client) or None

    def filter_projects_by_selected_client(self):
        selected_client_id = self.get_selected_client_id()

        if selected_client_id:
            self.fields["id_project"].queryset = self.fields["id_project"].queryset.filter(
                id_client_id=selected_client_id,
            )

    def clean_client_billing_dni(self):
        return (self.cleaned_data.get("client_billing_dni") or "").strip()

    def clean_client_billing_phone(self):
        phone = (self.cleaned_data.get("client_billing_phone") or "").strip()

        if phone and not phone.isdigit():
            raise forms.ValidationError("Billing phone must contain numbers only.")

        return phone

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

    def clean(self):
        cleaned_data = super().clean()

        company = cleaned_data.get("id_company")
        client = cleaned_data.get("id_client")
        project = cleaned_data.get("id_project") or self.project
        estimate = cleaned_data.get("id_estimate") or self.estimate

        if self.project:
            cleaned_data["id_company"] = self.project.id_company
            cleaned_data["id_client"] = self.project.id_client
            cleaned_data["id_project"] = self.project

            company = self.project.id_company
            client = self.project.id_client
            project = self.project

        if self.request_user and not self.request_user.is_superuser:
            cleaned_data["id_company"] = self.request_user.id_company
            company = self.request_user.id_company

        if self.estimate:
            cleaned_data["id_estimate"] = self.estimate
            estimate = self.estimate

            if not company:
                cleaned_data["id_company"] = self.estimate.id_company
                company = self.estimate.id_company

        if not company:
            raise forms.ValidationError("Company is required for this invoice.")

        if not client:
            raise forms.ValidationError("Client is required for this invoice.")

        if not project:
            raise forms.ValidationError(
                "Invoice project is required. Select an existing project before generating the invoice."
            )

        if (
            self.request_user
            and not self.request_user.is_superuser
            and company.id_company != self.request_user.id_company_id
        ):
            raise forms.ValidationError("You can only manage invoices for your company.")

        if client and company and client.id_company_id != company.id_company:
            raise forms.ValidationError("Client must belong to the selected company.")

        if project and company and project.id_company_id != company.id_company:
            raise forms.ValidationError("Project must belong to the selected company.")

        if project and client and project.id_client_id != client.id_client:
            raise forms.ValidationError("Project must belong to the selected client.")

        if estimate:
            if estimate.status != "approved":
                raise forms.ValidationError(
                    "Only approved estimates can generate invoices."
                )

            if estimate.id_company_id != company.id_company:
                raise forms.ValidationError(
                    "Estimate must belong to the selected company."
                )

        # Tax is editable on invoices. Defaults are set in __init__, but user changes are respected.
        cleaned_data["tax_enabled"] = bool(cleaned_data.get("tax_enabled"))
        cleaned_data["tax_rate"] = clean_decimal_value(cleaned_data.get("tax_rate"), default="0.00")

        if not cleaned_data.get("client_billing_name"):
            cleaned_data["client_billing_name"] = get_client_billing_name(client)

        if not cleaned_data.get("client_billing_email"):
            cleaned_data["client_billing_email"] = get_client_billing_email(client)

        if not cleaned_data.get("client_billing_phone"):
            cleaned_data["client_billing_phone"] = get_client_billing_phone(client)

        if not cleaned_data.get("client_billing_dni"):
            cleaned_data["client_billing_dni"] = get_client_billing_dni(client)

        if not cleaned_data.get("client_billing_address"):
            cleaned_data["client_billing_address"] = get_client_billing_address(client)

        return cleaned_data

    def save(self, commit=True):
        invoice = super().save(commit=False)

        company = self.cleaned_data.get("id_company")
        client = self.cleaned_data.get("id_client")
        project = self.cleaned_data.get("id_project")
        estimate = self.cleaned_data.get("id_estimate")

        if self.project:
            company = self.project.id_company
            client = self.project.id_client
            project = self.project

        if self.request_user and not self.request_user.is_superuser:
            company = self.request_user.id_company

        if company:
            invoice.id_company = company

        if client:
            invoice.id_client = client

        if project:
            invoice.id_project = project
            invoice.project_name = get_project_name(project)
            invoice.project_address = get_project_address(project)

        if estimate:
            invoice.id_estimate = estimate

        invoice.client_billing_name = (
            self.cleaned_data.get("client_billing_name")
            or get_client_billing_name(client)
        )
        invoice.client_billing_email = (
            self.cleaned_data.get("client_billing_email")
            or get_client_billing_email(client)
        )
        invoice.client_billing_phone = (
            self.cleaned_data.get("client_billing_phone")
            or get_client_billing_phone(client)
        )
        invoice.client_billing_dni = (
            self.cleaned_data.get("client_billing_dni")
            or get_client_billing_dni(client)
        )
        invoice.client_billing_address = (
            self.cleaned_data.get("client_billing_address")
            or get_client_billing_address(client)
        )

        invoice.tax_enabled = bool(self.cleaned_data.get("tax_enabled"))
        invoice.tax_rate = clean_decimal_value(self.cleaned_data.get("tax_rate"), default="0.00")

        if commit:
            invoice.save()

        return invoice


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = [
            "description",
            "quantity",
            "unit_price",
        ]

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 2,
                    "class": "crm_input item-description",
                    "placeholder": "Service or material description",
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


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class InvoiceSendEmailForm(forms.Form):
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
                "placeholder": "Invoice subject",
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