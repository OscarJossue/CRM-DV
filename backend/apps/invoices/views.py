from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.forms import inlineformset_factory
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.mixins import TenantModelViewSet
from apps.core.template_permissions import (
    ModulePermissionRequiredMixin,
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_DELETE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    require_module_action_or_403,
    user_can_module_action,
)
from apps.estimates.models import Estimate
from apps.projects.models import Project

from .forms import (
    InvoiceForm,
    InvoiceItemForm,
    InvoiceItemFormSet,
    InvoiceSendEmailForm,
)
from .models import Invoice, InvoiceItem
from .models.choices import (
    INVOICE_PAYMENT_STATUS_CHOICES,
    INVOICE_STATUS_CHOICES,
    INVOICE_STATUS_DRAFT,
    INVOICE_STATUS_PENDING_SEND,
    INVOICE_STATUS_SENT,
    INVOICE_STATUS_VOID,
)
from .permissions import user_can_access_invoice
from .selectors import invoice_list_for_user
from .serializers import InvoiceSerializer
from .services import (
    create_invoice,
    ensure_invoice_can_be_voided,
    ensure_invoice_has_no_confirmed_payments,
    generate_invoice,
    invoice_mark_sent,
    invoice_pdf_response,
    money,
    prepare_invoice_initial_from_estimate,
    prepare_invoice_items_initial_from_estimate,
    prepare_invoice_items_initial_from_project,
    recalculate_invoice,
    send_invoice_to_email,
    update_invoice,
    void_invoice,
)


INVOICE_DASHBOARD_STATUS_GROUPS = [
    {"key": INVOICE_STATUS_DRAFT, "label": "Draft", "statuses": [INVOICE_STATUS_DRAFT], "color": "#64748b"},
    {"key": INVOICE_STATUS_PENDING_SEND, "label": "Pending Send", "statuses": [INVOICE_STATUS_PENDING_SEND], "color": "#0868e8"},
    {"key": INVOICE_STATUS_SENT, "label": "Sent", "statuses": [INVOICE_STATUS_SENT], "color": "#0e9f6e"},
    {"key": INVOICE_STATUS_VOID, "label": "Void", "statuses": [INVOICE_STATUS_VOID], "color": "#6b7280"},
]


def get_invoice_status_group(status_key):
    for group in INVOICE_DASHBOARD_STATUS_GROUPS:
        if group["key"] == status_key:
            return group
    return None


def _decimal(value):
    try:
        return money(value or Decimal("0.00"))
    except Exception:
        return Decimal("0.00")


def project_queryset_for_user(user):
    queryset = Project.objects.select_related(
        "id_company",
        "id_client",
    ).all()

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def estimate_queryset_for_user(user):
    queryset = Estimate.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
    ).prefetch_related("items").all()

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def get_invoice_item_formset_class(extra=0):
    return inlineformset_factory(
        Invoice,
        InvoiceItem,
        form=InvoiceItemForm,
        extra=extra,
        can_delete=True,
        min_num=1,
        validate_min=True,
    )


def copy_estimate_item_photos_to_invoice(estimate, invoice):
    """Invoices intentionally do not carry item photos.

    Estimate items may have photos for proposal/proforma detail, but invoice
    items remain clean financial line items only.
    """
    return


def get_request_company_slug(request, company_slug=None):
    """Resolve the tenant slug without guessing or dropping company context."""
    if company_slug:
        return company_slug

    resolver_match = getattr(request, "resolver_match", None)
    resolver_kwargs = getattr(resolver_match, "kwargs", {}) or {}
    resolver_company_slug = resolver_kwargs.get("company_slug")

    if resolver_company_slug:
        return resolver_company_slug

    current_company = getattr(request, "current_company", None)
    if current_company and getattr(current_company, "slug", None):
        return current_company.slug

    user_company = getattr(getattr(request, "user", None), "id_company", None)
    if user_company and getattr(user_company, "slug", None):
        return user_company.slug

    return None


def get_active_invoice_namespace(request, company_slug=None):
    """Keep every invoice action inside the active legacy or company namespace."""
    resolver_match = getattr(request, "resolver_match", None)
    namespace = getattr(resolver_match, "namespace", "") or ""

    if namespace == "company_invoices":
        return namespace, get_request_company_slug(request, company_slug)

    if namespace == "invoices":
        return namespace, None

    active_company_slug = get_request_company_slug(request, company_slug)
    if active_company_slug:
        return "company_invoices", active_company_slug

    return "invoices", None


def reverse_invoice_url(request, view_name, company_slug=None, kwargs=None):
    """Reverse an invoice URL while preserving the tenant prefix."""
    kwargs = dict(kwargs or {})
    namespace, active_company_slug = get_active_invoice_namespace(
        request,
        company_slug,
    )

    if namespace == "company_invoices":
        if not active_company_slug:
            raise ValueError("A company slug is required for company invoice routes.")
        kwargs["company_slug"] = active_company_slug

    return reverse(f"{namespace}:{view_name}", kwargs=kwargs)


