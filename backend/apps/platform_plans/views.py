from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.platform_audit.models.choices import (
    PLATFORM_AUDIT_ACTION_ACTIVATE,
    PLATFORM_AUDIT_ACTION_CREATE,
    PLATFORM_AUDIT_ACTION_DEACTIVATE,
    PLATFORM_AUDIT_ACTION_UPDATE,
)
from apps.platform_audit.services import log_platform_action

from .forms import PlatformPlanForm
from .models import PlatformPlan
from .models.choices import PLAN_STATUS_ACTIVE, PLAN_STATUS_INACTIVE
from apps.accounts.models.choices import PLATFORM_PLANS
from apps.core.platform_permissions import (
    PERMISSION_APPROVE,
    PERMISSION_CREATE,
    PERMISSION_EDIT,
    PlatformPermissionRequiredMixin,
    user_can_platform_action,
)

class PlatformAdminRequiredMixin(PlatformPermissionRequiredMixin):
    platform_module_name = PLATFORM_PLANS


def snapshot_plan(plan):
    if not plan:
        return {}

    return {
        "plan_id": plan.id_plan,
        "name": plan.name,
        "code": plan.code,
        "description": plan.description,
        "price": str(plan.price or "0.00"),
        "billing_cycle": plan.billing_cycle,
        "max_users": plan.max_users,
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def log_plan_audit(
    *,
    request,
    plan,
    action,
    description,
    previous_snapshot=None,
    extra_metadata=None,
):
    try:
        metadata = {
            "plan": snapshot_plan(plan),
        }

        if previous_snapshot:
            metadata["previous_plan"] = previous_snapshot

        if extra_metadata:
            metadata["extra"] = extra_metadata

        log_platform_action(
            user=request.user,
            company=None,
            module_name="platform_plans",
            action=action,
            object_id=plan.id_plan,
            object_label=plan.name,
            description=description,
            request=request,
            metadata=metadata,
        )
    except Exception:
        pass


class PlatformPlanListView(LoginRequiredMixin, PlatformAdminRequiredMixin, ListView):
    model = PlatformPlan
    template_name = "platform_plans/list.html"
    context_object_name = "plans"
    login_url = "/login/"

    def get_queryset(self):
        return PlatformPlan.objects.all().order_by("price", "name")


class PlatformPlanDetailView(LoginRequiredMixin, PlatformAdminRequiredMixin, DetailView):
    model = PlatformPlan
    template_name = "platform_plans/detail.html"
    context_object_name = "plan"
    pk_url_kwarg = "id_plan"
    login_url = "/login/"


class PlatformPlanCreateView(LoginRequiredMixin, PlatformAdminRequiredMixin, CreateView):
    platform_permission_required = PERMISSION_CREATE

    model = PlatformPlan
    form_class = PlatformPlanForm
    template_name = "platform_plans/form.html"
    login_url = "/login/"

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()

            log_plan_audit(
                request=self.request,
                plan=self.object,
                action=PLATFORM_AUDIT_ACTION_CREATE,
                description=f"Platform plan created: {self.object.name}.",
            )

        messages.success(self.request, "Platform plan created successfully.")

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the platform plan form.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "platform_plans:detail",
            kwargs={"id_plan": self.object.id_plan},
        )


class PlatformPlanUpdateView(LoginRequiredMixin, PlatformAdminRequiredMixin, UpdateView):
    platform_permission_required = PERMISSION_EDIT

    model = PlatformPlan
    form_class = PlatformPlanForm
    template_name = "platform_plans/form.html"
    context_object_name = "plan"
    pk_url_kwarg = "id_plan"
    login_url = "/login/"

    def get_success_url(self):
        return reverse_lazy(
            "platform_plans:detail",
            kwargs={"id_plan": self.object.id_plan},
        )

    def form_valid(self, form):
        previous_plan = PlatformPlan.objects.get(id_plan=self.object.id_plan)
        previous_snapshot = snapshot_plan(previous_plan)

        with transaction.atomic():
            self.object = form.save()

            log_plan_audit(
                request=self.request,
                plan=self.object,
                action=PLATFORM_AUDIT_ACTION_UPDATE,
                description=f"Platform plan updated: {self.object.name}.",
                previous_snapshot=previous_snapshot,
            )

        messages.success(self.request, "Platform plan updated successfully.")

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please review the platform plan form.")
        return super().form_invalid(form)


@require_POST
def platform_plan_activate_view(request, id_plan):
    if not user_can_platform_action(request.user, PLATFORM_PLANS, PERMISSION_APPROVE):
        return redirect("platform_plans:list")

    plan = get_object_or_404(PlatformPlan, id_plan=id_plan)
    previous_snapshot = snapshot_plan(plan)

    with transaction.atomic():
        plan.status = PLAN_STATUS_ACTIVE
        plan.save(update_fields=["status"])

        log_plan_audit(
            request=request,
            plan=plan,
            action=PLATFORM_AUDIT_ACTION_ACTIVATE,
            description=f"Platform plan activated: {plan.name}.",
            previous_snapshot=previous_snapshot,
            extra_metadata={
                "status_before": previous_snapshot.get("status"),
                "status_after": plan.status,
            },
        )

    messages.success(request, "Platform plan activated successfully.")

    return redirect("platform_plans:detail", id_plan=plan.id_plan)


@require_POST
def platform_plan_deactivate_view(request, id_plan):
    if not user_can_platform_action(request.user, PLATFORM_PLANS, PERMISSION_APPROVE):
        return redirect("platform_plans:list")

    plan = get_object_or_404(PlatformPlan, id_plan=id_plan)
    previous_snapshot = snapshot_plan(plan)

    with transaction.atomic():
        plan.status = PLAN_STATUS_INACTIVE
        plan.save(update_fields=["status"])

        log_plan_audit(
            request=request,
            plan=plan,
            action=PLATFORM_AUDIT_ACTION_DEACTIVATE,
            description=f"Platform plan deactivated: {plan.name}.",
            previous_snapshot=previous_snapshot,
            extra_metadata={
                "status_before": previous_snapshot.get("status"),
                "status_after": plan.status,
            },
        )

    messages.success(request, "Platform plan deactivated successfully.")

    return redirect("platform_plans:detail", id_plan=plan.id_plan)