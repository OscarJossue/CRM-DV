from django import forms

from apps.clients.models import Client
from apps.projects.models import Project

from .models import Contract, ContractEvidence
from .models.choices import CONTRACT_STATUS_DRAFT


def first_value(obj, field_names, default=""):
    """Return the first usable scalar value without evaluating relation managers.

    Some models expose reverse relations with names such as ``notes``. Django
    relation managers are callable objects and are not valid form initial values.
    Ignoring callables/managers keeps legacy records with blank description
    fields from crashing contract creation.
    """
    if obj is None:
        return default

    for field_name in field_names:
        try:
            value = getattr(obj, field_name, None)
        except Exception:
            continue

        if value is None or value == "":
            continue

        if callable(value) or hasattr(value, "get_queryset"):
            continue

        return value

    return default
DEFAULT_PAYMENT_TERMS = """If full payment is not received within thirty (30) days of job completion, all workmanship guarantees shall become void. However, if minor work remains to be done, no more than 2% of the total contract price may be withheld by the customer pending full job completion. After thirty (30) days, a one and one-half (1 1/2) percent interest monthly interest charge will accrue on any outstanding balance. Any costs or expenses incurred to collect any unpaid balance for professional roofing services rendered shall become the responsibility of the customer."""

DEFAULT_CANCELLATION_TERMS = """This proposal/contract may be cancelled by the customer within three (3) business days following the signing hereof by giving written notice. If the customer cancels this agreement after the permitted cancellation period, the customer shall remain responsible for costs, labor, materials, and professional services already rendered or committed."""

DEFAULT_GUARANTEE_TERMS = """The limited guarantee provided in connection with this agreement applies only to workmanship and services expressly stated in this contract. This guarantee does not cover damages caused by storms, weather conditions, improper maintenance, pre-existing conditions, structural issues, or work performed by others. Any warranty or guarantee is subject to full payment and compliance with the terms of this agreement."""

DEFAULT_MISCELLANEOUS_TERMS = """Any dispute arising hereunder shall be governed by the laws of the applicable state. This document constitutes the entire agreement of the parties relating to the professional services described. The parties acknowledge and agree that this proposal/contract correctly states all terms of the agreement and may only be modified in writing signed by both parties."""

class ProjectSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
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
            option["attrs"]["data-project-name"] = first_value(
                project,
                ["name", "project_name", "title"],
            )
            option["attrs"]["data-project-address"] = first_value(
                project,
                ["project_address", "address", "location", "job_address"],
            )
            option["attrs"]["data-project-description"] = first_value(
                project,
                ["description", "project_notes", "scope", "notes"],
            )
        except Exception:
            pass

        return option

class ClientSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
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

            first_name = (getattr(client, "first_name", "") or "").strip()
            last_name = (getattr(client, "last_name", "") or "").strip()
            full_name = " ".join(part for part in [first_name, last_name] if part).strip()

            if not full_name:
                full_name = first_value(client, ["name", "full_name", "legal_name", "commercial_name"])

            option["attrs"]["data-client-name"] = full_name
            option["attrs"]["data-client-phone"] = first_value(client, ["phone", "phone_number", "mobile", "main_phone"])
            option["attrs"]["data-client-alt-phone"] = first_value(client, ["alt_phone", "secondary_phone", "other_phone"])
            option["attrs"]["data-client-email"] = first_value(client, ["email", "contact_email", "billing_email"])
            option["attrs"]["data-client-address"] = first_value(client, ["street_address", "address", "billing_address"])
            option["attrs"]["data-client-city"] = first_value(client, ["city", "billing_city"])
            option["attrs"]["data-client-state"] = first_value(client, ["state", "billing_state"])
            option["attrs"]["data-client-zip"] = first_value(client, ["zip_code", "zipcode", "postal_code", "billing_zip_code"])

        except Exception:
            pass

        return option
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        single_file_clean = super().clean

        if isinstance(data, (list, tuple)):
            return [single_file_clean(file, initial) for file in data]

        return single_file_clean(data, initial)    
