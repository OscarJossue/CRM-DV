import csv

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.core.tenant import user_is_global_admin
from apps.platform_audit.models.choices import (
    PLATFORM_AUDIT_ACTION_CREATE,
    PLATFORM_AUDIT_ACTION_EXPORT,
    PLATFORM_AUDIT_ACTION_SEND,
    PLATFORM_AUDIT_ACTION_UPDATE,
)
from apps.platform_audit.services import log_platform_action
from apps.platform_email.services import send_platform_html_email

from .forms import PlatformDocumentEmailForm, PlatformDocumentForm, PlatformDocumentItemFormSet
from apps.accounts.models import UserAccount

from .models import PlatformDocument, PlatformDocumentItem
from .models.choices import DOCUMENT_STATUS_CHOICES, DOCUMENT_TYPE_CHOICES
from .services import (
    can_generate_invoice_from_proforma,
    generate_invoice_from_paid_proforma,
    generate_platform_document_number,
    get_generated_invoice_for_proforma,
    recalculate_platform_document,
)
from apps.accounts.models.choices import PLATFORM_DOCUMENTS
from apps.core.platform_permissions import PlatformPermissionRequiredMixin

class PlatformAdminRequiredMixin(PlatformPermissionRequiredMixin):
    platform_module_name = PLATFORM_DOCUMENTS


def get_filtered_documents(request):
    queryset = PlatformDocument.objects.select_related(
        "id_company",
        "id_subscription",
        "created_by",
    ).prefetch_related("items")

    document_type = request.GET.get("type", "").strip()
    status = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()

    if document_type:
        queryset = queryset.filter(document_type=document_type)

    if status:
        queryset = queryset.filter(status=status)

    if q:
        queryset = queryset.filter(
            Q(document_number__icontains=q)
            | Q(id_company__name__icontains=q)
        )

    return queryset.distinct().order_by("-issue_date", "-id_document")


def snapshot_document(document):
    if not document:
        return {}

    items = []

    try:
        for item in document.items.all():
            items.append(
                {
                    "item_id": item.id_document_item,
                    "description": item.description,
                    "quantity": str(item.quantity or "0"),
                    "unit_price": str(item.unit_price or "0.00"),
                    "subtotal": str(item.subtotal or "0.00"),
                }
            )
    except Exception:
        items = []

    return {
        "document_id": document.id_document,
        "document_number": document.document_number,
        "document_type": document.document_type,
        "status": document.status,
        "company_id": document.id_company_id,
        "company_name": document.id_company.name if document.id_company else None,
        "company_slug": document.id_company.slug if document.id_company else None,
        "subscription_id": document.id_subscription_id,
        "source_document_id": document.source_document_id,
        "issue_date": document.issue_date.isoformat() if document.issue_date else None,
        "due_date": document.due_date.isoformat() if document.due_date else None,
        "subtotal": str(document.subtotal or "0.00"),
        "tax_rate": str(document.tax_rate or "0.00"),
        "tax_amount": str(document.tax_amount or "0.00"),
        "discount_amount": str(document.discount_amount or "0.00"),
        "total": str(document.total or "0.00"),
        "notes": document.notes,
        "terms": document.terms,
        "footer": document.footer,
        "items": items,
    }


def log_document_audit(
    *,
    request,
    document,
    action,
    description,
    previous_snapshot=None,
    extra_metadata=None,
):
    try:
        metadata = {
            "document": snapshot_document(document),
        }

        if previous_snapshot:
            metadata["previous_document"] = previous_snapshot

        if extra_metadata:
            metadata["extra"] = extra_metadata

        log_platform_action(
            user=request.user,
            company=document.id_company,
            module_name="platform_documents",
            action=action,
            object_id=document.id_document,
            object_label=document.document_number,
            description=description,
            request=request,
            metadata=metadata,
        )
    except Exception:
        pass


def get_active_item_forms(items_formset):
    active_forms = []

    for item_form in items_formset.forms:
        if not hasattr(item_form, "cleaned_data"):
            continue

        cleaned_data = item_form.cleaned_data

        if cleaned_data.get("DELETE"):
            continue

        description = (cleaned_data.get("description") or "").strip()
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")

        if description and quantity is not None and unit_price is not None:
            active_forms.append(item_form)

    return active_forms