def redirect_invoice_url(request, view_name, company_slug=None, kwargs=None):
    return redirect(
        reverse_invoice_url(
            request=request,
            view_name=view_name,
            company_slug=company_slug,
            kwargs=kwargs,
        )
    )


def reverse_companion_url(
    request,
    legacy_namespace,
    company_namespace,
    view_name,
    company_slug=None,
    kwargs=None,
):
    """Reverse a related module URL using the invoice page tenant context."""
    kwargs = dict(kwargs or {})
    invoice_namespace, active_company_slug = get_active_invoice_namespace(
        request,
        company_slug,
    )

    if invoice_namespace == "company_invoices":
        if not active_company_slug:
            raise ValueError("A company slug is required for company module routes.")
        kwargs["company_slug"] = active_company_slug
        return reverse(f"{company_namespace}:{view_name}", kwargs=kwargs)

    return reverse(f"{legacy_namespace}:{view_name}", kwargs=kwargs)


def build_invoice_action_urls(request, invoice, company_slug=None):
    invoice_kwargs = {"id_invoice": invoice.id_invoice}
    urls = {
        "list": reverse_invoice_url(request, "invoice_list", company_slug=company_slug),
        "create": reverse_invoice_url(request, "invoice_create", company_slug=company_slug),
        "detail": reverse_invoice_url(
            request, "invoice_detail", company_slug=company_slug, kwargs=invoice_kwargs
        ),
        "edit": reverse_invoice_url(
            request, "invoice_update", company_slug=company_slug, kwargs=invoice_kwargs
        ),
        "generate": reverse_invoice_url(
            request, "invoice_generate", company_slug=company_slug, kwargs=invoice_kwargs
        ),
        "send": reverse_invoice_url(
            request, "invoice_send", company_slug=company_slug, kwargs=invoice_kwargs
        ),
        "mark_sent": reverse_invoice_url(
            request, "invoice_mark_sent", company_slug=company_slug, kwargs=invoice_kwargs
        ),
        "void": reverse_invoice_url(
            request, "invoice_void", company_slug=company_slug, kwargs=invoice_kwargs
        ),
        "pdf_style": reverse_invoice_url(
            request, "invoice_pdf_style", company_slug=company_slug, kwargs=invoice_kwargs
        ),
        "pdf": reverse_invoice_url(
            request, "invoice_pdf", company_slug=company_slug, kwargs=invoice_kwargs
        ),
        "payment_create": reverse_companion_url(
            request,
            "payments",
            "company_payments",
            "payment_create_for_invoice",
            company_slug=company_slug,
            kwargs=invoice_kwargs,
        ),
        "client_detail": None,
        "project_detail": None,
    }

    client_id = getattr(invoice, "id_client_id", None)
    project_id = getattr(invoice, "id_project_id", None)

    if client_id:
        urls["client_detail"] = reverse_companion_url(
            request,
            "clients",
            "company_clients",
            "client_detail",
            company_slug=company_slug,
            kwargs={"id_client": client_id},
        )

    if project_id:
        urls["project_detail"] = reverse_companion_url(
            request,
            "projects",
            "company_projects",
            "project_detail",
            company_slug=company_slug,
            kwargs={"id_project": project_id},
        )

    return urls


def build_payment_detail_url(request, payment, company_slug=None):
    if not payment:
        return None
    return reverse_companion_url(
        request,
        "payments",
        "company_payments",
        "payment_detail",
        company_slug=company_slug,
        kwargs={"id_payment": payment.id_payment},
    )

DOCUMENT_STATUS_UI = {
    INVOICE_STATUS_DRAFT: {"stage": "draft", "caption_class": "is-neutral"},
    INVOICE_STATUS_PENDING_SEND: {"stage": "pending_send", "caption_class": "is-blue"},
    "pending": {"stage": "pending_send", "caption_class": "is-blue"},
    INVOICE_STATUS_SENT: {"stage": "sent", "caption_class": "is-success"},
    "partially_paid": {"stage": "sent", "caption_class": "is-success"},
    "paid": {"stage": "sent", "caption_class": "is-success"},
    "overdue": {"stage": "sent", "caption_class": "is-success"},
    INVOICE_STATUS_VOID: {"stage": "void", "caption_class": "is-void"},
    "cancelled": {"stage": "void", "caption_class": "is-void"},
}

PAYMENT_STATUS_UI = {
    "unpaid": {"stage": "unpaid", "caption_class": "is-danger"},
    "partial": {"stage": "partial", "caption_class": "is-warning"},
    "paid": {"stage": "paid", "caption_class": "is-success"},
    "overpaid": {"stage": "overpaid", "caption_class": "is-violet"},
    "void": {"stage": "void", "caption_class": "is-void"},
}


