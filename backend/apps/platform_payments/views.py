import csv

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.core.platform_permissions import (
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    PlatformPermissionRequiredMixin,
    user_can_platform_action,
)
from apps.platform_audit.models.choices import (
    PLATFORM_AUDIT_ACTION_CREATE,
    PLATFORM_AUDIT_ACTION_EXPORT,
    PLATFORM_AUDIT_ACTION_UPDATE,
)
from apps.platform_audit.services import log_platform_action
from apps.platform_users.constants import PLATFORM_MODULE_PAYMENTS

from .forms import PlatformPaymentForm
from .models import PlatformPayment
from .models.choices import (
    PAYMENT_METHOD_CHOICES,
    PAYMENT_STATUS_CHOICES,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_VOID,
)
from .services import apply_payment_effects, generate_platform_payment_number


class PlatformPaymentsPermissionMixin(PlatformPermissionRequiredMixin):
    login_url = "/login/"
    raise_exception = True
    platform_module_name = PLATFORM_MODULE_PAYMENTS
    platform_permission_required = PERMISSION_VIEW


def get_filtered_payments(request):
    queryset = PlatformPayment.objects.select_related(
        "id_company",
        "id_subscription",
        "id_subscription__id_plan",
        "id_document",
        "received_by",
    )

    status = request.GET.get("status", "").strip()
    method = request.GET.get("method", "").strip()
    q = request.GET.get("q", "").strip()

    if status:
        queryset = queryset.filter(status=status)

    if method:
        queryset = queryset.filter(method=method)

    if q:
        queryset = queryset.filter(
            Q(payment_number__icontains=q)
            | Q(id_company__name__icontains=q)
            | Q(reference__icontains=q)
            | Q(id_document__document_number__icontains=q)
            | Q(id_subscription__id_plan__name__icontains=q)
        )

    return queryset.distinct().order_by("-payment_date", "-id_payment")


def snapshot_payment(payment):
    if not payment:
        return {}

    return {
        "payment_id": payment.id_payment,
        "payment_number": payment.payment_number,
        "company_id": payment.id_company_id,
        "company_name": payment.id_company.name if payment.id_company else None,
        "company_slug": payment.id_company.slug if payment.id_company else None,
        "subscription_id": payment.id_subscription_id,
        "subscription_status": payment.id_subscription.status if payment.id_subscription else None,
        "subscription_renewal_date": (
            payment.id_subscription.renewal_date.isoformat()
            if payment.id_subscription and payment.id_subscription.renewal_date
            else None
        ),
        "plan_name": (
            payment.id_subscription.id_plan.name
            if payment.id_subscription and payment.id_subscription.id_plan
            else None
        ),
        "document_id": payment.id_document_id,
        "document_number": payment.id_document.document_number if payment.id_document else None,
        "amount": str(payment.amount or "0.00"),
        "status": payment.status,
        "method": payment.method,
        "reference": payment.reference,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
    }


def apply_payment_effects_with_metadata(payment):
    payment.refresh_from_db()

    document_before = payment.id_document.status if payment.id_document else None
    company_before = payment.id_company.status if payment.id_company else None
    subscription_before = payment.id_subscription.status if payment.id_subscription else None
    renewal_before = (
        payment.id_subscription.renewal_date.isoformat()
        if payment.id_subscription and payment.id_subscription.renewal_date
        else None
    )

    apply_payment_effects(payment)

    payment.refresh_from_db()

    document_after = payment.id_document.status if payment.id_document else None
    company_after = payment.id_company.status if payment.id_company else None
    subscription_after = payment.id_subscription.status if payment.id_subscription else None
    renewal_after = (
        payment.id_subscription.renewal_date.isoformat()
        if payment.id_subscription and payment.id_subscription.renewal_date
        else None
    )

    return {
        "document_id_after": payment.id_document_id,
        "document_number_after": payment.id_document.document_number if payment.id_document else None,
        "document_status_before": document_before,
        "document_status_after": document_after,
        "company_status_before": company_before,
        "company_status_after": company_after,
        "subscription_id_after": payment.id_subscription_id,
        "subscription_status_before": subscription_before,
        "subscription_status_after": subscription_after,
        "renewal_date_before": renewal_before,
        "renewal_date_after": renewal_after,
    }


def log_payment_audit(
    *,
    request,
    payment,
    action,
    description,
    previous_snapshot=None,
    extra_metadata=None,
):
    try:
        metadata = {
            "payment": snapshot_payment(payment),
        }

        if previous_snapshot:
            metadata["previous_payment"] = previous_snapshot

        if extra_metadata:
            metadata["effects"] = extra_metadata

        log_platform_action(
            user=request.user,
            company=payment.id_company,
            module_name="platform_payments",
            action=action,
            object_id=payment.id_payment,
            object_label=payment.payment_number,
            description=description,
            request=request,
            metadata=metadata,
        )
    except Exception:
        pass


