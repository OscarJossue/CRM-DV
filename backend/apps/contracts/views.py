from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from urllib.parse import urlencode
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.http import require_GET, require_POST




from apps.core.dashboard_ui import build_dashboard_items
from apps.core.mixins import TenantModelViewSet

from datetime import date, datetime
from decimal import Decimal

from django.db.models import Model
from django.db.models.manager import BaseManager
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
from apps.projects.models import Project

from .forms import ContractForm, ContractSendEmailForm
from .models import Contract
from .models.choices import (
    CONTRACT_STATUS_CHOICES,
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_PENDING,
)
from .permissions import user_can_access_contract
from .selectors import contract_list_for_user
from .serializers import ContractSerializer
from .services import (
    DEFAULT_PAYMENT_TERMS,
    DEFAULT_CANCELLATION_TERMS,
    DEFAULT_GUARANTEE_TERMS,
    DEFAULT_MISCELLANEOUS_TERMS,
    contract_activate,
    contract_complete,
    contract_create_instance,
    contract_mark_generated,
    contract_mark_signed,
    contract_pdf_response,
    contract_update_instance,
    contract_void,
    send_contract_to_email,
)

from .public_services import (
    ContractPublicFlowError,
    approve_contract_publicly,
    mark_contract_as_viewed,
    reject_contract_publicly,
)
def make_json_safe(value):
    if isinstance(value, BaseManager):
        return []

    if isinstance(value, Model):
        return str(value)

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            make_json_safe(item)
            for item in value
        ]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    return str(value)
def project_queryset_for_user(user):
    queryset = Project.objects.select_related(
        "id_company",
        "id_client",
    ).all()

    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(
        id_company_id=user.id_company_id,
    )


def contract_queryset_for_user(user):
    return contract_list_for_user(user)


class ContractListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = "contracts"
    permission_required = PERMISSION_VIEW
    template_name = "contracts/list.html"
    context_object_name = "contracts"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        base_queryset = contract_list_for_user(self.request.user)
        self.contract_base_queryset = base_queryset
        queryset = base_queryset
        query = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        if query:
            for token in query.split():
                queryset = queryset.filter(
                    Q(contract_number__icontains=token)
                    | Q(contract_title__icontains=token)
                    | Q(client_name__icontains=token)
                    | Q(id_client__client_code__icontains=token)
                    | Q(id_client__name__icontains=token)
                    | Q(id_client__dni__icontains=token)
                    | Q(project_name__icontains=token)
                    | Q(id_project__project_code__icontains=token)
                    | Q(id_project__name__icontains=token)
                )

        valid_statuses = {value for value, _label in CONTRACT_STATUS_CHOICES}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Contracts"
        context["can_create_contracts"] = user_can_module_action(self.request.user, "contracts", PERMISSION_CREATE)
        context["can_edit_contracts"] = user_can_module_action(self.request.user, "contracts", PERMISSION_EDIT)
        context["can_delete_contracts"] = user_can_module_action(self.request.user, "contracts", PERMISSION_DELETE)
        context["can_approve_contracts"] = user_can_module_action(self.request.user, "contracts", PERMISSION_APPROVE)

        status_ui = {
            "draft": ("Draft", "is-neutral"),
            "pending": ("Pending", "is-warning"),
            "generated": ("Generated", "is-blue"),
            "sent": ("Sent", "is-warning"),
            "viewed": ("Viewed", "is-violet"),
            "approved": ("Approved", "is-success"),
            "signed": ("Signed", "is-success"),
            "rejected": ("Rejected", "is-danger"),
            "void": ("Void", "is-danger"),
            "active": ("Active", "is-blue"),
            "completed": ("Completed", "is-success"),
            "cancelled": ("Cancelled", "is-danger"),
        }
        for contract in context.get("contracts", []):
            contract.status_label, contract.status_class = status_ui.get(contract.status, (contract.get_status_display(), "is-neutral"))

        current_status = self.request.GET.get("status", "")
        context["contract_filters"] = {"q": self.request.GET.get("q", ""), "status": current_status}
        base_queryset = getattr(self, "contract_base_queryset", contract_list_for_user(self.request.user))
        counts = {row["status"]: row["total"] for row in base_queryset.values("status").annotate(total=Count("id_contract"))}
        context["contract_dashboard_items"] = build_dashboard_items(
            self.request,
            [
                {"value": "draft", "label": "Draft", "caption": "Editable document", "icon": "bi-pencil-square", "color": "#64748b"},
                {"value": "pending", "label": "Pending", "caption": "Legacy pending contract", "icon": "bi-hourglass-split", "color": "#d97706"},
                {"value": "generated", "label": "Generated", "caption": "Document generated", "icon": "bi-file-earmark-check", "color": "#0868e8"},
                {"value": "sent", "label": "Sent", "caption": "Sent to customer", "icon": "bi-send", "color": "#f59e0b"},
                {"value": "viewed", "label": "Viewed", "caption": "Opened by customer", "icon": "bi-eye", "color": "#7c3aed"},
                {"value": "approved", "label": "Approved", "caption": "Customer approved", "icon": "bi-check2-circle", "color": "#0f8f83"},
                {"value": "active", "label": "Active", "caption": "Legacy active contract", "icon": "bi-play-circle", "color": "#1685f3"},
                {"value": "signed", "label": "Signed", "caption": "Final signed contract", "icon": "bi-pen", "color": "#0e9f6e"},
                {"value": "completed", "label": "Completed", "caption": "Legacy completed contract", "icon": "bi-check-all", "color": "#15803d"},
                {"value": "rejected", "label": "Rejected", "caption": "Customer rejected", "icon": "bi-x-circle", "color": "#ef3340"},
                {"value": "void", "label": "Void", "caption": "Voided contract", "icon": "bi-slash-circle", "color": "#6b7280"},
                {"value": "cancelled", "label": "Cancelled", "caption": "Legacy cancelled contract", "icon": "bi-x-octagon", "color": "#991b1b"},
            ],
            counts,
            active_value=current_status,
        )
        params = self.request.GET.copy(); params.pop("page", None)
        context["contract_filter_query"] = urlencode(params, doseq=True)
        return context