def apply_invoice_ui_state(invoice):
    document_ui = DOCUMENT_STATUS_UI.get(getattr(invoice, "status", None), DOCUMENT_STATUS_UI[INVOICE_STATUS_DRAFT])
    payment_ui = PAYMENT_STATUS_UI.get(getattr(invoice, "payment_status", None), PAYMENT_STATUS_UI["unpaid"])

    invoice.document_stage_key = document_ui["stage"]
    invoice.document_caption_class = document_ui["caption_class"]
    invoice.payment_stage_key = payment_ui["stage"]
    invoice.payment_caption_class = payment_ui["caption_class"]
    return invoice


class InvoiceListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "invoices"
    permission_required = PERMISSION_VIEW
    template_name = "invoices/list.html"
    context_object_name = "invoices"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        queryset = invoice_list_for_user(self.request.user)

        search_query = (self.request.GET.get("q") or "").strip()
        status_filter = (self.request.GET.get("status") or "").strip()
        payment_filter = (self.request.GET.get("payment") or "").strip()

        valid_payment_statuses = {status for status, _label in INVOICE_PAYMENT_STATUS_CHOICES}
        status_group = get_invoice_status_group(status_filter)

        if status_group:
            queryset = queryset.filter(status__in=status_group["statuses"])

        if payment_filter in valid_payment_statuses:
            queryset = queryset.filter(payment_status=payment_filter)

        if search_query:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search_query)
                | Q(id_client__name__icontains=search_query)
                | Q(client_billing_name__icontains=search_query)
                | Q(client_billing_dni__icontains=search_query)
                | Q(id_project__name__icontains=search_query)
                | Q(project_name__icontains=search_query)
            )

        invoices = list(queryset)

        for invoice in invoices:
            try:
                recalculate_invoice(invoice)
            except Exception:
                pass
            invoice.ui_urls = build_invoice_action_urls(
                self.request,
                invoice,
                company_slug=self.kwargs.get("company_slug"),
            )
            apply_invoice_ui_state(invoice)

        return invoices

    def build_status_query_string(self, status=None):
        params = self.request.GET.copy()
        if status:
            params["status"] = status
        else:
            params.pop("status", None)
        return urlencode(params, doseq=True)

    def get_invoice_dashboard_summary(self):
        queryset = invoice_list_for_user(self.request.user)
        invoices = list(queryset)
        total_count = len(invoices)
        total_invoiced = Decimal("0.00")
        total_paid = Decimal("0.00")
        total_balance_due = Decimal("0.00")
        open_invoices = 0
        current_status = (self.request.GET.get("status") or "").strip()
        items = []
        start_degree = 0.0
        gradient_parts = []

        for invoice in invoices:
            try:
                recalculate_invoice(invoice)
            except Exception:
                pass
            if invoice.status != INVOICE_STATUS_VOID:
                total_invoiced += _decimal(getattr(invoice, "total", 0))
                total_paid += _decimal(getattr(invoice, "paid_amount", 0))
                total_balance_due += _decimal(getattr(invoice, "balance_due", 0))
                if _decimal(getattr(invoice, "balance_due", 0)) > Decimal("0.00"):
                    open_invoices += 1

        for group in INVOICE_DASHBOARD_STATUS_GROUPS:
            count = sum(1 for invoice in invoices if invoice.status in group["statuses"])
            percent = round((count / total_count) * 100) if total_count else 0
            degrees = (count / total_count) * 360 if total_count else 0
            end_degree = start_degree + degrees
            if count > 0 and degrees > 0:
                gradient_parts.append(f"{group['color']} {start_degree:.2f}deg {end_degree:.2f}deg")
            start_degree = end_degree
            items.append(
                {
                    "key": group["key"],
                    "label": group["label"],
                    "count": count,
                    "percent": percent,
                    "color": group["color"],
                    "query_string": self.build_status_query_string(group["key"]),
                    "is_active": current_status == group["key"],
                    "is_zero": count == 0,
                }
            )

        return {
            "total": total_count,
            "total_invoiced": money(total_invoiced),
            "total_paid": money(total_paid),
            "total_balance_due": money(total_balance_due),
            "open_invoices": open_invoices,
            "items": items,
            "chart_gradient": ", ".join(gradient_parts) if gradient_parts else "#e5e7eb 0deg 360deg",
            "all_query_string": self.build_status_query_string(None),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Invoices"
        context["can_create_invoices"] = user_can_module_action(
            self.request.user,
            "invoices",
            PERMISSION_CREATE,
        )
        context["can_edit_invoices"] = user_can_module_action(
            self.request.user,
            "invoices",
            PERMISSION_EDIT,
        )
        context["can_delete_invoices"] = user_can_module_action(
            self.request.user,
            "invoices",
            PERMISSION_DELETE,
        )
        context["can_approve_invoices"] = user_can_module_action(
            self.request.user,
            "invoices",
            PERMISSION_APPROVE,
        )
        context["can_create_payments"] = user_can_module_action(
            self.request.user,
            "payments",
            PERMISSION_CREATE,
        )
        context["invoice_status_options"] = [(group["key"], group["label"]) for group in INVOICE_DASHBOARD_STATUS_GROUPS]
        context["invoice_dashboard_summary"] = self.get_invoice_dashboard_summary()
        context["invoice_payment_status_options"] = INVOICE_PAYMENT_STATUS_CHOICES
        context["current_invoice_search"] = self.request.GET.get("q", "")
        context["current_invoice_status"] = self.request.GET.get("status", "")
        context["current_invoice_payment"] = self.request.GET.get("payment", "")
        context["invoice_list_url"] = reverse_invoice_url(
            self.request,
            "invoice_list",
            company_slug=self.kwargs.get("company_slug"),
        )
        context["invoice_create_url"] = reverse_invoice_url(
            self.request,
            "invoice_create",
            company_slug=self.kwargs.get("company_slug"),
        )
        filter_params = self.request.GET.copy()
        filter_params.pop("page", None)
        context["invoice_filter_query"] = urlencode(filter_params, doseq=True)

        return context


class InvoiceDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "invoices"
    permission_required = PERMISSION_VIEW
    model = Invoice
    template_name = "invoices/detail.html"
    context_object_name = "invoice"
    pk_url_kwarg = "id_invoice"
    login_url = "/login/"

    def get_queryset(self):
        return invoice_list_for_user(self.request.user)

    def get_object(self, queryset=None):
        invoice = super().get_object(queryset)
        self.invoice_configuration_error = ""

        try:
            recalculate_invoice(invoice)
        except ValueError as exc:
            # Legacy drafts can exist without a project because the database
            # relationship is nullable. The detail page must remain usable so
            # an authorized user can repair the record instead of receiving a
            # server error. Generation/PDF actions still enforce completeness.
            self.invoice_configuration_error = str(exc)

        apply_invoice_ui_state(invoice)
        return invoice

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Invoice Details"
        context["invoice_configuration_error"] = getattr(
            self,
            "invoice_configuration_error",
            "",
        )
        context["can_edit_invoices"] = user_can_module_action(
            self.request.user,
            "invoices",
            PERMISSION_EDIT,
        )
        context["can_delete_invoices"] = user_can_module_action(
            self.request.user,
            "invoices",
            PERMISSION_DELETE,
        )
        context["can_approve_invoices"] = user_can_module_action(
            self.request.user,
            "invoices",
            PERMISSION_APPROVE,
        )
        context["can_create_payments"] = user_can_module_action(
            self.request.user,
            "payments",
            PERMISSION_CREATE,
        )
        context["invoice_can_toggle_pdf_style"] = context["can_edit_invoices"]
        context["invoice_urls"] = build_invoice_action_urls(
            self.request,
            self.object,
            company_slug=self.kwargs.get("company_slug"),
        )
        context["invoice_items"] = list(self.object.items.all())
        context["invoice_can_void"] = False
        context["invoice_void_block_reason"] = ""
        try:
            ensure_invoice_can_be_voided(self.object)
            ensure_invoice_has_no_confirmed_payments(self.object)
            context["invoice_can_void"] = True
        except ValueError as exc:
            context["invoice_void_block_reason"] = str(exc)

        client_credit_balance = 0

        try:
            from apps.payments.services import get_credit_account_balance

            if self.object.id_company and self.object.id_client:
                client_credit_balance = get_credit_account_balance(
                    company=self.object.id_company,
                    client=self.object.id_client,
                )
        except Exception:
            client_credit_balance = 0

        context["client_credit_balance"] = client_credit_balance

        try:
            from apps.payments.models import ClientCreditMovement, Payment, PaymentAllocation
            from apps.payments.models.choices import CREDIT_MOVEMENT_APPLIED, PAYMENT_CONFIRMED_STATUSES

            context["payment_allocations"] = PaymentAllocation.objects.select_related(
                "id_payment",
                "id_payment__id_client",
                "id_project",
            ).filter(
                id_invoice=self.object,
                id_payment__status__in=PAYMENT_CONFIRMED_STATUSES,
            ).order_by(
                "-allocated_at",
                "-id_payment_allocation",
            )

            context["credit_applications"] = ClientCreditMovement.objects.select_related(
                "id_payment",
                "id_invoice",
            ).filter(
                id_invoice=self.object,
                movement_type=CREDIT_MOVEMENT_APPLIED,
            ).order_by(
                "-movement_date",
                "-id_credit_movement",
            )

            context["legacy_payments"] = Payment.objects.select_related(
                "id_client",
                "id_project",
            ).filter(
                id_invoice=self.object,
                status__in=PAYMENT_CONFIRMED_STATUSES,
                allocations__isnull=True,
            ).order_by(
                "-payment_date",
                "-id_payment",
            ).distinct()
        except Exception:
            context["payment_allocations"] = []
            context["credit_applications"] = []
            context["legacy_payments"] = []

        for allocation in context["payment_allocations"]:
            allocation.ui_detail_url = build_payment_detail_url(
                self.request,
                allocation.id_payment,
                company_slug=self.kwargs.get("company_slug"),
            )
        for credit_application in context["credit_applications"]:
            credit_application.ui_detail_url = build_payment_detail_url(
                self.request,
                getattr(credit_application, "id_payment", None),
                company_slug=self.kwargs.get("company_slug"),
            )
        for legacy_payment in context["legacy_payments"]:
            legacy_payment.ui_detail_url = build_payment_detail_url(
                self.request,
                legacy_payment,
                company_slug=self.kwargs.get("company_slug"),
            )

        return context


class InvoiceCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "invoices"
    permission_required = PERMISSION_CREATE
    model = Invoice
    form_class = InvoiceForm
    template_name = "invoices/form.html"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.project = None
        self.estimate = None

        id_project = (
            self.kwargs.get("id_project")
            or self.request.GET.get("project_id")
            or self.request.POST.get("project_id")
            or self.request.GET.get("id_project")
            or self.request.POST.get("id_project")
        )
        estimate_id = self.request.GET.get("estimate_id") or self.request.POST.get(
            "id_estimate"
        )

        if id_project:
            self.project = get_object_or_404(
                project_queryset_for_user(request.user),
                id_project=id_project,
            )

        if estimate_id:
            self.estimate = get_object_or_404(
                estimate_queryset_for_user(request.user),
                id_estimate=estimate_id,
                status="approved",
            )

            existing_invoice = Invoice.objects.filter(
                id_estimate=self.estimate,
            ).first()

            if existing_invoice and request.method.lower() == "get":
                messages.info(
                    request,
                    f"This estimate already has invoice {existing_invoice.invoice_number}.",
                )
                return redirect_invoice_url(
                    request,
                    "invoice_detail",
                    company_slug=self.kwargs.get("company_slug"),
                    kwargs={"id_invoice": existing_invoice.id_invoice},
                )

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()

        if self.estimate:
            initial.update(prepare_invoice_initial_from_estimate(self.estimate))

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["project"] = self.project
        kwargs["estimate"] = self.estimate
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Preserve the exact bound formset when form_valid/form_invalid sends it
        # back to the template. Rebuilding it can hide the real field errors.
        if "item_formset" not in context:
            if self.request.POST:
                context["item_formset"] = InvoiceItemFormSet(
                    self.request.POST,
                    self.request.FILES,
                )
            elif self.estimate:
                items_initial = list(
                    prepare_invoice_items_initial_from_estimate(self.estimate)
                )
                item_formset_class = get_invoice_item_formset_class(extra=0)
                context["item_formset"] = item_formset_class(
                    initial=items_initial,
                    queryset=InvoiceItem.objects.none(),
                )
            elif self.project:
                # A project invoice starts with exactly one editable item using
                # the project's scope and contract amount.
                items_initial = prepare_invoice_items_initial_from_project(self.project)
                item_formset_class = get_invoice_item_formset_class(extra=0)
                context["item_formset"] = item_formset_class(
                    initial=items_initial,
                    queryset=InvoiceItem.objects.none(),
                )
            else:
                # ``min_num=1`` already creates the one required blank form.
                # Adding extra=1 would render two rows: max(0, 1) + 1.
                item_formset_class = get_invoice_item_formset_class(extra=0)
                context["item_formset"] = item_formset_class(
                    queryset=InvoiceItem.objects.none(),
                )

        context["page_title"] = "Create Invoice"
        context["form_title"] = "Create Invoice"
        context["submit_label"] = "Generate Invoice"
        context["invoice_source_project"] = self.project
        context["project"] = self.project
        context["estimate"] = self.estimate
        context["form_action_url"] = self.request.get_full_path()
        context["cancel_url"] = reverse_invoice_url(
            self.request,
            "invoice_list",
            company_slug=self.kwargs.get("company_slug"),
        )
        if self.project:
            context["cancel_url"] = reverse_companion_url(
                self.request,
                "projects",
                "company_projects",
                "project_detail",
                company_slug=self.kwargs.get("company_slug"),
                kwargs={"id_project": self.project.id_project},
            )

        return context

    def get_success_url(self):
        return reverse_invoice_url(
            self.request,
            "invoice_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_invoice": self.object.id_invoice},
        )

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        item_formset = context["item_formset"]

        if not item_formset.is_valid():
            # The wizard renders the exact field error on step 3. Do not replace
            # it with a generic modal that gives no useful information.
            return self.render_to_response(
                self.get_context_data(form=form, item_formset=item_formset)
            )

        self.object = form.save(commit=False)
        self.object.status = INVOICE_STATUS_DRAFT
        submit_mode = (self.request.POST.get("submit_mode") or "generate").strip()

        try:
            with transaction.atomic():
                create_invoice(
                    invoice=self.object,
                    user=self.request.user,
                    status=INVOICE_STATUS_DRAFT,
                )
                item_formset.instance = self.object
                item_formset.save()
                copy_estimate_item_photos_to_invoice(self.estimate, self.object)
                recalculate_invoice(self.object)

                if submit_mode == "generate":
                    generate_invoice(
                        invoice=self.object,
                        user=self.request.user,
                    )

            if submit_mode == "draft":
                messages.success(self.request, "Invoice draft saved successfully.")
            else:
                messages.success(
                    self.request,
                    f"Invoice {self.object.invoice_number} generated successfully.",
                )
            return redirect(self.get_success_url())

        except Exception as error:
            messages.error(
                self.request,
                f"Invoice could not be saved: {error}",
            )
            return self.render_to_response(
                self.get_context_data(form=form, item_formset=item_formset)
            )

    def form_invalid(self, form):
        # Field and non-field errors are displayed inside the correct wizard step.
        return self.render_to_response(self.get_context_data(form=form))


class InvoiceUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "invoices"
    permission_required = PERMISSION_EDIT
    model = Invoice
    form_class = InvoiceForm
    template_name = "invoices/form.html"
    context_object_name = "invoice"
    pk_url_kwarg = "id_invoice"
    login_url = "/login/"

    def get_queryset(self):
        return invoice_list_for_user(self.request.user).filter(
            status=INVOICE_STATUS_DRAFT,
        )

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object.status != INVOICE_STATUS_DRAFT:
            messages.error(request, "This invoice can no longer be edited.")
            return redirect_invoice_url(
                request,
                "invoice_detail",
                company_slug=self.kwargs.get("company_slug"),
                kwargs={"id_invoice": self.object.id_invoice},
            )

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if "item_formset" not in context:
            if self.request.POST:
                context["item_formset"] = InvoiceItemFormSet(
                    self.request.POST,
                    self.request.FILES,
                    instance=self.object,
                )
            else:
                # extra=0: an existing draft shows only its saved items. No
                # additional blank row is injected; Add item creates one on demand.
                context["item_formset"] = InvoiceItemFormSet(instance=self.object)

        context["page_title"] = "Edit Invoice"
        context["form_title"] = "Edit Invoice"
        context["submit_label"] = "Update Invoice"
        context["invoice_source_project"] = self.object.id_project
        context["project"] = self.object.id_project
        context["estimate"] = self.object.id_estimate
        context["form_action_url"] = self.request.get_full_path()
        context["cancel_url"] = reverse_invoice_url(
            self.request,
            "invoice_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_invoice": self.object.id_invoice},
        )

        return context

    def get_success_url(self):
        return reverse_invoice_url(
            self.request,
            "invoice_detail",
            company_slug=self.kwargs.get("company_slug"),
            kwargs={"id_invoice": self.object.id_invoice},
        )

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        item_formset = context["item_formset"]

        if not item_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, item_formset=item_formset)
            )

        self.object = form.save(commit=False)
        submit_mode = (self.request.POST.get("submit_mode") or "draft").strip()

        try:
            with transaction.atomic():
                update_invoice(
                    invoice=self.object,
                    user=self.request.user,
                )
                item_formset.instance = self.object
                item_formset.save()
                recalculate_invoice(self.object)

                if submit_mode == "generate":
                    generate_invoice(
                        invoice=self.object,
                        user=self.request.user,
                    )

            if submit_mode == "generate":
                messages.success(
                    self.request,
                    f"Invoice {self.object.invoice_number} generated successfully.",
                )
            else:
                messages.success(
                    self.request,
                    f"Invoice {self.object.invoice_number or self.object.id_invoice} updated successfully.",
                )
            return redirect(self.get_success_url())

        except Exception as error:
            messages.error(
                self.request,
                f"Invoice could not be updated: {error}",
            )
            return self.render_to_response(
                self.get_context_data(form=form, item_formset=item_formset)
            )

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class InvoiceSendView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "invoices"
    permission_required = PERMISSION_EDIT
    template_name = "invoices/send.html"
    login_url = "/login/"

    def get_invoice(self, request, id_invoice):
        return get_object_or_404(
            invoice_list_for_user(request.user),
            id_invoice=id_invoice,
        )

    def validate_send_allowed(self, request, invoice):
        if invoice.status not in [INVOICE_STATUS_PENDING_SEND, INVOICE_STATUS_SENT]:
            messages.error(request, "Only pending send or sent invoices can be sent.")
            return False
        return True

    def get_initial_email(self, invoice):
        if invoice.client_billing_email:
            return invoice.client_billing_email

        client = invoice.id_client

        for field_name in ["email", "client_email", "billing_email", "contact_email"]:
            value = getattr(client, field_name, None)
            if value:
                return value

        return ""

    def get(self, request, id_invoice, company_slug=None, *args, **kwargs):
        invoice = self.get_invoice(request, id_invoice)

        if not self.validate_send_allowed(request, invoice):
            return redirect_invoice_url(
                request,
                "invoice_detail",
                company_slug=company_slug,
                kwargs={"id_invoice": invoice.id_invoice},
            )

        form = InvoiceSendEmailForm(
            initial={
                "recipient_email": self.get_initial_email(invoice),
                "subject": f"Invoice {invoice.invoice_number or invoice.id_invoice}",
                "message": "Please review the invoice details.",
            }
        )

        return render(
            request,
            self.template_name,
            {
                "invoice": invoice,
                "form": form,
                "invoice_urls": build_invoice_action_urls(
                    request, invoice, company_slug=company_slug
                ),
                "form_action_url": request.get_full_path(),
            },
        )

    def post(self, request, id_invoice, company_slug=None, *args, **kwargs):
        invoice = self.get_invoice(request, id_invoice)

        if not self.validate_send_allowed(request, invoice):
            return redirect_invoice_url(
                request,
                "invoice_detail",
                company_slug=company_slug,
                kwargs={"id_invoice": invoice.id_invoice},
            )

        form = InvoiceSendEmailForm(request.POST)

        if form.is_valid():
            try:
                send_invoice_to_email(
                    invoice=invoice,
                    recipient_email=form.cleaned_data["recipient_email"],
                    subject=form.cleaned_data.get("subject", ""),
                    message=form.cleaned_data.get("message", ""),
                    user=request.user,
                )

                messages.success(
                    request,
                    f"Invoice {invoice.invoice_number} sent successfully.",
                )

                return redirect_invoice_url(
                    request,
                    "invoice_detail",
                    company_slug=company_slug,
                    kwargs={"id_invoice": invoice.id_invoice},
                )

            except Exception as error:
                messages.error(request, f"Invoice could not be sent: {error}")

        return render(
            request,
            self.template_name,
            {
                "invoice": invoice,
                "form": form,
                "invoice_urls": build_invoice_action_urls(
                    request, invoice, company_slug=company_slug
                ),
                "form_action_url": request.get_full_path(),
            },
        )