def save_document_items(document, items_formset):
    for item_form in items_formset.forms:
        cleaned_data = item_form.cleaned_data
        item_instance = item_form.instance

        if cleaned_data.get("DELETE"):
            if item_instance and item_instance.pk:
                item_instance.delete()
            continue

        description = (cleaned_data.get("description") or "").strip()
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")

        if not description or quantity is None or unit_price is None:
            continue

        if item_instance and item_instance.pk:
            item = item_instance
        else:
            item = PlatformDocumentItem(id_document=document)

        item.description = description
        item.quantity = quantity
        item.unit_price = unit_price
        item.save()


class PlatformDocumentListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    model = PlatformDocument
    template_name = "platform_documents/list.html"
    context_object_name = "documents"
    login_url = "/login/"
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_documents(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        document_type = self.request.GET.get("type", "").strip()
        status = self.request.GET.get("status", "").strip()
        q = self.request.GET.get("q", "").strip()

        base_queryset = PlatformDocument.objects.all()

        context["document_type_filter"] = document_type
        context["status_filter"] = status
        context["q"] = q
        context["document_type_choices"] = DOCUMENT_TYPE_CHOICES
        context["status_choices"] = DOCUMENT_STATUS_CHOICES
        context["active_querystring"] = self.request.GET.urlencode()

        context["total_documents"] = base_queryset.count()
        context["total_proformas"] = base_queryset.filter(document_type="proforma").count()
        context["total_invoices"] = base_queryset.filter(document_type="invoice").count()
        context["total_paid"] = base_queryset.filter(status="paid").count()
        context["total_pending"] = base_queryset.exclude(status__in=["paid", "void"]).count()

        all_params = self.request.GET.copy()
        all_params.pop("type", None)

        proforma_params = self.request.GET.copy()
        proforma_params["type"] = "proforma"

        invoice_params = self.request.GET.copy()
        invoice_params["type"] = "invoice"

        context["all_documents_url"] = f"?{all_params.urlencode()}" if all_params else "?"
        context["proformas_url"] = f"?{proforma_params.urlencode()}"
        context["invoices_url"] = f"?{invoice_params.urlencode()}"

        return context


class PlatformDocumentDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    model = PlatformDocument
    template_name = "platform_documents/detail.html"
    context_object_name = "document"
    pk_url_kwarg = "id_document"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformDocument.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        ).prefetch_related("items")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        generated_invoice = get_generated_invoice_for_proforma(self.object)

        context["generated_invoice"] = generated_invoice
        context["can_generate_invoice"] = can_generate_invoice_from_proforma(self.object)

        return context


class PlatformDocumentPrintView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    model = PlatformDocument
    template_name = "platform_documents/print.html"
    context_object_name = "document"
    pk_url_kwarg = "id_document"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformDocument.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        ).prefetch_related("items", "platform_payments")

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        log_document_audit(
            request=request,
            document=self.object,
            action=PLATFORM_AUDIT_ACTION_EXPORT,
            description=f"Platform document opened for print/PDF: {self.object.document_number}.",
            extra_metadata={
                "export_type": "print_or_pdf",
            },
        )

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class PlatformDocumentCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    model = PlatformDocument
    form_class = PlatformDocumentForm
    template_name = "platform_documents/form.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["items_formset"] = PlatformDocumentItemFormSet(self.request.POST)
        else:
            context["items_formset"] = PlatformDocumentItemFormSet()

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context["items_formset"]

        if not items_formset.is_valid():
            return self.form_invalid(form)

        active_item_forms = get_active_item_forms(items_formset)

        if not active_item_forms:
            form.add_error(None, "At least one line item is required.")
            return self.form_invalid(form)

        with transaction.atomic():
            document = form.save(commit=False)
            document.created_by = self.request.user
            document.document_number = generate_platform_document_number(
                form.cleaned_data.get("document_type")
            )
            document.save()

            self.object = document

            save_document_items(self.object, items_formset)
            recalculate_platform_document(self.object)
            self.object.refresh_from_db()

            log_document_audit(
                request=self.request,
                document=self.object,
                action=PLATFORM_AUDIT_ACTION_CREATE,
                description=(
                    f"Platform document created: {self.object.document_number} "
                    f"for {self.object.id_company.name}."
                ),
            )

        messages.success(self.request, "Platform document created successfully.")

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the platform document form.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_documents:detail",
            kwargs={"id_document": self.object.id_document},
        )


class PlatformDocumentUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    model = PlatformDocument
    form_class = PlatformDocumentForm
    template_name = "platform_documents/form.html"
    context_object_name = "document"
    pk_url_kwarg = "id_document"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformDocument.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        ).prefetch_related("items")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["items_formset"] = PlatformDocumentItemFormSet(
                self.request.POST,
                instance=self.object,
            )
        else:
            context["items_formset"] = PlatformDocumentItemFormSet(instance=self.object)

        return context

    def form_valid(self, form):
        previous_document = PlatformDocument.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        ).prefetch_related("items").get(id_document=self.object.id_document)

        previous_snapshot = snapshot_document(previous_document)

        context = self.get_context_data()
        items_formset = context["items_formset"]

        if not items_formset.is_valid():
            return self.form_invalid(form)

        active_item_forms = get_active_item_forms(items_formset)

        if not active_item_forms:
            form.add_error(None, "At least one line item is required.")
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()

            save_document_items(self.object, items_formset)
            recalculate_platform_document(self.object)
            self.object.refresh_from_db()

            log_document_audit(
                request=self.request,
                document=self.object,
                action=PLATFORM_AUDIT_ACTION_UPDATE,
                description=(
                    f"Platform document updated: {self.object.document_number} "
                    f"for {self.object.id_company.name}."
                ),
                previous_snapshot=previous_snapshot,
            )

        messages.success(self.request, "Platform document updated successfully.")

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the platform document form.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_documents:detail",
            kwargs={"id_document": self.object.id_document},
        )


class PlatformDocumentExportCSVView(LoginRequiredMixin, PlatformAdminRequiredMixin, TemplateView):
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        documents = get_filtered_documents(request)
        exported_count = documents.count()

        try:
            log_platform_action(
                user=request.user,
                company=None,
                module_name="platform_documents",
                action=PLATFORM_AUDIT_ACTION_EXPORT,
                object_id=None,
                object_label="platform-documents.csv",
                description="Platform documents exported to CSV.",
                request=request,
                metadata={
                    "filters": request.GET.dict(),
                    "exported_count": exported_count,
                },
            )
        except Exception:
            pass

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="platform-documents.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Document Number",
                "Company",
                "Company Slug",
                "Document Type",
                "Status",
                "Issue Date",
                "Due Date",
                "Subtotal",
                "Tax Rate",
                "Tax Amount",
                "Discount",
                "Total",
                "Created By",
                "Created At",
            ]
        )

        for document in documents:
            writer.writerow(
                [
                    document.document_number,
                    document.id_company.name if document.id_company else "",
                    document.id_company.slug if document.id_company else "",
                    document.get_document_type_display(),
                    document.get_status_display(),
                    document.issue_date,
                    document.due_date or "",
                    document.subtotal,
                    document.tax_rate,
                    document.tax_amount,
                    document.discount_amount,
                    document.total,
                    document.created_by.email if document.created_by else "",
                    document.created_at,
                ]
            )

        return response


@require_POST
def platform_document_generate_invoice_view(request, id_document):
    if not user_is_global_admin(request.user):
        return redirect("platform_documents:list")

    proforma = get_object_or_404(
        PlatformDocument.objects.select_related(
            "id_company",
            "id_subscription",
            "created_by",
        ).prefetch_related("items"),
        id_document=id_document,
    )

    previous_snapshot = snapshot_document(proforma)

    try:
        with transaction.atomic():
            invoice = generate_invoice_from_paid_proforma(
                proforma,
                created_by=request.user,
            )

            invoice.refresh_from_db()

            log_document_audit(
                request=request,
                document=invoice,
                action=PLATFORM_AUDIT_ACTION_CREATE,
                description=(
                    f"Invoice generated from paid proforma {proforma.document_number}: "
                    f"{invoice.document_number}."
                ),
                extra_metadata={
                    "source_proforma": previous_snapshot,
                    "generated_invoice_id": invoice.id_document,
                    "generated_invoice_number": invoice.document_number,
                },
            )

        messages.success(request, "Invoice generated successfully from paid proforma.")
        return redirect("platform_documents:detail", id_document=invoice.id_document)

    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("platform_documents:detail", id_document=proforma.id_document)

def get_company_owner_user(company):
    if not company:
        return None

    owner_user = (
        UserAccount.objects.select_related("id_company", "id_role")
        .filter(
            id_company=company,
            is_active=True,
            is_company_owner=True,
        )
        .order_by("id_user")
        .first()
    )

    if owner_user:
        return owner_user

    return (
        UserAccount.objects.select_related("id_company", "id_role")
        .filter(
            id_company=company,
            is_active=True,
            id_role__name__iexact="Owner",
        )
        .order_by("id_user")
        .first()
    )