def build_public_contract_url(request, contract, company_slug=None):
    base_url = getattr(settings, "CRM_PUBLIC_BASE_URL", "").rstrip("/")

    if not company_slug:
        company = getattr(contract, "id_company", None)
        company_slug = getattr(company, "slug", "") or ""

    if company_slug:
        path = f"/{str(company_slug).strip('/')}/contracts/public/{contract.public_token}/"
    else:
        path = f"/contracts/public/{contract.public_token}/"

    if base_url:
        return f"{base_url}{path}"

    return request.build_absolute_uri(path)
def get_public_contract_context(contract, page_title="Contract Preview", company_slug=None, **extra_context):
    context = {
        "contract": contract,
        "page_title": page_title,
        "context_payment_terms": contract.payment_terms or DEFAULT_PAYMENT_TERMS,
        "context_cancellation_terms": contract.cancellation_terms or DEFAULT_CANCELLATION_TERMS,
        "context_guarantee_terms": contract.guarantee_terms or DEFAULT_GUARANTEE_TERMS,
        "context_miscellaneous_terms": contract.miscellaneous_terms or DEFAULT_MISCELLANEOUS_TERMS,
        "public_approve_action": "approve/",
        "public_reject_action": "reject/",
        "public_sign_action": f"sign/{contract.sign_token}/",
    }

    context.update(extra_context)

    return context
class ContractDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = "contracts"
    permission_required = PERMISSION_VIEW
    model = Contract
    template_name = "contracts/detail.html"
    context_object_name = "contract"
    pk_url_kwarg = "id_contract"
    login_url = "/login/"

    def get_queryset(self):
        return contract_list_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Contract Details"

        company_slug = self.kwargs.get("company_slug")


        context["public_contract_url"] = build_public_contract_url(
            request=self.request,
            contract=self.object,
            company_slug=company_slug,
        )



        
        context["can_create_contracts"] = user_can_module_action(
            self.request.user,
            "contracts",
            PERMISSION_CREATE,
        )
        context["can_edit_contracts"] = user_can_module_action(
            self.request.user,
            "contracts",
            PERMISSION_EDIT,
        )
        context["can_delete_contracts"] = user_can_module_action(
            self.request.user,
            "contracts",
            PERMISSION_DELETE,
        )
        context["can_approve_contracts"] = user_can_module_action(
            self.request.user,
            "contracts",
            PERMISSION_APPROVE,
        )

        return context


class ContractCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = "contracts"
    permission_required = PERMISSION_CREATE
    model = Contract
    form_class = ContractForm
    template_name = "contracts/form.html"
    success_url = reverse_lazy("contracts:contract_list")
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.project = None
        id_project = self.kwargs.get("id_project")

        if id_project:
            self.project = get_object_or_404(
                project_queryset_for_user(request.user),
                id_project=id_project,
            )

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["project"] = self.project

        return kwargs

    def get_success_url(self):
        return reverse_lazy(
            "contracts:contract_detail",
            kwargs={"id_contract": self.object.id_contract},
        )

    def form_valid(self, form):
        self.object = form.save(commit=False)

        try:
            contract_create_instance(
                contract=self.object,
                user=self.request.user,
            )
            form.save_evidence_images(self.object)
            

            action = self.request.POST.get("contract_action", "draft")

            if action == "generate":
                contract_mark_generated(
                    contract=self.object,
                    user=self.request.user,
                )

                messages.success(
                    self.request,
                    "Contract saved and generated successfully.",
                )
            else:
                messages.success(
                    self.request,
                    "Contract saved as draft successfully.",
                )

            return redirect(self.get_success_url())

        except Exception as error:
            messages.error(
                self.request,
                f"Contract could not be created: {error}",
            )

            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Please review the contract form.",
        )

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Create Contract"
        context["form_title"] = "Create Contract"
        context["submit_label"] = "Save Draft"
        context["project"] = self.project
        raw_client_snapshot_data = getattr(
            context.get("form"),
            "client_snapshot_data",
            {},
        )

        raw_project_snapshot_data = getattr(
            context.get("form"),
            "project_snapshot_data",
            {},
        )

        context["client_snapshot_data"] = make_json_safe(raw_client_snapshot_data)
        context["project_snapshot_data"] = make_json_safe(raw_project_snapshot_data)
        return context


class ContractUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = "contracts"
    permission_required = PERMISSION_EDIT
    model = Contract
    form_class = ContractForm
    template_name = "contracts/form.html"
    context_object_name = "contract"
    pk_url_kwarg = "id_contract"
    login_url = "/login/"

    def get_queryset(self):
        return contract_list_for_user(self.request.user).filter(
            status__in=[
                CONTRACT_STATUS_DRAFT,
                CONTRACT_STATUS_PENDING,
            ]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user

        return kwargs

    def get_success_url(self):
        return reverse_lazy(
            "contracts:contract_detail",
            kwargs={"id_contract": self.object.id_contract},
        )

    def form_valid(self, form):
        self.object = form.save(commit=False)

        try:
            contract_update_instance(
                contract=self.object,
                user=self.request.user,
            )
            form.save_evidence_images(self.object)

            action = self.request.POST.get("contract_action", "draft")

            if action == "generate":
                contract_mark_generated(
                    contract=self.object,
                    user=self.request.user,
                )

                messages.success(
                    self.request,
                    "Contract updated and generated successfully.",
                )
            else:
                messages.success(
                    self.request,
                    "Contract updated successfully.",
                )

            return redirect(self.get_success_url())

        except Exception as error:
            messages.error(
                self.request,
                f"Contract could not be updated: {error}",
            )

            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Please review the contract form.",
        )

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["page_title"] = "Edit Contract"
        context["form_title"] = "Edit Contract"
        context["submit_label"] = "Update Contract"
        context["project"] = self.object.id_project

        raw_client_snapshot_data = getattr(
            context.get("form"),
            "client_snapshot_data",
            {},
        )

        raw_project_snapshot_data = getattr(
            context.get("form"),
            "project_snapshot_data",
            {},
        )

        context["client_snapshot_data"] = make_json_safe(raw_client_snapshot_data)
        context["project_snapshot_data"] = make_json_safe(raw_project_snapshot_data)

        return context


class ContractPDFView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = "contracts"
    permission_required = PERMISSION_VIEW
    login_url = "/login/"

    def get(self, request, id_contract, company_slug=None, *args, **kwargs):
        contract = get_object_or_404(
            contract_queryset_for_user(request.user),
            id_contract=id_contract,
        )

        try:
            return contract_pdf_response(contract)

        except Exception as error:
            messages.error(
                request,
                f"Contract PDF could not be generated: {error}",
            )

            return redirect(
                "contracts:contract_detail",
                id_contract=contract.id_contract,
            )