@require_POST
def invoice_generate_view(request, id_invoice, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "invoices",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    invoice = get_object_or_404(
        invoice_list_for_user(request.user),
        id_invoice=id_invoice,
    )

    if not user_can_access_invoice(request.user, invoice):
        return HttpResponseForbidden("Permission denied.")

    try:
        generate_invoice(invoice=invoice, user=request.user)
        messages.success(
            request,
            f"Invoice {invoice.invoice_number} generated successfully.",
        )
    except Exception as error:
        messages.error(request, f"Invoice could not be generated: {error}")

    return redirect_invoice_url(request, "invoice_detail", company_slug=company_slug, kwargs={"id_invoice": invoice.id_invoice})


@require_POST
def invoice_mark_sent_view(request, id_invoice, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "invoices",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    invoice = get_object_or_404(
        invoice_list_for_user(request.user),
        id_invoice=id_invoice,
    )

    if not user_can_access_invoice(request.user, invoice):
        return HttpResponseForbidden("Permission denied.")

    try:
        invoice_mark_sent(invoice)
        messages.success(request, "Invoice marked as sent successfully.")
    except Exception as error:
        messages.error(request, f"Invoice could not be marked as sent: {error}")

    return redirect_invoice_url(request, "invoice_detail", company_slug=company_slug, kwargs={"id_invoice": invoice.id_invoice})


@require_http_methods(["GET", "POST"])
def invoice_void_view(request, id_invoice, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "invoices",
        PERMISSION_APPROVE,
    )

    if permission_response:
        return permission_response

    invoice = get_object_or_404(
        invoice_list_for_user(request.user),
        id_invoice=id_invoice,
    )

    if not user_can_access_invoice(request.user, invoice):
        return HttpResponseForbidden("Permission denied.")

    if request.method != "POST":
        messages.error(request, "Use the protected Void action and provide a reason. Invoice status was not changed.")
        return redirect_invoice_url(
            request,
            "invoice_detail",
            company_slug=company_slug,
            kwargs={"id_invoice": invoice.id_invoice},
        )

    reason = request.POST.get("void_reason", "").strip()

    try:
        void_invoice(invoice=invoice, user=request.user, reason=reason)
        messages.success(request, "Invoice voided successfully.")
        return redirect_invoice_url(request, "invoice_list", company_slug=company_slug)
    except Exception as error:
        messages.error(request, f"Invoice could not be voided: {error}")
        return redirect_invoice_url(request, "invoice_detail", company_slug=company_slug, kwargs={"id_invoice": invoice.id_invoice})


@require_http_methods(["GET", "POST"])
def invoice_pdf_style_view(request, id_invoice, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "invoices",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    invoice = get_object_or_404(
        invoice_list_for_user(request.user),
        id_invoice=id_invoice,
    )

    if not user_can_access_invoice(request.user, invoice):
        return HttpResponseForbidden("Permission denied.")

    if request.method == "POST":
        invoice.pdf_header_dark = request.POST.get("pdf_header_dark") in ["1", "on", "true", "True", "yes"]
    else:
        # Fallback for cached links or browser navigation to /pdf-style/.
        # It avoids a hard 405 and still performs the intended toggle.
        requested_value = request.GET.get("pdf_header_dark")
        if requested_value in ["0", "1", "on", "true", "false"]:
            invoice.pdf_header_dark = requested_value in ["1", "on", "true"]
        else:
            invoice.pdf_header_dark = not bool(invoice.pdf_header_dark)

    invoice.save(update_fields=["pdf_header_dark", "last_modified_at"])

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    wants_json = "application/json" in request.headers.get("Accept", "")
    if is_ajax or wants_json:
        return JsonResponse(
            {
                "ok": True,
                "pdf_header_dark": bool(invoice.pdf_header_dark),
            }
        )

    messages.success(request, "Invoice PDF logo background updated successfully.")
    return redirect_invoice_url(request, "invoice_detail", company_slug=company_slug, kwargs={"id_invoice": invoice.id_invoice})


@require_GET
def invoice_pdf_view(request, id_invoice, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "invoices",
        PERMISSION_VIEW,
    )

    if permission_response:
        return permission_response

    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
            "id_estimate",
        ).prefetch_related("items"),
        id_invoice=id_invoice,
    )

    if not user_can_access_invoice(request.user, invoice):
        return HttpResponseForbidden("Permission denied.")

    try:
        return invoice_pdf_response(invoice)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))


