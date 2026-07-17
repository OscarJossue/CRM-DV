from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.platform_permissions import (
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PlatformPermissionRequiredMixin,
    user_can_platform_action,
)
from apps.platform_audit.models.choices import (
    PLATFORM_AUDIT_ACTION_ACTIVATE,
    PLATFORM_AUDIT_ACTION_CREATE,
    PLATFORM_AUDIT_ACTION_DEACTIVATE,
    PLATFORM_AUDIT_ACTION_SUSPEND,
    PLATFORM_AUDIT_ACTION_UPDATE,
)
from apps.platform_audit.services import log_platform_action
from apps.platform_users.constants import PLATFORM_MODULE_SUBSCRIPTIONS

from .forms import PlatformSubscriptionForm
from .models import PlatformSubscription
from .models.choices import (
    SUBSCRIPTION_CANCELED,
    SUBSCRIPTION_SUSPENDED,
)
from .services import (
    reactivate_platform_subscription,
    sync_company_access,
    sync_subscription_status,
)


class PlatformAdminRequiredMixin(PlatformPermissionRequiredMixin):
    platform_module_name = PLATFORM_MODULE_SUBSCRIPTIONS


def snapshot_subscription(subscription):
    if not subscription:
        return {}

    return {
        "subscription_id": subscription.id_subscription,
        "company_id": subscription.id_company_id,
        "company_name": subscription.id_company.name if subscription.id_company else None,
        "company_slug": subscription.id_company.slug if subscription.id_company else None,
        "plan_id": subscription.id_plan_id,
        "plan_name": subscription.id_plan.name if subscription.id_plan else None,
        "status": subscription.status,
        "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
        "renewal_date": subscription.renewal_date.isoformat() if subscription.renewal_date else None,
        "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
        "notes": subscription.notes,
    }


def sync_subscription_and_company(subscription):
    company_before = subscription.id_company.status if subscription.id_company else None
    subscription_before = subscription.status

    sync_subscription_status(subscription)

    subscription.refresh_from_db()

    company = subscription.id_company

    if company:
        sync_company_access(company)
        company.refresh_from_db()

    return {
        "subscription_status_before": subscription_before,
        "subscription_status_after": subscription.status,
        "company_status_before": company_before,
        "company_status_after": company.status if company else None,
    }


def log_subscription_audit(
    *,
    request,
    subscription,
    action,
    description,
    previous_snapshot=None,
    extra_metadata=None,
):
    try:
        metadata = {
            "subscription": snapshot_subscription(subscription),
        }

        if previous_snapshot:
            metadata["previous_subscription"] = previous_snapshot

        if extra_metadata:
            metadata["effects"] = extra_metadata

        log_platform_action(
            user=request.user,
            company=subscription.id_company,
            module_name="platform_subscriptions",
            action=action,
            object_id=subscription.id_subscription,
            object_label=f"{subscription.id_company.name} - {subscription.id_plan.name}",
            description=description,
            request=request,
            metadata=metadata,
        )
    except Exception:
        pass


class PlatformSubscriptionListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    model = PlatformSubscription
    template_name = "platform_subscriptions/list.html"
    context_object_name = "subscriptions"
    login_url = "/login/"

    def get_queryset(self):
        return (
            PlatformSubscription.objects.select_related(
                "id_company",
                "id_plan",
            )
            .all()
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create_subscriptions"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_SUBSCRIPTIONS,
            PERMISSION_CREATE,
        )
        context["can_edit_subscriptions"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_SUBSCRIPTIONS,
            PERMISSION_EDIT,
        )
        context["can_approve_subscriptions"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_SUBSCRIPTIONS,
            PERMISSION_APPROVE,
        )
        return context


class PlatformSubscriptionCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    platform_permission_required = PERMISSION_CREATE

    model = PlatformSubscription
    form_class = PlatformSubscriptionForm
    template_name = "platform_subscriptions/form.html"
    context_object_name = "subscription"
    login_url = "/login/"

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()

            effects_metadata = sync_subscription_and_company(self.object)

            log_subscription_audit(
                request=self.request,
                subscription=self.object,
                action=PLATFORM_AUDIT_ACTION_CREATE,
                description=(
                    f"Platform subscription created for "
                    f"{self.object.id_company.name} with plan {self.object.id_plan.name}."
                ),
                extra_metadata=effects_metadata,
            )

        messages.success(self.request, "Subscription created successfully.")

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the subscription form.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_subscriptions:detail",
            kwargs={"id_subscription": self.object.id_subscription},
        )


class PlatformSubscriptionDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    model = PlatformSubscription
    template_name = "platform_subscriptions/detail.html"
    context_object_name = "subscription"
    pk_url_kwarg = "id_subscription"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformSubscription.objects.select_related(
            "id_company",
            "id_plan",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_edit_subscriptions"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_SUBSCRIPTIONS,
            PERMISSION_EDIT,
        )
        context["can_approve_subscriptions"] = user_can_platform_action(
            self.request.user,
            PLATFORM_MODULE_SUBSCRIPTIONS,
            PERMISSION_APPROVE,
        )
        return context


class PlatformSubscriptionUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    platform_permission_required = PERMISSION_EDIT

    model = PlatformSubscription
    form_class = PlatformSubscriptionForm
    template_name = "platform_subscriptions/form.html"
    context_object_name = "subscription"
    pk_url_kwarg = "id_subscription"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformSubscription.objects.select_related(
            "id_company",
            "id_plan",
        )

    def form_valid(self, form):
        previous_subscription = PlatformSubscription.objects.select_related(
            "id_company",
            "id_plan",
        ).get(id_subscription=self.object.id_subscription)

        previous_snapshot = snapshot_subscription(previous_subscription)

        with transaction.atomic():
            self.object = form.save()

            effects_metadata = sync_subscription_and_company(self.object)

            log_subscription_audit(
                request=self.request,
                subscription=self.object,
                action=PLATFORM_AUDIT_ACTION_UPDATE,
                description=(
                    f"Platform subscription updated for "
                    f"{self.object.id_company.name} with plan {self.object.id_plan.name}."
                ),
                previous_snapshot=previous_snapshot,
                extra_metadata=effects_metadata,
            )

        messages.success(self.request, "Subscription updated successfully.")

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the subscription form.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_subscriptions:detail",
            kwargs={"id_subscription": self.object.id_subscription},
        )


@require_POST
def platform_subscription_activate_view(request, id_subscription):
    if not user_can_platform_action(
        request.user,
        PLATFORM_MODULE_SUBSCRIPTIONS,
        PERMISSION_APPROVE,
    ):
        return redirect("platform_subscriptions:list")

    subscription = get_object_or_404(
        PlatformSubscription.objects.select_related("id_company", "id_plan"),
        id_subscription=id_subscription,
    )

    previous_snapshot = snapshot_subscription(subscription)

    with transaction.atomic():
        reactivate_platform_subscription(
            subscription,
            force_new_cycle=True,
        )
        subscription.refresh_from_db()

        effects_metadata = sync_subscription_and_company(subscription)

        log_subscription_audit(
            request=request,
            subscription=subscription,
            action=PLATFORM_AUDIT_ACTION_ACTIVATE,
            description=f"Platform subscription activated for {subscription.id_company.name}.",
            previous_snapshot=previous_snapshot,
            extra_metadata=effects_metadata,
        )

    messages.success(request, "Subscription activated successfully.")

    return redirect("platform_subscriptions:detail", id_subscription=subscription.id_subscription)


@require_POST
def platform_subscription_suspend_view(request, id_subscription):
    if not user_can_platform_action(
        request.user,
        PLATFORM_MODULE_SUBSCRIPTIONS,
        PERMISSION_APPROVE,
    ):
        return redirect("platform_subscriptions:list")

    subscription = get_object_or_404(
        PlatformSubscription.objects.select_related("id_company", "id_plan"),
        id_subscription=id_subscription,
    )

    previous_snapshot = snapshot_subscription(subscription)

    with transaction.atomic():
        subscription.status = SUBSCRIPTION_SUSPENDED
        subscription.save(update_fields=["status"])

        effects_metadata = sync_subscription_and_company(subscription)

        log_subscription_audit(
            request=request,
            subscription=subscription,
            action=PLATFORM_AUDIT_ACTION_SUSPEND,
            description=f"Platform subscription suspended for {subscription.id_company.name}.",
            previous_snapshot=previous_snapshot,
            extra_metadata=effects_metadata,
        )

    messages.success(request, "Subscription suspended successfully.")

    return redirect("platform_subscriptions:detail", id_subscription=subscription.id_subscription)


@require_POST
def platform_subscription_cancel_view(request, id_subscription):
    if not user_can_platform_action(
        request.user,
        PLATFORM_MODULE_SUBSCRIPTIONS,
        PERMISSION_APPROVE,
    ):
        return redirect("platform_subscriptions:list")

    subscription = get_object_or_404(
        PlatformSubscription.objects.select_related("id_company", "id_plan"),
        id_subscription=id_subscription,
    )

    previous_snapshot = snapshot_subscription(subscription)

    with transaction.atomic():
        subscription.status = SUBSCRIPTION_CANCELED
        subscription.save(update_fields=["status"])

        effects_metadata = sync_subscription_and_company(subscription)

        log_subscription_audit(
            request=request,
            subscription=subscription,
            action=PLATFORM_AUDIT_ACTION_DEACTIVATE,
            description=f"Platform subscription canceled for {subscription.id_company.name}.",
            previous_snapshot=previous_snapshot,
            extra_metadata=effects_metadata,
        )

    messages.success(request, "Subscription canceled successfully.")

    return redirect("platform_subscriptions:detail", id_subscription=subscription.id_subscription)