class ContractSendView(LoginRequiredMixin, ModulePermissionRequiredMixin, FormView):
    module_name = "contracts"
    permission_required = PERMISSION_EDIT
    form_class = ContractSendEmailForm
    template_name = "contracts/send.html"
    login_url = "/login/"

    def dispatch(self, request, *args, **kwargs):
        self.contract = get_object_or_404(
            contract_queryset_for_user(request.user),
            id_contract=self.kwargs["id_contract"],
        )

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()

        contract_number = self.contract.contract_number or self.contract.id_contract
        resend_label = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")

        initial["recipient_email"] = self.contract.client_email

        if self.contract.status in ["sent", "viewed", "approved"]:
            initial["subject"] = f"Resend Contract {contract_number} - {resend_label}"
        else:
            initial["subject"] = f"Contract {contract_number} - {resend_label}"

        initial["message"] = (
            "Please review the attached contract for your project. "
            "Let us know if you have any questions."
        )

        return initial

    def get_success_url(self):
        return reverse_lazy(
            "contracts:contract_detail",
            kwargs={"id_contract": self.contract.id_contract},
        )

    def form_valid(self, form):
        try:
            company_slug = self.kwargs.get("company_slug")

            public_contract_url = build_public_contract_url(
                request=self.request,
                contract=self.contract,
                company_slug=company_slug,
            )

            sent_count = send_contract_to_email(
                contract=self.contract,
                recipient_email=form.cleaned_data["recipient_email"],
                subject=form.cleaned_data.get("subject", ""),
                message=form.cleaned_data.get("message", ""),
                user=self.request.user,
                public_contract_url=public_contract_url,
            )

            messages.success(
                self.request,
                (
                    f"Contract email sent successfully to {form.cleaned_data['recipient_email']} "
                    f"with subject: {form.cleaned_data.get('subject', '')}. "
                    f"SMTP result: {sent_count}"
                ),
            )

            return redirect(self.get_success_url())

        except Exception as error:
            messages.error(
                self.request,
                f"Contract could not be sent: {error}",
            )

            return self.form_invalid(form)
    def form_invalid(self, form):
        messages.error(
            self.request,
            "Please review the email form.",
        )

        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.contract.status in ["sent", "viewed", "approved"]:
            context["page_title"] = "Resend Contract"
            context["form_title"] = "Resend Contract"
            context["submit_label"] = "Resend Contract"
        else:
            context["page_title"] = "Send Contract"
            context["form_title"] = "Send Contract"
            context["submit_label"] = "Send Contract"

        context["contract"] = self.contract

        return context