class InvoiceViewSet(TenantModelViewSet):
    module_name = "invoices"
    queryset = Invoice.objects.select_related(
        "id_company",
        "id_client",
        "id_project",
        "id_estimate",
    ).prefetch_related("items").all()
    serializer_class = InvoiceSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return invoice_list_for_user(self.request.user)

    def perform_create(self, serializer):
        company = serializer.validated_data.get("id_company")
        client = serializer.validated_data.get("id_client")
        project = serializer.validated_data.get("id_project")
        estimate = serializer.validated_data.get("id_estimate")

        if not self.request.user.is_superuser:
            company = self.request.user.id_company

        if not company:
            raise PermissionDenied("Company is required.")

        if not client:
            raise PermissionDenied("Client is required.")

        if not project:
            raise PermissionDenied("Project is required.")

        if client.id_company_id != company.id_company:
            raise PermissionDenied("Client must belong to the selected company.")

        if project.id_company_id != company.id_company:
            raise PermissionDenied("Project must belong to the selected company.")

        if project.id_client_id != client.id_client:
            raise PermissionDenied("Project must belong to the selected client.")

        if estimate and estimate.id_company_id != company.id_company:
            raise PermissionDenied("Estimate must belong to the selected company.")

        instance = serializer.save(
            id_company=company,
            id_client=client,
            id_project=project,
            status=INVOICE_STATUS_DRAFT,
        )

        recalculate_invoice(instance)

    def perform_update(self, serializer):
        instance = self.get_object()

        if not user_can_access_invoice(self.request.user, instance):
            raise PermissionDenied("You can only update invoices from your company.")

        if instance.status != INVOICE_STATUS_DRAFT:
            raise PermissionDenied("This invoice can no longer be edited.")

        updated_instance = serializer.save()
        recalculate_invoice(updated_instance)

    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        if not user_can_module_action(request.user, "invoices", PERMISSION_EDIT):
            raise PermissionDenied("You do not have permission to generate invoices.")

        invoice = self.get_object()
        generate_invoice(invoice=invoice, user=request.user)

        return Response(
            {
                "detail": "Invoice generated successfully.",
                "invoice_id": invoice.id_invoice,
                "status": invoice.status,
            }
        )

    @action(detail=True, methods=["post"])
    def mark_sent(self, request, pk=None):
        if not user_can_module_action(request.user, "invoices", PERMISSION_EDIT):
            raise PermissionDenied("You do not have permission to edit invoices.")

        invoice = self.get_object()
        invoice_mark_sent(invoice)

        return Response(
            {
                "detail": "Invoice marked as sent successfully.",
                "invoice_id": invoice.id_invoice,
                "status": invoice.status,
            }
        )

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        if not user_can_module_action(request.user, "invoices", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to void invoices.")

        invoice = self.get_object()
        reason = request.data.get("void_reason", "")

        void_invoice(invoice=invoice, user=request.user, reason=reason)

        return Response(
            {
                "detail": "Invoice voided successfully.",
                "invoice_id": invoice.id_invoice,
                "status": invoice.status,
                "payment_status": invoice.payment_status,
            }
        )