class PlatformPaymentListView(LoginRequiredMixin, PlatformPaymentsPermissionMixin, ListView):
    platform_permission_required = PERMISSION_VIEW

    model = PlatformPayment
    template_name = "platform_payments/list.html"
    context_object_name = "payments"
    login_url = "/login/"
    paginate_by = 20

    def get_queryset(self):
        return get_filtered_payments(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        status = self.request.GET.get("status", "").strip()
        method = self.request.GET.get("method", "").strip()
        q = self.request.GET.get("q", "").strip()

        base_queryset = PlatformPayment.objects.all()

        paid_total = (
            base_queryset.filter(status=PAYMENT_STATUS_PAID)
            .aggregate(total=Sum("amount"))
            .get("total")
            or 0
        )

        context["status_filter"] = status
        context["method_filter"] = method
        context["q"] = q
        context["status_choices"] = PAYMENT_STATUS_CHOICES
        context["method_choices"] = PAYMENT_METHOD_CHOICES
        context["active_querystring"] = self.request.GET.urlencode()

        context["total_payments"] = base_queryset.count()
        context["paid_payments"] = base_queryset.filter(status=PAYMENT_STATUS_PAID).count()
        context["pending_payments"] = base_queryset.filter(status="pending").count()
        context["void_payments"] = base_queryset.filter(status=PAYMENT_STATUS_VOID).count()
        context["paid_total"] = paid_total

        context["can_create_payments"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_PAYMENTS,
            PERMISSION_CREATE,
        )
        context["can_edit_payments"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_PAYMENTS,
            PERMISSION_EDIT,
        )
        context["can_approve_payments"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_PAYMENTS,
            PERMISSION_APPROVE,
        )

        return context


class PlatformPaymentDetailView(LoginRequiredMixin, PlatformPaymentsPermissionMixin, DetailView):
    platform_permission_required = PERMISSION_VIEW

    model = PlatformPayment
    template_name = "platform_payments/detail.html"
    context_object_name = "payment"
    pk_url_kwarg = "id_payment"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformPayment.objects.select_related(
            "id_company",
            "id_subscription",
            "id_subscription__id_plan",
            "id_document",
            "received_by",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["can_edit_payments"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_PAYMENTS,
            PERMISSION_EDIT,
        )
        context["can_approve_payments"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_PAYMENTS,
            PERMISSION_APPROVE,
        )

        return context


class PlatformPaymentCreateView(LoginRequiredMixin, PlatformPaymentsPermissionMixin, CreateView):
    platform_permission_required = PERMISSION_CREATE

    model = PlatformPayment
    form_class = PlatformPaymentForm
    template_name = "platform_payments/form.html"
    login_url = "/login/"

    def form_valid(self, form):
        with transaction.atomic():
            payment = form.save(commit=False)
            payment.payment_number = generate_platform_payment_number()
            payment.received_by = self.request.user

            if payment.status == PAYMENT_STATUS_PAID and not payment.payment_date:
                payment.payment_date = timezone.localdate()

            payment.save()
            self.object = payment

            effects_metadata = apply_payment_effects_with_metadata(self.object)

            log_payment_audit(
                request=self.request,
                payment=self.object,
                action=PLATFORM_AUDIT_ACTION_CREATE,
                description=f"SaaS payment recorded: {self.object.payment_number} for {self.object.id_company.name}",
                extra_metadata=effects_metadata,
            )

        messages.success(
            self.request,
            "SaaS payment recorded successfully. If it was marked as paid, the subscription, company access and document were updated automatically.",
        )

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the SaaS payment form.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_payments:detail",
            kwargs={"id_payment": self.object.id_payment},
        )


class PlatformPaymentUpdateView(LoginRequiredMixin, PlatformPaymentsPermissionMixin, UpdateView):
    platform_permission_required = PERMISSION_EDIT

    model = PlatformPayment
    form_class = PlatformPaymentForm
    template_name = "platform_payments/form.html"
    context_object_name = "payment"
    pk_url_kwarg = "id_payment"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformPayment.objects.select_related(
            "id_company",
            "id_subscription",
            "id_subscription__id_plan",
            "id_document",
            "received_by",
        )

    def form_valid(self, form):
        previous_payment = PlatformPayment.objects.select_related(
            "id_company",
            "id_subscription",
            "id_subscription__id_plan",
            "id_document",
            "received_by",
        ).get(id_payment=self.object.id_payment)

        previous_snapshot = snapshot_payment(previous_payment)

        with transaction.atomic():
            self.object = form.save()

            if self.object.status == PAYMENT_STATUS_PAID and not self.object.payment_date:
                self.object.payment_date = timezone.localdate()
                self.object.save(update_fields=["payment_date", "updated_at"])

            effects_metadata = apply_payment_effects_with_metadata(self.object)

            log_payment_audit(
                request=self.request,
                payment=self.object,
                action=PLATFORM_AUDIT_ACTION_UPDATE,
                description=f"SaaS payment updated: {self.object.payment_number} for {self.object.id_company.name}",
                previous_snapshot=previous_snapshot,
                extra_metadata=effects_metadata,
            )

        messages.success(
            self.request,
            "SaaS payment updated successfully. Paid payments update subscription access automatically.",
        )

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the SaaS payment form.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_payments:detail",
            kwargs={"id_payment": self.object.id_payment},
        )


