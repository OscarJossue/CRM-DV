from decimal import Decimal, InvalidOperation

from django import forms
from django.db.models import Q

from apps.clients.models import Client
from apps.invoices.models import Invoice
from apps.invoices.models.choices import INVOICE_PAYABLE_STATUSES
from apps.projects.models import Project

from .models import ClientCreditAccount, Payment
from .models.choices import PAYMENT_STATUS_VOID
from .services import recalculate_invoice_payment_status


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


def get_company_from_user_or_client(user=None, client=None):
    if user and user.is_authenticated and not user.is_superuser:
        return user.id_company

    if client:
        return client.id_company

    return None


class ClientSelect(forms.Select):
    def __init__(self, *args, client_credit_balances=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_credit_balances = client_credit_balances or {}

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
            option["attrs"]["data-company"] = str(client.id_company_id or "")
            option["attrs"]["data-credit"] = str(
                self.client_credit_balances.get(client.id_client, Decimal("0.00"))
            )
        except Exception:
            pass

        return option


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
            option["attrs"]["data-company"] = str(project.id_company_id or "")
        except Exception:
            pass

        return option


class PaymentForm(forms.ModelForm):
    use_client_credit = forms.BooleanField(
        required=False,
        label="Use client credit balance",
        widget=forms.CheckboxInput(
            attrs={
                "class": "payment_credit_checkbox",
            }
        ),
    )

    class Meta:
        model = Payment
        fields = [
            "id_client",
            "id_project",
            "id_invoice",
            "payment_date",
            "payment_method",
            "voucher_code",
            "amount",
            "receipt_file",
            "notes",
        ]

        labels = {
            "id_client": "Client",
            "id_project": "Project",
            "id_invoice": "Legacy Main Invoice",
            "payment_date": "Payment Date",
            "payment_method": "Payment Method",
            "voucher_code": "Voucher / Reference",
            "amount": "Payment Amount",
            "receipt_file": "Receipt File",
            "notes": "Notes",
        }

        widgets = {
            "id_client": ClientSelect(attrs={"class": "crm_input"}),
            "id_project": ProjectSelect(attrs={"class": "crm_input"}),
            "id_invoice": forms.HiddenInput(),
            "payment_date": forms.DateInput(
                attrs={
                    "class": "crm_input",
                    "type": "date",
                }
            ),
            "payment_method": forms.Select(attrs={"class": "crm_input"}),
            "voucher_code": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Receipt, voucher, check, Zelle, ACH or bank code",
                }
            ),
            "amount": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "inputmode": "decimal",
                    "placeholder": "0.00",
                }
            ),
            "receipt_file": forms.ClearableFileInput(
                attrs={
                    "class": "crm_input",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Optional payment notes",
                }
            ),
        }

    def __init__(self, *args, user=None, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user
        self.invoice = invoice
        self.allocation_fields = []
        self.open_invoices_queryset = Invoice.objects.none()

        self.fields["id_client"].required = True
        self.fields["id_project"].required = True
        self.fields["id_invoice"].required = False
        self.fields["voucher_code"].required = False

        if self.instance and self.instance.pk:
            self.fields["use_client_credit"].initial = False
            self.fields["use_client_credit"].disabled = True

        company_id = None

        if user and user.is_authenticated and not user.is_superuser:
            company_id = user.id_company_id

            self.fields["id_client"].queryset = Client.objects.filter(
                id_company=company_id,
            ).order_by("name")

            self.fields["id_project"].queryset = Project.objects.filter(
                id_company=company_id,
            ).order_by("-created_at")

        else:
            self.fields["id_client"].queryset = Client.objects.all().order_by("name")
            self.fields["id_project"].queryset = Project.objects.all().order_by("-created_at")

        self.fields["id_client"].empty_label = "Select client"
        self.fields["id_project"].empty_label = "Select project"

        self.client_credit_balances = self.get_client_credit_balances(company_id=company_id)
        if hasattr(self.fields["id_client"].widget, "client_credit_balances"):
            self.fields["id_client"].widget.client_credit_balances = self.client_credit_balances

        if invoice:
            recalculate_invoice_payment_status(invoice)
            invoice.refresh_from_db()

            company_id = invoice.id_company_id

            self.fields["id_client"].initial = invoice.id_client
            self.fields["id_project"].initial = invoice.id_project
            self.fields["id_invoice"].initial = invoice
            self.fields["amount"].initial = invoice.balance_due

            self.client_credit_balances = self.get_client_credit_balances(company_id=company_id)
            if hasattr(self.fields["id_client"].widget, "client_credit_balances"):
                self.fields["id_client"].widget.client_credit_balances = self.client_credit_balances

        selected_client_id = self.get_selected_client_id()
        selected_project_id = self.get_selected_project_id()

        if selected_client_id:
            self.fields["id_project"].queryset = self.fields["id_project"].queryset.filter(
                id_client_id=selected_client_id,
            )

        candidate_invoices_queryset = Invoice.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
        ).filter(
            status__in=INVOICE_PAYABLE_STATUSES,
        )

        if company_id:
            candidate_invoices_queryset = candidate_invoices_queryset.filter(
                id_company_id=company_id,
            )

        # Important UX rule:
        # - Initial GET must preload all open invoices for the company so the right panel
        #   can show them immediately when the user selects Client + Project in the browser.
        # - POST/edit can safely narrow the queryset to the selected client/project.
        if selected_client_id:
            candidate_invoices_queryset = candidate_invoices_queryset.filter(
                id_client_id=selected_client_id,
            )
        elif invoice:
            candidate_invoices_queryset = candidate_invoices_queryset.filter(
                id_client_id=invoice.id_client_id,
            )

        if selected_project_id:
            candidate_invoices_queryset = candidate_invoices_queryset.filter(
                id_project_id=selected_project_id,
            )

        open_invoices = []

        for invoice_to_refresh in candidate_invoices_queryset.distinct():
            recalculate_invoice_payment_status(invoice_to_refresh)
            invoice_to_refresh.refresh_from_db()

            has_existing_allocation = bool(
                self.instance
                and self.instance.pk
                and invoice_to_refresh.payment_allocations.filter(
                    id_payment_id=self.instance.pk,
                ).exists()
            )

            if invoice_to_refresh.balance_due > Decimal("0.00") or has_existing_allocation:
                open_invoices.append(invoice_to_refresh)

        self.open_invoices_queryset = sorted(
            open_invoices,
            key=lambda item: (
                item.issue_date,
                item.id_invoice,
            ),
        )

        self.build_allocation_fields(invoice=invoice)

    def get_client_credit_balances(self, company_id=None):
        balances = {}
        queryset = self.fields["id_client"].queryset

        accounts = ClientCreditAccount.objects.filter(
            id_client__in=queryset,
        )

        if company_id:
            accounts = accounts.filter(id_company_id=company_id)

        for account in accounts:
            balances[account.id_client_id] = account.balance or Decimal("0.00")

        return balances

    def get_selected_client_id(self):
        if self.data:
            return self.data.get("id_client") or None

        if self.invoice:
            return self.invoice.id_client_id

        if self.instance and self.instance.pk and self.instance.id_client_id:
            return self.instance.id_client_id

        initial_client = self.initial.get("id_client") if self.initial else None

        return getattr(initial_client, "id_client", initial_client) or None

    def get_selected_project_id(self):
        if self.data:
            return self.data.get("id_project") or None

        if self.invoice and self.invoice.id_project_id:
            return self.invoice.id_project_id

        if self.instance and self.instance.pk and self.instance.id_project_id:
            return self.instance.id_project_id

        initial_project = self.initial.get("id_project") if self.initial else None

        return getattr(initial_project, "id_project", initial_project) or None

    def build_allocation_fields(self, invoice=None):
        order_index = 1

        for open_invoice in self.open_invoices_queryset:
            selected_field_name = f"allocation_selected_{open_invoice.id_invoice}"
            order_field_name = f"allocation_order_{open_invoice.id_invoice}"

            initial_selected = False
            initial_order = ""

            if invoice and invoice.id_invoice == open_invoice.id_invoice:
                initial_selected = True
                initial_order = "1"

            existing_allocation = None

            if self.instance and self.instance.pk:
                existing_allocation = self.instance.allocations.filter(
                    id_invoice=open_invoice,
                ).first()

                if existing_allocation:
                    initial_selected = True
                    initial_order = str(order_index)
                    order_index += 1

            max_available = open_invoice.balance_due or Decimal("0.00")

            if existing_allocation:
                max_available += existing_allocation.amount or Decimal("0.00")

            self.fields[selected_field_name] = forms.BooleanField(
                required=False,
                initial=initial_selected,
                label="Select",
                widget=forms.CheckboxInput(
                    attrs={
                        "class": "allocation-checkbox",
                        "data-invoice": str(open_invoice.id_invoice),
                        "data-balance": str(open_invoice.balance_due or Decimal("0.00")),
                        "data-max": str(max_available),
                        "data-order-field": order_field_name,
                    }
                ),
            )

            self.fields[order_field_name] = forms.CharField(
                required=False,
                initial=initial_order,
                widget=forms.HiddenInput(
                    attrs={
                        "class": "allocation-order",
                        "data-invoice": str(open_invoice.id_invoice),
                    }
                ),
            )

            self.allocation_fields.append(
                {
                    "selected_field_name": selected_field_name,
                    "selected_field": self[selected_field_name],
                    "order_field_name": order_field_name,
                    "order_field": self[order_field_name],
                    "invoice": open_invoice,
                    "max_available": max_available,
                }
            )

    def clean_voucher_code(self):
        voucher_code = (self.cleaned_data.get("voucher_code") or "").strip()

        # Voucher/reference is optional for credit-only applications.
        # If it is left blank, the payment service generates an internal code,
        # so the user can consume existing client credit without typing a receipt.
        if not voucher_code:
            return ""

        client = self.cleaned_data.get("id_client")
        company = get_company_from_user_or_client(
            user=self.request_user,
            client=client,
        )

        if not company:
            return voucher_code

        exists = Payment.objects.filter(
            id_company=company,
            voucher_code=voucher_code,
        ).exclude(
            status=PAYMENT_STATUS_VOID,
        )

        if self.instance and self.instance.pk:
            exists = exists.exclude(pk=self.instance.pk)

        if exists.exists():
            raise forms.ValidationError(
                "This voucher code already exists for this company. You can reuse it only if the previous payment is void."
            )

        return voucher_code


    def clean_receipt_file(self):
        receipt = self.cleaned_data.get("receipt_file")
        if not receipt:
            return receipt

        max_size = 5 * 1024 * 1024
        if getattr(receipt, "size", 0) > max_size:
            raise forms.ValidationError("Receipt file must not exceed 5 MB.")

        allowed_types = {"application/pdf", "image/jpeg", "image/png"}
        content_type = (getattr(receipt, "content_type", "") or "").lower()
        if content_type not in allowed_types:
            raise forms.ValidationError("Receipt must be a PDF, JPEG, or PNG file.")

        header = receipt.read(12)
        receipt.seek(0)
        is_pdf = header.startswith(b"%PDF-")
        is_jpeg = header.startswith(b"\xff\xd8\xff")
        is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
        if not (is_pdf or is_jpeg or is_png):
            raise forms.ValidationError("Receipt content does not match an allowed file type.")

        return receipt

    def clean_amount(self):
        amount = clean_decimal_value(
            self.cleaned_data.get("amount"),
            default="0.00",
        )

        if amount < Decimal("0.00"):
            raise forms.ValidationError("Payment amount cannot be negative.")

        return amount

    def clean(self):
        cleaned_data = super().clean()

        client = cleaned_data.get("id_client")
        project = cleaned_data.get("id_project")
        amount = cleaned_data.get("amount") or Decimal("0.00")
        use_client_credit = bool(cleaned_data.get("use_client_credit")) and not (self.instance and self.instance.pk)

        company = get_company_from_user_or_client(
            user=self.request_user,
            client=client,
        )

        if not company:
            raise forms.ValidationError("Company is required for this payment.")

        if not client:
            raise forms.ValidationError("Client is required for this payment.")

        if not project:
            raise forms.ValidationError("Project is required for this payment.")

        if (
            self.request_user
            and not self.request_user.is_superuser
            and client.id_company_id != self.request_user.id_company_id
        ):
            raise forms.ValidationError("You can only manage payments for your company.")

        if client and company and client.id_company_id != company.id_company:
            raise forms.ValidationError("Client must belong to the selected company.")

        if project:
            if project.id_company_id != company.id_company:
                raise forms.ValidationError("Project must belong to the selected company.")

            if project.id_client_id != client.id_client:
                raise forms.ValidationError("Project must belong to the selected client.")

        selected_invoices = []

        for item in self.allocation_fields:
            selected_field_name = item["selected_field_name"]
            order_field_name = item["order_field_name"]
            invoice = item["invoice"]
            max_available = item["max_available"]

            is_selected = bool(cleaned_data.get(selected_field_name))

            if not is_selected:
                continue

            recalculate_invoice_payment_status(invoice)
            invoice.refresh_from_db()

            raw_order = cleaned_data.get(order_field_name) or "999999"

            try:
                order_value = int(raw_order)
            except (TypeError, ValueError):
                order_value = 999999

            if invoice.id_company_id != company.id_company:
                raise forms.ValidationError(
                    f"Invoice {invoice.invoice_number or invoice.id_invoice} does not belong to this company."
                )

            if invoice.id_client_id != client.id_client:
                raise forms.ValidationError(
                    f"Invoice {invoice.invoice_number or invoice.id_invoice} does not belong to this client."
                )

            if project and invoice.id_project_id != project.id_project:
                raise forms.ValidationError(
                    f"Invoice {invoice.invoice_number or invoice.id_invoice} does not belong to the selected project."
                )

            if invoice.status not in INVOICE_PAYABLE_STATUSES:
                raise forms.ValidationError(
                    f"Invoice {invoice.invoice_number or invoice.id_invoice} cannot receive payments."
                )

            if invoice.balance_due <= Decimal("0.00"):
                raise forms.ValidationError(
                    f"Invoice {invoice.invoice_number or invoice.id_invoice} does not have pending balance."
                )

            selected_invoices.append(
                {
                    "invoice": invoice,
                    "max_available": invoice.balance_due,
                    "order": order_value,
                }
            )

        if not selected_invoices:
            raise forms.ValidationError(
                "You must select at least one unpaid invoice to create a payment."
            )

        selected_invoices.sort(
            key=lambda item: (
                item["order"],
                item["invoice"].issue_date,
                item["invoice"].id_invoice,
            )
        )

        account_balance = Decimal("0.00")

        if use_client_credit:
            account = ClientCreditAccount.objects.filter(
                id_company=company,
                id_client=client,
            ).first()

            if account:
                account_balance = account.balance or Decimal("0.00")

        if amount <= Decimal("0.00") and (not use_client_credit or account_balance <= Decimal("0.00")):
            raise forms.ValidationError(
                "Enter a payment amount or enable client credit with an available balance."
            )

        remaining_amount = amount
        remaining_client_credit = account_balance
        allocations = []
        credit_applications = []

        for item in selected_invoices:
            invoice = item["invoice"]
            invoice_balance = invoice.balance_due or Decimal("0.00")
            remaining_invoice_balance = invoice_balance

            credit_apply_amount = Decimal("0.00")

            if use_client_credit and remaining_invoice_balance > Decimal("0.00"):
                credit_apply_amount = remaining_invoice_balance

                if credit_apply_amount > remaining_client_credit:
                    credit_apply_amount = remaining_client_credit

                if credit_apply_amount > Decimal("0.00"):
                    credit_applications.append(
                        {
                            "invoice": invoice,
                            "amount": credit_apply_amount,
                        }
                    )

                    remaining_client_credit = remaining_client_credit - credit_apply_amount
                    remaining_invoice_balance = remaining_invoice_balance - credit_apply_amount

            payment_apply_amount = remaining_invoice_balance

            if payment_apply_amount > remaining_amount:
                payment_apply_amount = remaining_amount

            if payment_apply_amount > Decimal("0.00"):
                allocations.append(
                    {
                        "invoice": invoice,
                        "amount": payment_apply_amount,
                    }
                )

                remaining_amount = remaining_amount - payment_apply_amount

        if not allocations and not credit_applications:
            raise forms.ValidationError(
                "The selected invoices could not receive payment. Check the payment amount or available client credit."
            )

        total_allocated = Decimal("0.00")

        for allocation in allocations:
            total_allocated += allocation["amount"]

        total_credit_applied = Decimal("0.00")

        for credit_application in credit_applications:
            total_credit_applied += credit_application["amount"]

        if total_allocated > amount:
            raise forms.ValidationError(
                "Total allocated amount cannot be greater than the payment amount."
            )

        if total_credit_applied > account_balance:
            raise forms.ValidationError(
                "Client credit applied cannot be greater than the available credit balance."
            )

        cleaned_data["_company"] = company
        cleaned_data["_allocations_data"] = allocations
        cleaned_data["_credit_applications_data"] = credit_applications
        cleaned_data["_total_allocated"] = total_allocated
        cleaned_data["_client_credit_used"] = total_credit_applied
        cleaned_data["_available_client_credit"] = account_balance
        cleaned_data["_credit_amount"] = amount - total_allocated

        return cleaned_data

    def get_allocations_data(self):
        return self.cleaned_data.get("_allocations_data", [])

    def get_total_allocated(self):
        return self.cleaned_data.get("_total_allocated", Decimal("0.00"))

    def get_credit_amount(self):
        return self.cleaned_data.get("_credit_amount", Decimal("0.00"))

    def get_credit_applications_data(self):
        return self.cleaned_data.get("_credit_applications_data", [])

    def get_client_credit_used(self):
        return self.cleaned_data.get("_client_credit_used", Decimal("0.00"))

    def get_available_client_credit(self):
        return self.cleaned_data.get("_available_client_credit", Decimal("0.00"))

    def save(self, commit=True):
        payment = super().save(commit=False)

        company = self.cleaned_data.get("_company")
        client = self.cleaned_data.get("id_client")
        project = self.cleaned_data.get("id_project")

        payment.id_company = company
        payment.id_client = client
        payment.id_project = project
        payment.id_invoice = None
        payment.reference_code = payment.voucher_code

        if commit:
            payment.save()

        return payment