class ContractForm(forms.ModelForm):
    evidence_images = MultipleFileField(
        label="Evidence Photos",
        required=False,
        widget=MultipleFileInput(
            attrs={
                "class": "crm_input",
                "accept": "image/*",
                "multiple": True,
            }
        ),
    )
    class Meta:
        model = Contract
        fields = [
            "id_client",
            "id_project",

            "contract_title",
            "contract_date",
            "expiration_date",

            "company_name",
            "company_phone",
            "company_email",
            "company_address",
            "company_license",

            "client_name",
            "client_phone",
            "client_alt_phone",
            "client_email",
            "client_street_address",
            "client_city",
            "client_state",
            "client_zip_code",

            "project_name",
            "project_address",
            "project_description",
            "project_photo",
            "pdf_header_dark",

            "work_to_be_done",
            "additional_work",
            "work_not_to_be_done",
            "special_instructions",
            "consumer_notice",
            "cancellation_notice",
            "payment_terms",
            "cancellation_terms",
            "guarantee_terms",
            "miscellaneous_terms",

            "company_representative_name",
            "company_representative_title",
            "customer_signature_name",
            "signed_date",
        ]

        labels = {
            "id_client": "Client",
            "id_project": "Project",
            "contract_title": "Contract Title",
            "contract_date": "Contract Date",
            "expiration_date": "Expiration Date",

            "company_name": "Company Name",
            "company_phone": "Company Phone",
            "company_email": "Company Email",
            "company_address": "Company Address",
            "company_license": "Company License",

            "client_name": "Customer Name",
            "client_phone": "Customer Phone",
            "client_alt_phone": "Customer Alternate Phone",
            "client_email": "Customer Email",
            "client_street_address": "Street Address",
            "client_city": "City",
            "client_state": "State",
            "client_zip_code": "Zip Code",

            "project_name": "Project Name",
            "project_address": "Project Address",
            "project_description": "Project Description",
            "project_photo": "Project Photo Optional",
            "pdf_header_dark": "Use Dark PDF Header",

            "work_to_be_done": "Work To Be Done",
            "additional_work": "Additional Work To Be Done",
            "work_not_to_be_done": "Work NOT To Be Done",
            "special_instructions": "Special Instructions",
            "consumer_notice": "Notice To Consumer",
            "cancellation_notice": "Cancellation Notice",

            "company_representative_name": "Company Representative",
            "company_representative_title": "Representative Title",
            "customer_signature_name": "Customer Signature Name",
            "signed_date": "Signed Date",

            "payment_terms": "Payment Terms And Conditions",
            "cancellation_terms": "Cancellation",
            "guarantee_terms": "Guarantee",
            "miscellaneous_terms": "Miscellaneous Terms",
        }

        widgets = {
            "id_client": ClientSelect(attrs={"class": "crm_input"}),
            "id_project": ProjectSelect(attrs={"class": "crm_input"}),

            "contract_title": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Service Contract",
                }
            ),
            "contract_date": forms.DateInput(
                attrs={
                    "class": "crm_input",
                    "type": "date",
                }
            ),
            "expiration_date": forms.DateInput(
                attrs={
                    "class": "crm_input",
                    "type": "date",
                }
            ),

            "company_name": forms.TextInput(attrs={"class": "crm_input"}),
            "company_phone": forms.TextInput(attrs={"class": "crm_input"}),
            "company_email": forms.EmailInput(attrs={"class": "crm_input"}),
            "company_address": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                }
            ),
            "company_license": forms.TextInput(attrs={"class": "crm_input"}),

            "client_name": forms.TextInput(attrs={"class": "crm_input"}),
            "client_phone": forms.TextInput(attrs={"class": "crm_input"}),
            "client_alt_phone": forms.TextInput(attrs={"class": "crm_input"}),
            "client_email": forms.EmailInput(attrs={"class": "crm_input"}),
            "client_street_address": forms.TextInput(attrs={"class": "crm_input"}),
            "client_city": forms.TextInput(attrs={"class": "crm_input"}),
            "client_state": forms.TextInput(attrs={"class": "crm_input"}),
            "client_zip_code": forms.TextInput(attrs={"class": "crm_input"}),

            "project_name": forms.TextInput(attrs={"class": "crm_input"}),
            "project_address": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                }
            ),
            "project_description": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "General project description.",
                }
            ),
            "project_photo": forms.ClearableFileInput(
                attrs={
                    "class": "crm_input",
                    "accept": "image/*",
                }
            ),
            "pdf_header_dark": forms.CheckboxInput(),

            "work_to_be_done": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 9,
                    "placeholder": "Describe the work included under this contract.",
                }
            ),
            "additional_work": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Additional work to be done.",
                }
            ),
            "work_not_to_be_done": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Work not included in this contract.",
                }
            ),
            "special_instructions": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Special instructions for this contract.",
                }
            ),
            "consumer_notice": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 6,
                }
            ),
            "cancellation_notice": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 5,
                    "placeholder": "Cancellation notice address or legal cancellation text.",
                }
            ),

            "company_representative_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Representative full name",
                }
            ),
            "company_representative_title": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Owner, Manager, Sales Representative, etc.",
                }
            ),
            "customer_signature_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Customer name for signature",
                }
            ),
            "signed_date": forms.DateInput(
                attrs={
                    "class": "crm_input",
                    "type": "date",
                }
            ),
            "payment_terms": forms.Textarea(
                attrs={
                    "class": "crm_input contract_terms_input",
                    "rows": 8,
                }
            ),
            "cancellation_terms": forms.Textarea(
                attrs={
                    "class": "crm_input contract_terms_input",
                    "rows": 8,
                }
            ),
            "guarantee_terms": forms.Textarea(
                attrs={
                    "class": "crm_input contract_terms_input",
                    "rows": 8,
                }
            ),
            "miscellaneous_terms": forms.Textarea(
                attrs={
                    "class": "crm_input contract_terms_input",
                    "rows": 8,
                }
            ),
        }

    def __init__(self, *args, user=None, project=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user
        self.project = project

        readonly_fields = [
            "company_name",
            "company_phone",
            "company_email",
            "company_license",
            "company_address",

            "client_name",
            "client_phone",
            "client_email",
            "client_street_address",

            "customer_signature_name",
            "signed_date",

            "project_name",
            "project_address",
        ]

        for field_name in readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["readonly"] = "readonly"
                self.fields[field_name].widget.attrs["class"] = (
                    self.fields[field_name].widget.attrs.get("class", "") + " contract_readonly_input"
                ).strip()

        self.fields["id_client"].required = True
        self.fields["id_project"].required = True
        self.fields["contract_title"].required = True
        self.fields["contract_date"].required = True
        self.fields["work_to_be_done"].required = True
        if not self.instance.pk:
            self.fields["payment_terms"].initial = DEFAULT_PAYMENT_TERMS
            self.fields["cancellation_terms"].initial = DEFAULT_CANCELLATION_TERMS
            self.fields["guarantee_terms"].initial = DEFAULT_GUARANTEE_TERMS
            self.fields["miscellaneous_terms"].initial = DEFAULT_MISCELLANEOUS_TERMS
        else:
            if not self.instance.payment_terms:
                self.fields["payment_terms"].initial = DEFAULT_PAYMENT_TERMS

            if not self.instance.cancellation_terms:
                self.fields["cancellation_terms"].initial = DEFAULT_CANCELLATION_TERMS

            if not self.instance.guarantee_terms:
                self.fields["guarantee_terms"].initial = DEFAULT_GUARANTEE_TERMS

            if not self.instance.miscellaneous_terms:
                self.fields["miscellaneous_terms"].initial = DEFAULT_MISCELLANEOUS_TERMS

        if user and user.is_authenticated and not user.is_superuser:
            company_id = user.id_company_id

            self.fields["id_client"].queryset = Client.objects.filter(
                id_company_id=company_id,
            ).order_by("name")

            self.fields["id_project"].queryset = Project.objects.select_related(
                "id_company",
                "id_client",
            ).filter(
                id_company_id=company_id,
            ).order_by("-created_at")

        else:
            self.fields["id_client"].queryset = Client.objects.select_related(
                "id_company",
            ).all().order_by("id_company__name", "name")

            self.fields["id_project"].queryset = Project.objects.select_related(
                "id_company",
                "id_client",
            ).all().order_by("-created_at")

        self.client_snapshot_data = {}

        for client in self.fields["id_client"].queryset:
            first_name = (getattr(client, "first_name", "") or "").strip()
            last_name = (getattr(client, "last_name", "") or "").strip()

            if not first_name and not last_name:
                name_parts = (getattr(client, "name", "") or "").strip().split()
                first_name = name_parts[0] if len(name_parts) >= 1 else ""
                last_name = name_parts[1] if len(name_parts) >= 2 else ""

            customer_name = " ".join(
                part for part in [first_name, last_name] if part
            ).strip()

            if not customer_name:
                customer_name = (getattr(client, "name", "") or "").strip()

            self.client_snapshot_data[str(client.pk)] = {
                "customer_name": customer_name,
                "phone": getattr(client, "phone", "") or "",
                "email": getattr(client, "email", "") or "",
                "address": getattr(client, "address", "") or "",
            }

        self.project_snapshot_data = {}

        for project_item in self.fields["id_project"].queryset:
            self.project_snapshot_data[str(project_item.pk)] = {
                "project_name": first_value(
                    project_item,
                    ["name", "project_name", "title"],
                ),
                "project_address": first_value(
                    project_item,
                    ["project_address", "address", "location", "job_address"],
                ),
                "project_description": first_value(
                    project_item,
                    ["description", "project_notes", "scope", "notes"],
                ),
            }

        selected_client_id = self.get_selected_client_id()

        if selected_client_id and not project:
            self.fields["id_project"].queryset = self.fields["id_project"].queryset.filter(
                id_client_id=selected_client_id,
            )

        if project:
            self.fields["id_project"].queryset = Project.objects.filter(
                id_project=project.id_project,
            )
            self.fields["id_project"].initial = project
            self.fields["id_project"].disabled = True

            self.fields["id_client"].queryset = Client.objects.filter(
                id_client=project.id_client_id,
            )
            self.fields["id_client"].initial = project.id_client
            self.fields["id_client"].disabled = True

            self.set_initial_from_project(project)

        elif not self.instance.pk:
            self.set_initial_from_user_company(user)

        if self.instance and self.instance.pk:
            if self.instance.id_client_id:
                self.fields["id_project"].queryset = self.fields["id_project"].queryset.filter(
                    id_client_id=self.instance.id_client_id,
                )

    def get_selected_client_id(self):
        if self.data:
            return self.data.get(self.add_prefix("id_client")) or self.data.get("id_client") or None

        if self.project:
            return self.project.id_client_id

        if self.instance and self.instance.pk and self.instance.id_client_id:
            return self.instance.id_client_id

        initial_client = self.initial.get("id_client") if self.initial else None
        return getattr(initial_client, "id_client", initial_client) or None

    def clean_company_phone(self):
        phone = (self.cleaned_data.get("company_phone") or "").strip()

        if phone and not phone.isdigit():
            raise forms.ValidationError("Company phone must contain numbers only.")

        return phone

    def clean_client_phone(self):
        phone = (self.cleaned_data.get("client_phone") or "").strip()

        if phone and not phone.isdigit():
            raise forms.ValidationError("Customer phone must contain numbers only.")

        return phone

    def clean_client_alt_phone(self):
        phone = (self.cleaned_data.get("client_alt_phone") or "").strip()

        if phone and not phone.isdigit():
            raise forms.ValidationError("Customer alternate phone must contain numbers only.")

        return phone

    def set_initial_from_user_company(self, user):
        if not user or not user.is_authenticated:
            return

        company = getattr(user, "id_company", None)

        if not company:
            return

        self.fields["company_name"].initial = first_value(
            company,
            ["name", "company_name", "legal_name", "commercial_name"],
        )
        self.fields["company_phone"].initial = first_value(
            company,
            ["phone", "phone_number", "main_phone", "company_phone"],
        )
        self.fields["company_email"].initial = first_value(
            company,
            ["email", "company_email", "contact_email"],
        )
        self.fields["company_address"].initial = first_value(
            company,
            ["address", "company_address", "street_address", "full_address"],
        )
        self.fields["company_license"].initial = first_value(
            company,
            ["license", "license_number", "company_license", "contractor_license"],
        )

    def set_initial_from_project(self, project):
        client = project.id_client
        company = project.id_company

        self.fields["company_name"].initial = first_value(
            company,
            ["name", "company_name", "legal_name", "commercial_name"],
        )
        self.fields["company_phone"].initial = first_value(
            company,
            ["phone", "phone_number", "main_phone", "company_phone"],
        )
        self.fields["company_email"].initial = first_value(
            company,
            ["email", "company_email", "contact_email"],
        )
        self.fields["company_address"].initial = first_value(
            company,
            ["address", "company_address", "street_address", "full_address"],
        )
        self.fields["company_license"].initial = first_value(
            company,
            ["license", "license_number", "company_license", "contractor_license"],
        )

        self.fields["client_name"].initial = first_value(
            client,
            ["name", "legal_name", "commercial_name", "full_name"],
        )
        self.fields["client_phone"].initial = first_value(
            client,
            ["phone", "phone_number", "mobile", "main_phone"],
        )
        self.fields["client_alt_phone"].initial = first_value(
            client,
            ["alt_phone", "secondary_phone", "other_phone"],
        )
        self.fields["client_email"].initial = first_value(
            client,
            ["email", "contact_email", "billing_email"],
        )
        self.fields["client_street_address"].initial = first_value(
            client,
            ["street_address", "address", "billing_address"],
        )
        self.fields["client_city"].initial = first_value(
            client,
            ["city", "billing_city"],
        )
        self.fields["client_state"].initial = first_value(
            client,
            ["state", "billing_state"],
        )
        self.fields["client_zip_code"].initial = first_value(
            client,
            ["zip_code", "zipcode", "postal_code", "billing_zip_code"],
        )

        self.fields["project_name"].initial = first_value(
            project,
            ["name", "project_name", "title"],
        )
        self.fields["project_address"].initial = first_value(
            project,
            ["project_address", "address", "location", "job_address"],
        )
        self.fields["project_description"].initial = first_value(
            project,
            ["description", "project_notes", "scope", "notes"],
        )

    def clean(self):
        cleaned_data = super().clean()

        client = cleaned_data.get("id_client")
        project = cleaned_data.get("id_project") or self.project

        if self.project:
            cleaned_data["id_project"] = self.project
            cleaned_data["id_client"] = self.project.id_client
            project = self.project
            client = self.project.id_client

        if not client:
            raise forms.ValidationError("Client is required.")

        if not project:
            raise forms.ValidationError("Project is required.")

        if self.request_user and self.request_user.is_authenticated and not self.request_user.is_superuser:
            if project.id_company_id != self.request_user.id_company_id:
                raise forms.ValidationError("You can only manage contracts for your company.")

            if client.id_company_id != self.request_user.id_company_id:
                raise forms.ValidationError("Client must belong to your company.")

        if client and project and project.id_client_id != client.id_client:
            raise forms.ValidationError("Project must belong to the selected client.")

        return cleaned_data

    def save(self, commit=True):
        contract = super().save(commit=False)

        if self.project:
            contract.id_project = self.project
            contract.id_client = self.project.id_client

        if contract.id_project and not contract.id_company_id:
            contract.id_company = contract.id_project.id_company

        if contract.id_client and not contract.id_company_id:
            contract.id_company = contract.id_client.id_company

        if not contract.status:
            contract.status = CONTRACT_STATUS_DRAFT

        # Contracts is documentary only. No financial/billing behavior.
        contract.contract_price = 0
        contract.initial_payment = 0
        contract.balance_due = 0
        contract.state_sales_tax_rate = 0
        contract.local_sales_tax_rate = 0
        contract.state_sales_tax_amount = 0
        contract.local_sales_tax_amount = 0
        contract.total_amount_due = 0

        if commit:
            contract.save()
            self.save_evidence_images(contract)

        return contract

    def save_evidence_images(self, contract):
        evidence_files = self.files.getlist("evidence_images")

        if not evidence_files:
            return

        current_count = ContractEvidence.objects.filter(
            id_contract=contract,
        ).count()

        for index, image in enumerate(evidence_files, start=current_count + 1):
            ContractEvidence.objects.create(
                id_contract=contract,
                image=image,
                sort_order=index,
            )
class ContractSendEmailForm(forms.Form):
    recipient_email = forms.EmailField(
        label="Recipient Email",
        widget=forms.EmailInput(
            attrs={
                "class": "crm_input",
                "placeholder": "customer@email.com",
            }
        ),
    )

    subject = forms.CharField(
        label="Subject",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Contract for your project",
            }
        ),
    )

    message = forms.CharField(
        label="Message",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 6,
                "placeholder": "Please review the attached contract.",
            }
        ),
    )