class PlatformDocumentSendEmailView(LoginRequiredMixin, PlatformAdminRequiredMixin, FormView):
    template_name = "platform_documents/send_email.html"
    form_class = PlatformDocumentEmailForm
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.document = get_object_or_404(
            PlatformDocument.objects.select_related(
                "id_company",
                "id_subscription",
                "created_by",
            ).prefetch_related("items", "platform_payments"),
            id_document=kwargs.get("id_document"),
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()

        owner_user = get_company_owner_user(self.document.id_company)
        recipient_email = owner_user.email if owner_user else ""

        owner_name = ""

        if owner_user:
            owner_name = " ".join(
                [
                    owner_user.first_name or "",
                    owner_user.last_name or "",
                ]
            ).strip()

        if not owner_name:
            owner_name = self.document.id_company.name

        document_label = self.document.get_document_type_display()

        initial["recipient_email"] = recipient_email
        initial["subject"] = f"{document_label} {self.document.document_number} - CEO Marketing USA"
        initial["message"] = (
            f"Hello {owner_name},\n\n"
            f"Please find below your {document_label.lower()} generated by CEO Marketing USA.\n\n"
            "Thank you."
        )

        return initial


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["document"] = self.document
        context["print_url"] = self.request.build_absolute_uri(
            reverse_lazy(
                "platform_documents:print",
                kwargs={"id_document": self.document.id_document},
            )
        )

        return context

    def form_valid(self, form):
        print_url = self.request.build_absolute_uri(
            reverse_lazy(
                "platform_documents:print",
                kwargs={"id_document": self.document.id_document},
            )
        )

        logo_cid = "ceo_marketing_logo"
        logo_path = settings.MEDIA_ROOT / "logo_empresa.png"

        html_message = render_to_string(
            "platform_documents/email_document.html",
            {
                "document": self.document,
                "document_items": self.document.items.all(),
                "custom_message": form.cleaned_data["message"],
                "print_url": print_url,
                "logo_cid": logo_cid,
            },
            request=self.request,
        )

        plain_message = (
            f"{form.cleaned_data['message']}\n\n"
            f"Document: {self.document.document_number}\n"
            f"Company: {self.document.id_company.name}\n"
            f"Total: ${self.document.total}\n"
            f"View / Print: {print_url}"
        )

        previous_snapshot = snapshot_document(self.document)

        email_log = send_platform_html_email(
            recipient_email=form.cleaned_data["recipient_email"],
            subject=form.cleaned_data["subject"],
            message=plain_message,
            html_message=html_message,
            company=self.document.id_company,
            email_type="platform_document",
            inline_images=[
                {
                    "path": logo_path,
                    "cid": logo_cid,
                    "filename": "logo_empresa.png",
                }
            ],
        )

        if email_log.status == "sent":
            if self.document.status == "draft":
                self.document.status = "sent"
                self.document.save(update_fields=["status", "updated_at"])

            self.document.refresh_from_db()

            log_document_audit(
                request=self.request,
                document=self.document,
                action=PLATFORM_AUDIT_ACTION_SEND,
                description=(
                    f"Platform document sent by email: {self.document.document_number} "
                    f"to {form.cleaned_data['recipient_email']}."
                ),
                previous_snapshot=previous_snapshot,
                extra_metadata={
                    "recipient_email": form.cleaned_data["recipient_email"],
                    "subject": form.cleaned_data["subject"],
                    "email_log_id": getattr(email_log, "id_email_log", None),
                    "email_status": email_log.status,
                    "print_url": print_url,
                },
            )

            messages.success(self.request, "Platform document email sent successfully.")
        else:
            log_document_audit(
                request=self.request,
                document=self.document,
                action=PLATFORM_AUDIT_ACTION_SEND,
                description=(
                    f"Platform document email failed: {self.document.document_number} "
                    f"to {form.cleaned_data['recipient_email']}."
                ),
                previous_snapshot=previous_snapshot,
                extra_metadata={
                    "recipient_email": form.cleaned_data["recipient_email"],
                    "subject": form.cleaned_data["subject"],
                    "email_log_id": getattr(email_log, "id_email_log", None),
                    "email_status": email_log.status,
                    "error_message": email_log.error_message,
                },
            )

            messages.error(
                self.request,
                f"Platform document email failed. {email_log.error_message or 'Check email logs.'}",
            )

        return redirect("platform_documents:detail", id_document=self.document.id_document)