@require_POST
def contract_generate_view(request, id_contract, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "contracts",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    contract = get_object_or_404(
        contract_queryset_for_user(request.user),
        id_contract=id_contract,
    )

    try:
        contract_mark_generated(
            contract=contract,
            user=request.user,
        )

        messages.success(
            request,
            "Contract generated successfully.",
        )

    except Exception as error:
        messages.error(
            request,
            f"Contract could not be generated: {error}",
        )

    return redirect(
        "contracts:contract_detail",
        id_contract=contract.id_contract,
    )


@require_POST
def contract_mark_signed_view(request, id_contract, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "contracts",
        PERMISSION_APPROVE,
    )

    if permission_response:
        return permission_response

    contract = get_object_or_404(
        contract_queryset_for_user(request.user),
        id_contract=id_contract,
    )

    if not user_can_access_contract(request.user, contract):
        return HttpResponseForbidden("Permission denied.")

    try:
        contract_mark_signed(
            contract=contract,
            user=request.user,
        )

        messages.success(
            request,
            "Contract marked as signed successfully.",
        )

    except Exception as error:
        messages.error(
            request,
            f"Contract could not be marked as signed: {error}",
        )

    return redirect(
        "contracts:contract_detail",
        id_contract=contract.id_contract,
    )


@require_POST
def contract_void_view(request, id_contract, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "contracts",
        PERMISSION_DELETE,
    )

    if permission_response:
        return permission_response

    contract = get_object_or_404(
        contract_queryset_for_user(request.user),
        id_contract=id_contract,
    )

    if not user_can_access_contract(request.user, contract):
        return HttpResponseForbidden("Permission denied.")

    reason = request.POST.get("void_reason", "").strip()

    try:
        contract_void(
            contract=contract,
            user=request.user,
            reason=reason,
        )

        messages.success(
            request,
            "Contract voided successfully.",
        )

    except Exception as error:
        messages.error(
            request,
            f"Contract could not be voided: {error}",
        )

    return redirect(
        "contracts:contract_detail",
        id_contract=contract.id_contract,
    )


@require_POST
def contract_activate_view(request, id_contract, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "contracts",
        PERMISSION_EDIT,
    )

    if permission_response:
        return permission_response

    contract = get_object_or_404(
        contract_queryset_for_user(request.user),
        id_contract=id_contract,
    )

    if not user_can_access_contract(request.user, contract):
        return HttpResponseForbidden("Permission denied.")

    try:
        contract_activate(contract)

        messages.success(
            request,
            "Contract activated successfully.",
        )

    except Exception as error:
        messages.error(
            request,
            f"Contract could not be activated: {error}",
        )

    return redirect(
        "contracts:contract_detail",
        id_contract=contract.id_contract,
    )


@require_POST
def contract_complete_view(request, id_contract, company_slug=None):
    permission_response = require_module_action_or_403(
        request.user,
        "contracts",
        PERMISSION_APPROVE,
    )

    if permission_response:
        return permission_response

    contract = get_object_or_404(
        contract_queryset_for_user(request.user),
        id_contract=id_contract,
    )

    if not user_can_access_contract(request.user, contract):
        return HttpResponseForbidden("Permission denied.")

    try:
        contract_complete(contract)

        messages.success(
            request,
            "Contract completed successfully.",
        )

    except Exception as error:
        messages.error(
            request,
            f"Contract could not be completed: {error}",
        )

    return redirect(
        "contracts:contract_detail",
        id_contract=contract.id_contract,
    )


@require_POST
def contract_cancel_view(request, id_contract, company_slug=None):
    return contract_void_view(
        request,
        id_contract,
    )


class ContractViewSet(TenantModelViewSet):
    module_name = "contracts"
    queryset = Contract.objects.select_related(
        "id_company",
        "id_client",
        "id_client__id_company",
        "id_project",
        "id_project__id_company",
        "created_by",
        "updated_by",
    ).all()
    serializer_class = ContractSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = None

    def get_queryset(self):
        return contract_list_for_user(self.request.user)

    def perform_create(self, serializer):
        contract = serializer.save()

        if not user_can_access_contract(self.request.user, contract):
            raise PermissionDenied("You can only create contracts for your company.")

        contract_create_instance(
            contract=contract,
            user=self.request.user,
        )

    def perform_update(self, serializer):
        contract = self.get_object()

        if not user_can_access_contract(self.request.user, contract):
            raise PermissionDenied("You can only update contracts from your company.")

        instance = serializer.save()

        contract_update_instance(
            contract=instance,
            user=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        if not user_can_module_action(request.user, "contracts", PERMISSION_EDIT):
            raise PermissionDenied("You do not have permission to generate contracts.")

        contract = self.get_object()

        contract_mark_generated(
            contract=contract,
            user=request.user,
        )

        return Response(
            {
                "detail": "Contract generated successfully.",
                "contract_id": contract.id_contract,
                "status": contract.status,
            }
        )

    @action(detail=True, methods=["post"])
    def mark_signed(self, request, pk=None):
        if not user_can_module_action(request.user, "contracts", PERMISSION_APPROVE):
            raise PermissionDenied("You do not have permission to sign contracts.")

        contract = self.get_object()

        contract_mark_signed(
            contract=contract,
            user=request.user,
        )

        return Response(
            {
                "detail": "Contract marked as signed successfully.",
                "contract_id": contract.id_contract,
                "status": contract.status,
            }
        )

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        if not user_can_module_action(request.user, "contracts", PERMISSION_DELETE):
            raise PermissionDenied("You do not have permission to void contracts.")

        contract = self.get_object()
        reason = request.data.get("void_reason", "")

        contract_void(
            contract=contract,
            user=request.user,
            reason=reason,
        )

        return Response(
            {
                "detail": "Contract voided successfully.",
                "contract_id": contract.id_contract,
                "status": contract.status,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self.void(
            request,
            pk=pk,
        )


@never_cache
@xframe_options_deny
@require_GET
def public_contract_preview_view(request, token, company_slug=None):
    """
    Public contract preview for customers.
    No CRM login required.
    Access is protected by public_token.
    """
    contract = get_object_or_404(
        Contract.objects.select_related(
            "id_company",
            "id_client",
            "id_project",
            "id_estimate",
        ).prefetch_related(
            "evidence_photos",
        ),
        public_token=token,
    )

    mark_contract_as_viewed(contract)

    return render(
        request,
        "contracts/public_preview.html",
        get_public_contract_context(
            contract,
            page_title=f"Contract {contract.contract_number or contract.id_contract}",
            company_slug=company_slug,
        ),
    )



@never_cache
@xframe_options_deny
@require_POST
def public_contract_approve_view(request, token, company_slug=None):
    from apps.contracts.public_services import (
        ContractPublicFlowError,
        approve_contract_publicly,
        get_public_contract_by_token,
    )
    from apps.contracts.notification_services import notify_contract_approved_to_contract_users

    contract = get_public_contract_by_token(token)

    try:
        approve_contract_publicly(contract)

        try:
            notify_contract_approved_to_contract_users(contract)
        except Exception:
            pass

        if company_slug:
            return redirect(f"/{company_slug}/contracts/public/{contract.public_token}/?sign=1")

        return redirect(f"/contracts/public/{contract.public_token}/?sign=1")

    except ContractPublicFlowError as error:
        messages.error(request, str(error))

        if company_slug:
            return redirect(f"/{company_slug}/contracts/public/{contract.public_token}/")

        return redirect(f"/contracts/public/{contract.public_token}/")

@never_cache
@xframe_options_deny
@require_POST
def public_contract_reject_view(request, token, company_slug=None):
    from apps.contracts.public_services import (
        ContractPublicFlowError,
        get_public_contract_by_token,
        reject_contract_publicly,
    )
    from apps.contracts.notification_services import notify_contract_rejected_to_contract_users

    contract = get_public_contract_by_token(token)

    try:
        reject_contract_publicly(
            contract=contract,
            reason=rejection_reason,
        )

        try:
            notify_contract_rejected_to_contract_users(contract)
        except Exception:
            pass

        return render(
            request,
            "contracts/public_result.html",
            {
                "contract": contract,
                "result_title": "Contract Rejected",
                "result_message": "Your rejection reason has been submitted successfully.",
                "result_type": "danger",
            },
        )

    except ContractPublicFlowError as error:
        return render(
            request,
            "contracts/public_preview.html",
            get_public_contract_context(
                contract,
                page_title="Contract Preview",
                rejection_error=str(error),
                rejection_reason=rejection_reason,
            ),
        )
@never_cache
@xframe_options_deny
@require_POST
def public_contract_sign_view(request, token, sign_token, company_slug=None):
    from apps.contracts.public_services import get_public_contract_by_token
    from apps.contracts.signature_services import (
        ContractSignatureError,
        sign_contract_publicly,
    )
    from apps.contracts.notification_services import notify_contract_signed_to_contract_users

    contract = get_public_contract_by_token(token)

    try:
        signed_contract = sign_contract_publicly(
            contract=contract,
            signature_data=signature_data,
            sign_token=sign_token,
        )

        try:
            notify_contract_signed_to_contract_users(signed_contract)
        except Exception:
            pass

        try:
            from apps.contracts.signed_email_services import send_contract_signed_customer_email

            if company_slug:
                public_contract_url = f"/{company_slug}/contracts/public/{signed_contract.public_token}/"
            else:
                public_contract_url = f"/contracts/public/{signed_contract.public_token}/"

            public_contract_url = request.build_absolute_uri(public_contract_url)

            send_contract_signed_customer_email(
                contract=signed_contract,
                public_contract_url=public_contract_url,
            )
        except Exception:
            pass

        return render(
            request,
            "contracts/public_result.html",
            {
                "contract": contract,
                "result_title": "Contract Signed Successfully",
                "result_message": "Thank you. Your contract has been approved and signed successfully.",
                "result_type": "success",
            },
        )

    except ContractSignatureError as error:
        return render(
            request,
            "contracts/public_preview.html",
            get_public_contract_context(
                contract,
                page_title="Contract Preview",
                signature_error=str(error),
            ),
        )