class PlatformPaymentExportCSVView(LoginRequiredMixin, PlatformPaymentsPermissionMixin, TemplateView):
    platform_permission_required = PERMISSION_VIEW
    login_url = "/login/"

    def get(self, request, *args, **kwargs):
        payments = get_filtered_payments(request)
        exported_count = payments.count()

        try:
            log_platform_action(
                user=request.user,
                company=None,
                module_name="platform_payments",
                action=PLATFORM_AUDIT_ACTION_EXPORT,
                object_id=None,
                object_label="platform-payments.csv",
                description="Platform payments exported to CSV.",
                request=request,
                metadata={
                    "filters": request.GET.dict(),
                    "exported_count": exported_count,
                },
            )
        except Exception:
            pass

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="platform-payments.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Payment Number",
                "Company",
                "Company Slug",
                "Document",
                "Subscription",
                "Plan",
                "Amount",
                "Status",
                "Method",
                "Reference",
                "Payment Date",
                "Received By",
                "Created At",
            ]
        )

        for payment in payments:
            writer.writerow(
                [
                    payment.payment_number,
                    payment.id_company.name if payment.id_company else "",
                    payment.id_company.slug if payment.id_company else "",
                    payment.id_document.document_number if payment.id_document else "",
                    payment.id_subscription.id_subscription if payment.id_subscription else "",
                    payment.id_subscription.id_plan.name if payment.id_subscription and payment.id_subscription.id_plan else "",
                    payment.amount,
                    payment.get_status_display(),
                    payment.get_method_display(),
                    payment.reference or "",
                    payment.payment_date or "",
                    payment.received_by.email if payment.received_by else "",
                    payment.created_at,
                ]
            )

        return response


@require_POST
def platform_payment_mark_paid_view(request, id_payment):
    if not user_can_platform_action(
        request.user,
        PLATFORM_MODULE_PAYMENTS,
        PERMISSION_APPROVE,
    ):
        raise DjangoPermissionDenied("You do not have permission to mark payments as paid.")

    payment = get_object_or_404(
        PlatformPayment.objects.select_related(
            "id_company",
            "id_subscription",
            "id_subscription__id_plan",
            "id_document",
            "received_by",
        ),
        id_payment=id_payment,
    )

    previous_snapshot = snapshot_payment(payment)

    with transaction.atomic():
        payment.status = PAYMENT_STATUS_PAID

        if not payment.payment_date:
            payment.payment_date = timezone.localdate()

        payment.save(update_fields=["status", "payment_date", "updated_at"])

        effects_metadata = apply_payment_effects_with_metadata(payment)

        log_payment_audit(
            request=request,
            payment=payment,
            action=PLATFORM_AUDIT_ACTION_UPDATE,
            description=f"SaaS payment marked as paid: {payment.payment_number} for {payment.id_company.name}",
            previous_snapshot=previous_snapshot,
            extra_metadata=effects_metadata,
        )

    messages.success(
        request,
        "Payment marked as paid. Subscription renewal, company access and automatic document were updated.",
    )

    return redirect("platform_payments:detail", id_payment=payment.id_payment)


@require_POST
def platform_payment_void_view(request, id_payment):
    if not user_can_platform_action(
        request.user,
        PLATFORM_MODULE_PAYMENTS,
        PERMISSION_APPROVE,
    ):
        raise DjangoPermissionDenied("You do not have permission to void payments.")

    payment = get_object_or_404(
        PlatformPayment.objects.select_related(
            "id_company",
            "id_subscription",
            "id_subscription__id_plan",
            "id_document",
            "received_by",
        ),
        id_payment=id_payment,
    )

    previous_snapshot = snapshot_payment(payment)

    with transaction.atomic():
        payment.status = PAYMENT_STATUS_VOID
        payment.save(update_fields=["status", "updated_at"])

        effects_metadata = apply_payment_effects_with_metadata(payment)

        log_payment_audit(
            request=request,
            payment=payment,
            action=PLATFORM_AUDIT_ACTION_UPDATE,
            description=f"SaaS payment voided: {payment.payment_number} for {payment.id_company.name}",
            previous_snapshot=previous_snapshot,
            extra_metadata=effects_metadata,
        )

    messages.success(request, "Payment voided successfully.")

    return redirect("platform_payments:detail", id_payment=payment.id_payment)