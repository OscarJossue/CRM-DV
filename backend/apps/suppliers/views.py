from decimal import Decimal
from io import BytesIO
from urllib.parse import urlencode
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View
from rest_framework.exceptions import PermissionDenied

from apps.core.mixins import TenantModelViewSet
from apps.core.ui_translation import translate_ui_text as ui
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

from .forms import (
    SupplierDocumentForm,
    SupplierForm,
    SupplierOfferForm,
    SupplierPurchaseForm,
    SupplierPurchaseItemFormSet,
)
from .models import Supplier, SupplierDocument, SupplierOffer, SupplierPurchase
from .models.choices import (
    PURCHASE_PAYMENT_STATUS_CHOICES,
    PURCHASE_STATUS_CANCELLED,
    PURCHASE_STATUS_CHOICES,
    SUPPLIER_CATEGORY_CHOICES,
    SUPPLIER_STATUS_ACTIVE,
    SUPPLIER_STATUS_CHOICES,
)
from .permissions import user_can_access_supplier_object
from .selectors import (
    supplier_document_list_for_user,
    supplier_list_for_user,
    supplier_offer_list_for_user,
    supplier_purchase_list_for_user,
)
from .serializers import SupplierDocumentSerializer, SupplierOfferSerializer, SupplierPurchaseSerializer, SupplierSerializer
from .services import (
    activate_product,
    activate_supplier,
    cancel_purchase,
    create_product_from_form,
    create_purchase_with_items,
    create_supplier_from_form,
    deactivate_product,
    deactivate_supplier,
    delete_product_if_unused,
    delete_supplier_if_empty,
    recalculate_purchase,
    update_product_from_form,
    update_purchase_with_items,
    update_supplier_from_form,
    money,
)

MODULE_NAME = "suppliers"


SUPPLIER_STATUS_GROUPS = [
    {"key": "active", "label": "Active", "color": "#16a34a"},
    {"key": "inactive", "label": "Inactive", "color": "#64748b"},
    {"key": "blocked", "label": "Blocked", "color": "#dc2626"},
]

PURCHASE_STATUS_GROUPS = [
    {"key": "draft", "label": "Draft", "color": "#64748b"},
    {"key": "pending", "label": "Pending", "color": "#f59e0b"},
    {"key": "completed", "label": "Completed", "color": "#16a34a"},
    {"key": "cancelled", "label": "Cancelled", "color": "#dc2626"},
]

PURCHASE_PAYMENT_STATUS_GROUPS = [
    {"key": "unpaid", "label": "Unpaid", "color": "#ef3340"},
    {"key": "partial", "label": "Partially Paid", "color": "#f59e0b"},
    {"key": "paid", "label": "Paid", "color": "#0e9f6e"},
]


def get_request_company_slug(request, company_slug=None):
    if company_slug:
        return company_slug

    current_company = getattr(request, "current_company", None)
    if current_company and getattr(current_company, "slug", None):
        return current_company.slug

    user_company = getattr(getattr(request, "user", None), "id_company", None)
    if user_company and getattr(user_company, "slug", None):
        return user_company.slug

    return None


def reverse_supplier_url(request, view_name, company_slug=None, kwargs=None):
    kwargs = dict(kwargs or {})
    active_company_slug = get_request_company_slug(request, company_slug)

    if active_company_slug:
        kwargs["company_slug"] = active_company_slug
        return reverse(f"company_suppliers:{view_name}", kwargs=kwargs)

    return reverse(f"suppliers:{view_name}", kwargs=kwargs)


def redirect_supplier_url(request, view_name, company_slug=None, kwargs=None):
    return redirect(reverse_supplier_url(request, view_name, company_slug=company_slug, kwargs=kwargs))


def decimal_value(value):
    if value in [None, ""]:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def action_context(user):
    return {
        "can_view_suppliers": user_can_module_action(user, MODULE_NAME, PERMISSION_VIEW),
        "can_create_suppliers": user_can_module_action(user, MODULE_NAME, PERMISSION_CREATE),
        "can_edit_suppliers": user_can_module_action(user, MODULE_NAME, PERMISSION_EDIT),
        "can_delete_suppliers": user_can_module_action(user, MODULE_NAME, PERMISSION_DELETE),
        "can_approve_suppliers": user_can_module_action(user, MODULE_NAME, PERMISSION_APPROVE),
    }


def build_status_summary(queryset, groups, status_field, current_status=""):
    objects = list(queryset)
    total_count = len(objects)
    start_degree = 0.0
    gradient_parts = []
    items = []

    for group in groups:
        count = sum(1 for obj in objects if getattr(obj, status_field, None) == group["key"])
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
                "is_active": current_status == group["key"],
                "is_zero": count == 0,
            }
        )

    return {
        "total": total_count,
        "items": items,
        "chart_gradient": ", ".join(gradient_parts) if gradient_parts else "#e5e7eb 0deg 360deg",
    }


class SupplierDashboardView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    """Old dashboard route kept for compatibility; simplified module opens suppliers list."""

    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    login_url = "/login/"

    def get(self, request, company_slug=None, *args, **kwargs):
        return redirect_supplier_url(request, "supplier_list", company_slug=company_slug)


class SupplierListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "suppliers/supplier_list.html"
    context_object_name = "suppliers"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        queryset = supplier_list_for_user(self.request.user).prefetch_related("offers", "purchases")
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()

        if q:
            queryset = queryset.filter(
                Q(supplier_code__icontains=q)
                | Q(company_name__icontains=q)
                | Q(contact_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(tax_id__icontains=q)
                | Q(address__icontains=q)
                | Q(city__icontains=q)
            )
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(action_context(self.request.user))
        context.update(
            {
                "page_title": "Suppliers",
                "status_options": SUPPLIER_STATUS_CHOICES,
                "current_search": self.request.GET.get("q", ""),
                "current_status": self.request.GET.get("status", ""),
                "supplier_status_summary": build_status_summary(supplier_list_for_user(self.request.user), SUPPLIER_STATUS_GROUPS, "status", self.request.GET.get("status", "")),
            }
        )
        return context


class SupplierDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    model = Supplier
    template_name = "suppliers/supplier_detail.html"
    context_object_name = "supplier"
    pk_url_kwarg = "id_supplier"
    login_url = "/login/"

    def get_queryset(self):
        return supplier_list_for_user(self.request.user).prefetch_related("offers", "purchases", "documents")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(action_context(self.request.user))
        context.update(
            {
                "page_title": "Supplier Details",
                "supplier_offers": supplier_offer_list_for_user(self.request.user).filter(id_supplier=self.object)[:12],
                "supplier_purchases": supplier_purchase_list_for_user(self.request.user).filter(id_supplier=self.object)[:12],
                "supplier_documents": supplier_document_list_for_user(self.request.user).filter(id_supplier=self.object)[:12],
            }
        )
        return context


class SupplierCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_CREATE
    model = Supplier
    form_class = SupplierForm
    template_name = "suppliers/supplier_form.html"
    login_url = "/login/"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            self.object = create_supplier_from_form(form, self.request.user)
            messages.success(self.request, "Supplier created successfully.")
            return redirect(self.get_success_url())
        except Exception as error:
            messages.error(self.request, f"Supplier could not be created: {error}")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse_supplier_url(self.request, "supplier_detail", kwargs={"id_supplier": self.object.id_supplier})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(action_context(self.request.user))
        context.update({"page_title": "Register Supplier", "form_title": "Register Supplier", "submit_label": "Save Supplier", "cancel_url": reverse_supplier_url(self.request, "supplier_list")})
        return context


class SupplierUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT
    model = Supplier
    form_class = SupplierForm
    template_name = "suppliers/supplier_form.html"
    context_object_name = "supplier"
    pk_url_kwarg = "id_supplier"
    login_url = "/login/"

    def get_queryset(self):
        return supplier_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            self.object = update_supplier_from_form(form, self.request.user)
            messages.success(self.request, "Supplier updated successfully.")
            return redirect(self.get_success_url())
        except Exception as error:
            messages.error(self.request, f"Supplier could not be updated: {error}")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse_supplier_url(self.request, "supplier_detail", kwargs={"id_supplier": self.object.id_supplier})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(action_context(self.request.user))
        context.update({"page_title": "Edit Supplier", "form_title": "Edit Supplier", "submit_label": "Update Supplier", "cancel_url": reverse_supplier_url(self.request, "supplier_detail", kwargs={"id_supplier": self.object.id_supplier})})
        return context


@require_POST
@login_required
def supplier_toggle_status_view(request, id_supplier, company_slug=None):
    permission_response = require_module_action_or_403(request.user, MODULE_NAME, PERMISSION_EDIT)
    if permission_response:
        return permission_response

    supplier = get_object_or_404(supplier_list_for_user(request.user), id_supplier=id_supplier)
    if supplier.status == SUPPLIER_STATUS_ACTIVE:
        deactivate_supplier(supplier, request.user)
        messages.success(request, "Supplier deactivated successfully.")
    else:
        activate_supplier(supplier, request.user)
        messages.success(request, "Supplier activated successfully.")

    return redirect_supplier_url(request, "supplier_detail", company_slug=company_slug, kwargs={"id_supplier": supplier.id_supplier})


@require_POST
@login_required
def supplier_delete_view(request, id_supplier, company_slug=None):
    permission_response = require_module_action_or_403(request.user, MODULE_NAME, PERMISSION_DELETE)
    if permission_response:
        return permission_response

    supplier = get_object_or_404(supplier_list_for_user(request.user), id_supplier=id_supplier)
    deleted = delete_supplier_if_empty(supplier)
    if deleted:
        messages.success(request, "Supplier deleted successfully.")
    else:
        deactivate_supplier(supplier, request.user)
        messages.warning(request, "Supplier has purchases, so it was deactivated instead of deleted.")
    return redirect_supplier_url(request, "supplier_list", company_slug=company_slug)


class SupplierOfferListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "suppliers/offer_list.html"
    context_object_name = "offers"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        queryset = supplier_offer_list_for_user(self.request.user)
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        supplier_id = (self.request.GET.get("supplier") or "").strip()
        category = (self.request.GET.get("category") or "").strip()

        if q:
            queryset = queryset.filter(
                Q(name__icontains=q)
                | Q(product_code__icontains=q)
                | Q(description__icontains=q)
                | Q(id_supplier__company_name__icontains=q)
            )
        if status:
            queryset = queryset.filter(status=status)
        if supplier_id:
            queryset = queryset.filter(id_supplier_id=supplier_id)
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(action_context(self.request.user))
        context.update(
            {
                "page_title": "Products and Services",
                "suppliers": supplier_list_for_user(self.request.user).filter(status=SUPPLIER_STATUS_ACTIVE),
                "status_options": SUPPLIER_STATUS_CHOICES,
                "category_options": SUPPLIER_CATEGORY_CHOICES,
                "current_search": self.request.GET.get("q", ""),
                "current_status": self.request.GET.get("status", ""),
                "current_supplier": self.request.GET.get("supplier", ""),
                "current_category": self.request.GET.get("category", ""),
                "offer_status_summary": build_status_summary(
                    supplier_offer_list_for_user(self.request.user),
                    SUPPLIER_STATUS_GROUPS,
                    "status",
                    self.request.GET.get("status", ""),
                ),
            }
        )
        return context


class SupplierOfferCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_CREATE
    model = SupplierOffer
    form_class = SupplierOfferForm
    template_name = "suppliers/offer_form.html"
    login_url = "/login/"

    def get_supplier(self):
        supplier_id = self.kwargs.get("id_supplier") or self.request.GET.get("supplier")
        if not supplier_id:
            return None
        return get_object_or_404(supplier_list_for_user(self.request.user), id_supplier=supplier_id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["supplier"] = self.get_supplier()
        return kwargs

    def form_valid(self, form):
        self.object = create_product_from_form(form, self.request.user)
        messages.success(self.request, "Product created successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_supplier_url(self.request, "offer_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.get_supplier()
        context.update(action_context(self.request.user))
        context.update({"page_title": "Add Product or Service", "form_title": "Add Product or Service", "submit_label": "Save Product / Service", "supplier": supplier, "cancel_url": reverse_supplier_url(self.request, "supplier_detail", kwargs={"id_supplier": supplier.id_supplier}) if supplier else reverse_supplier_url(self.request, "offer_list")})
        return context


class SupplierOfferUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, UpdateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT
    model = SupplierOffer
    form_class = SupplierOfferForm
    template_name = "suppliers/offer_form.html"
    context_object_name = "offer"
    pk_url_kwarg = "id_supplier_offer"
    login_url = "/login/"

    def get_queryset(self):
        return supplier_offer_list_for_user(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = update_product_from_form(form, self.request.user)
        messages.success(self.request, "Product updated successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_supplier_url(self.request, "offer_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(action_context(self.request.user))
        context.update({"page_title": "Edit Product or Service", "form_title": "Edit Product or Service", "submit_label": "Update Product / Service", "cancel_url": reverse_supplier_url(self.request, "offer_list")})
        return context


@require_POST
@login_required
def supplier_offer_toggle_status_view(request, id_supplier_offer, company_slug=None):
    permission_response = require_module_action_or_403(request.user, MODULE_NAME, PERMISSION_EDIT)
    if permission_response:
        return permission_response

    product = get_object_or_404(supplier_offer_list_for_user(request.user), id_supplier_offer=id_supplier_offer)
    if product.status == SUPPLIER_STATUS_ACTIVE:
        deactivate_product(product, request.user)
        messages.success(request, "Product deactivated successfully.")
    else:
        activate_product(product, request.user)
        messages.success(request, "Product activated successfully.")
    return redirect_supplier_url(request, "offer_list", company_slug=company_slug)


@require_POST
@login_required
def supplier_offer_delete_view(request, id_supplier_offer, company_slug=None):
    permission_response = require_module_action_or_403(request.user, MODULE_NAME, PERMISSION_DELETE)
    if permission_response:
        return permission_response

    product = get_object_or_404(supplier_offer_list_for_user(request.user), id_supplier_offer=id_supplier_offer)
    deleted = delete_product_if_unused(product)
    if deleted:
        messages.success(request, "Product deleted successfully.")
    else:
        deactivate_product(product, request.user)
        messages.warning(request, "Product is already used in purchases, so it was deactivated instead of deleted.")
    return redirect_supplier_url(request, "offer_list", company_slug=company_slug)


class SupplierPurchaseListView(LoginRequiredMixin, ModulePermissionRequiredMixin, ListView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "suppliers/purchase_list.html"
    context_object_name = "purchases"
    paginate_by = 20
    login_url = "/login/"

    def get_queryset(self):
        queryset = supplier_purchase_list_for_user(self.request.user)
        q = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        payment_status = (self.request.GET.get("payment") or "").strip()
        supplier_id = (self.request.GET.get("supplier") or "").strip()
        date_from = (self.request.GET.get("date_from") or "").strip()
        date_to = (self.request.GET.get("date_to") or "").strip()

        if q:
            queryset = queryset.filter(
                Q(purchase_number__icontains=q)
                | Q(external_document_number__icontains=q)
                | Q(id_supplier__company_name__icontains=q)
                | Q(description__icontains=q)
            )
        if status:
            queryset = queryset.filter(status=status)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        if supplier_id:
            queryset = queryset.filter(id_supplier_id=supplier_id)
        if date_from:
            queryset = queryset.filter(purchase_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(purchase_date__lte=date_to)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_queryset = supplier_purchase_list_for_user(self.request.user)
        for purchase in base_queryset[:100]:
            try:
                recalculate_purchase(purchase)
            except Exception:
                pass
        summary = build_status_summary(base_queryset, PURCHASE_STATUS_GROUPS, "status", self.request.GET.get("status", ""))
        for item in summary["items"]:
            params = self.request.GET.copy()
            params["status"] = item["key"]
            item["query_string"] = urlencode(params, doseq=True)
        context.update(action_context(self.request.user))
        context.update(
            {
                "page_title": "Purchases",
                "suppliers": supplier_list_for_user(self.request.user).filter(status=SUPPLIER_STATUS_ACTIVE),
                "status_options": PURCHASE_STATUS_CHOICES,
                "payment_status_options": PURCHASE_PAYMENT_STATUS_CHOICES,
                "purchase_status_summary": summary,
                "purchase_payment_summary": build_status_summary(
                    base_queryset.exclude(status=PURCHASE_STATUS_CANCELLED),
                    PURCHASE_PAYMENT_STATUS_GROUPS,
                    "payment_status",
                    self.request.GET.get("payment", ""),
                ),
                "total_purchases": money(base_queryset.exclude(status=PURCHASE_STATUS_CANCELLED).aggregate(total=Sum("total"))["total"] or Decimal("0.00")),
                "total_paid": money(base_queryset.exclude(status=PURCHASE_STATUS_CANCELLED).aggregate(total=Sum("paid_amount"))["total"] or Decimal("0.00")),
                "total_balance": money(base_queryset.exclude(status=PURCHASE_STATUS_CANCELLED).aggregate(total=Sum("balance_due"))["total"] or Decimal("0.00")),
                "current_search": self.request.GET.get("q", ""),
                "current_status": self.request.GET.get("status", ""),
                "current_payment": self.request.GET.get("payment", ""),
                "current_supplier": self.request.GET.get("supplier", ""),
                "current_date_from": self.request.GET.get("date_from", ""),
                "current_date_to": self.request.GET.get("date_to", ""),
            }
        )
        return context


class SupplierPurchaseDetailView(LoginRequiredMixin, ModulePermissionRequiredMixin, DetailView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    model = SupplierPurchase
    template_name = "suppliers/purchase_detail.html"
    context_object_name = "purchase"
    pk_url_kwarg = "id_supplier_purchase"
    login_url = "/login/"

    def get_queryset(self):
        return supplier_purchase_list_for_user(self.request.user)

    def get_object(self, queryset=None):
        purchase = super().get_object(queryset)
        recalculate_purchase(purchase)
        return purchase

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(action_context(self.request.user))
        context.update({"page_title": "Purchase Details", "purchase_documents": supplier_document_list_for_user(self.request.user).filter(id_purchase=self.object)})
        return context


class SupplierPurchaseCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_CREATE
    template_name = "suppliers/purchase_form.html"
    login_url = "/login/"

    def get_supplier(self):
        supplier_id = self.kwargs.get("id_supplier") or self.request.GET.get("supplier")
        if not supplier_id:
            return None
        return get_object_or_404(supplier_list_for_user(self.request.user), id_supplier=supplier_id)

    def get_context(self, form, formset):
        context = action_context(self.request.user)
        context.update(
            {
                "page_title": "Register Purchase",
                "form_title": "Register Purchase",
                "submit_label": "Save Purchase",
                "form": form,
                "item_formset": formset,
                "supplier": self.get_supplier(),
                "cancel_url": reverse_supplier_url(self.request, "supplier_detail", kwargs={"id_supplier": self.get_supplier().id_supplier}) if self.get_supplier() else reverse_supplier_url(self.request, "purchase_list"),
            }
        )
        return context

    def get(self, request, company_slug=None, *args, **kwargs):
        supplier = self.get_supplier()
        form = SupplierPurchaseForm(user=request.user, supplier=supplier)
        formset = SupplierPurchaseItemFormSet(form_kwargs={"user": request.user, "supplier": supplier})
        return render(request, self.template_name, self.get_context(form, formset))

    def post(self, request, company_slug=None, *args, **kwargs):
        supplier = self.get_supplier()
        form = SupplierPurchaseForm(request.POST, user=request.user, supplier=supplier)
        selected_supplier = supplier or form.data.get("id_supplier")
        formset_supplier = supplier
        if selected_supplier and not supplier:
            formset_supplier = supplier_list_for_user(request.user).filter(id_supplier=selected_supplier).first()
        formset = SupplierPurchaseItemFormSet(request.POST, form_kwargs={"user": request.user, "supplier": formset_supplier})
        if form.is_valid() and formset.is_valid():
            try:
                purchase = create_purchase_with_items(form, formset, request.user)
                messages.success(request, "Purchase registered successfully.")
                return redirect_supplier_url(request, "purchase_detail", company_slug=company_slug, kwargs={"id_supplier_purchase": purchase.id_supplier_purchase})
            except Exception as error:
                messages.error(request, f"Purchase could not be registered: {error}")
        else:
            messages.error(request, "Please review the purchase form and items.")
        return render(request, self.template_name, self.get_context(form, formset))


class SupplierPurchaseUpdateView(LoginRequiredMixin, ModulePermissionRequiredMixin, View):
    module_name = MODULE_NAME
    permission_required = PERMISSION_EDIT
    template_name = "suppliers/purchase_form.html"
    login_url = "/login/"

    def get_purchase(self):
        return get_object_or_404(supplier_purchase_list_for_user(self.request.user), id_supplier_purchase=self.kwargs.get("id_supplier_purchase"))

    def get_context(self, purchase, form, formset):
        context = action_context(self.request.user)
        context.update(
            {
                "page_title": "Edit Purchase",
                "form_title": "Edit Purchase",
                "submit_label": "Update Purchase",
                "purchase": purchase,
                "cancel_url": reverse_supplier_url(self.request, "purchase_detail", kwargs={"id_supplier_purchase": purchase.id_supplier_purchase}),
                "form": form,
                "item_formset": formset,
            }
        )
        return context

    def get(self, request, company_slug=None, *args, **kwargs):
        purchase = self.get_purchase()
        form = SupplierPurchaseForm(instance=purchase, user=request.user, supplier=purchase.id_supplier)
        formset = SupplierPurchaseItemFormSet(instance=purchase, form_kwargs={"user": request.user, "supplier": purchase.id_supplier})
        return render(request, self.template_name, self.get_context(purchase, form, formset))

    def post(self, request, company_slug=None, *args, **kwargs):
        purchase = self.get_purchase()
        form = SupplierPurchaseForm(request.POST, instance=purchase, user=request.user, supplier=purchase.id_supplier)
        formset = SupplierPurchaseItemFormSet(request.POST, instance=purchase, form_kwargs={"user": request.user, "supplier": purchase.id_supplier})
        if form.is_valid() and formset.is_valid():
            try:
                purchase = update_purchase_with_items(form, formset, request.user)
                messages.success(request, "Purchase updated successfully.")
                return redirect_supplier_url(request, "purchase_detail", company_slug=company_slug, kwargs={"id_supplier_purchase": purchase.id_supplier_purchase})
            except Exception as error:
                messages.error(request, f"Purchase could not be updated: {error}")
        else:
            messages.error(request, "Please review the purchase form and items.")
        return render(request, self.template_name, self.get_context(purchase, form, formset))


@require_POST
@login_required
def supplier_purchase_cancel_view(request, id_supplier_purchase, company_slug=None):
    permission_response = require_module_action_or_403(request.user, MODULE_NAME, PERMISSION_APPROVE)
    if permission_response:
        return permission_response

    purchase = get_object_or_404(supplier_purchase_list_for_user(request.user), id_supplier_purchase=id_supplier_purchase)
    cancel_purchase(purchase, request.user)
    messages.success(request, "Purchase cancelled successfully.")
    return redirect_supplier_url(request, "purchase_detail", company_slug=company_slug, kwargs={"id_supplier_purchase": purchase.id_supplier_purchase})


class SupplierDocumentCreateView(LoginRequiredMixin, ModulePermissionRequiredMixin, CreateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_CREATE
    model = SupplierDocument
    form_class = SupplierDocumentForm
    template_name = "suppliers/document_form.html"
    login_url = "/login/"

    def get_supplier(self):
        supplier_id = self.kwargs.get("id_supplier") or self.request.GET.get("supplier")
        if not supplier_id:
            return None
        return get_object_or_404(supplier_list_for_user(self.request.user), id_supplier=supplier_id)

    def get_purchase(self):
        purchase_id = self.kwargs.get("id_supplier_purchase") or self.request.GET.get("purchase")
        if not purchase_id:
            return None
        return get_object_or_404(supplier_purchase_list_for_user(self.request.user), id_supplier_purchase=purchase_id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["supplier"] = self.get_supplier()
        kwargs["purchase"] = self.get_purchase()
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        purchase = form.cleaned_data.get("id_purchase") or self.get_purchase()
        supplier = form.cleaned_data.get("id_supplier") or self.get_supplier()
        if purchase:
            self.object.id_purchase = purchase
            self.object.id_supplier = purchase.id_supplier
            self.object.id_company = purchase.id_company
        elif supplier:
            self.object.id_supplier = supplier
            self.object.id_company = supplier.id_company
        else:
            self.object.id_company = self.request.user.id_company
        self.object.uploaded_by = self.request.user
        self.object.save()
        messages.success(self.request, "Document uploaded successfully.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        if self.object.id_purchase_id:
            return reverse_supplier_url(self.request, "purchase_detail", kwargs={"id_supplier_purchase": self.object.id_purchase_id})
        if self.object.id_supplier_id:
            return reverse_supplier_url(self.request, "supplier_detail", kwargs={"id_supplier": self.object.id_supplier_id})
        return reverse_supplier_url(self.request, "supplier_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        supplier = self.get_supplier()
        purchase = self.get_purchase()
        context.update(action_context(self.request.user))
        context.update({"page_title": "Upload Supplier Document", "form_title": "Upload Supplier Document", "submit_label": "Upload Document", "supplier": supplier, "purchase": purchase, "cancel_url": reverse_supplier_url(self.request, "purchase_detail", kwargs={"id_supplier_purchase": purchase.id_supplier_purchase}) if purchase else (reverse_supplier_url(self.request, "supplier_detail", kwargs={"id_supplier": supplier.id_supplier}) if supplier else reverse_supplier_url(self.request, "supplier_list"))})
        return context


@require_POST
@login_required
def supplier_document_delete_view(request, id_supplier_document, company_slug=None):
    permission_response = require_module_action_or_403(request.user, MODULE_NAME, PERMISSION_DELETE)
    if permission_response:
        return permission_response

    document = get_object_or_404(supplier_document_list_for_user(request.user), id_supplier_document=id_supplier_document)
    supplier_id = document.id_supplier_id
    purchase_id = document.id_purchase_id
    document.delete()
    messages.success(request, "Document deleted successfully.")
    if purchase_id:
        return redirect_supplier_url(request, "purchase_detail", company_slug=company_slug, kwargs={"id_supplier_purchase": purchase_id})
    if supplier_id:
        return redirect_supplier_url(request, "supplier_detail", company_slug=company_slug, kwargs={"id_supplier": supplier_id})
    return redirect_supplier_url(request, "supplier_list", company_slug=company_slug)


def get_report_queryset_for_request(request):
    queryset = supplier_purchase_list_for_user(request.user).exclude(status=PURCHASE_STATUS_CANCELLED)
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    supplier_id = (request.GET.get("supplier") or "").strip()
    category = (request.GET.get("category") or "").strip()

    if date_from:
        queryset = queryset.filter(purchase_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(purchase_date__lte=date_to)
    if supplier_id:
        queryset = queryset.filter(id_supplier_id=supplier_id)
    if category:
        queryset = queryset.filter(category=category)
    return queryset


class SupplierReportsView(LoginRequiredMixin, ModulePermissionRequiredMixin, TemplateView):
    module_name = MODULE_NAME
    permission_required = PERMISSION_VIEW
    template_name = "suppliers/reports.html"
    login_url = "/login/"

    def get_queryset(self):
        return get_report_queryset_for_request(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        purchases = self.get_queryset()
        by_supplier = purchases.values("id_supplier__company_name").annotate(total=Sum("total"), paid=Sum("paid_amount"), balance=Sum("balance_due"), count=Count("id_supplier_purchase")).order_by("-total")[:20]
        by_category = purchases.values("category").annotate(total=Sum("total"), paid=Sum("paid_amount"), balance=Sum("balance_due"), count=Count("id_supplier_purchase")).order_by("-total")
        query_string = self.request.GET.urlencode()
        context.update(action_context(self.request.user))
        context.update(
            {
                "page_title": "Supplier Reports",
                "suppliers": supplier_list_for_user(self.request.user),
                "category_options": SUPPLIER_CATEGORY_CHOICES,
                "purchases": purchases[:100],
                "by_supplier": by_supplier,
                "by_category": by_category,
                "total_purchases": money(purchases.aggregate(total=Sum("total"))["total"] or Decimal("0.00")),
                "total_paid": money(purchases.aggregate(total=Sum("paid_amount"))["total"] or Decimal("0.00")),
                "total_balance": money(purchases.aggregate(total=Sum("balance_due"))["total"] or Decimal("0.00")),
                "current_date_from": self.request.GET.get("date_from", ""),
                "current_date_to": self.request.GET.get("date_to", ""),
                "current_supplier": self.request.GET.get("supplier", ""),
                "current_category": self.request.GET.get("category", ""),
                "export_querystring": query_string,
            }
        )
        return context


def _xlsx_cell(value, ref):
    if value is None:
        value = ""
    if isinstance(value, (int, float, Decimal)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def _column_name(number):
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def build_simple_xlsx(headers, rows):
    xml_rows = []
    all_rows = [headers] + rows
    for row_index, row in enumerate(all_rows, 1):
        cells = []
        for col_index, value in enumerate(row, 1):
            cells.append(_xlsx_cell(value, f"{_column_name(col_index)}{row_index}"))
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'''
    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Supplier Purchases" sheetId="1" r:id="rId1"/></sheets></workbook>'''
    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    workbook_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'''
    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'''

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml)
        workbook.writestr("_rels/.rels", rels_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


def purchase_export_rows(purchases):
    rows = []
    for purchase in purchases:
        rows.append([
            purchase.purchase_number or "",
            purchase.purchase_date.isoformat() if purchase.purchase_date else "",
            purchase.id_supplier.company_name,
            purchase.external_document_number or "",
            purchase.get_status_display(),
            purchase.get_payment_status_display(),
            purchase.subtotal,
            purchase.tax_amount,
            purchase.discount_amount,
            purchase.total,
            purchase.paid_amount,
            purchase.balance_due,
            purchase.description or "",
        ])
    return rows


@login_required
def supplier_reports_xlsx_view(request, company_slug=None):
    permission_response = require_module_action_or_403(request.user, MODULE_NAME, PERMISSION_VIEW)
    if permission_response:
        return permission_response
    headers = [ui(value) for value in ["Purchase #", "Date", "Supplier", "Reference", "Status", "Payment", "Subtotal", "Tax", "Discount", "Total", "Paid", "Balance", "Description"]]
    purchases = get_report_queryset_for_request(request)
    content = build_simple_xlsx(headers, purchase_export_rows(purchases))
    response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="supplier_purchases_report.xlsx"'
    response["Cache-Control"] = "no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    return response


@login_required
def supplier_reports_pdf_view(request, company_slug=None):
    permission_response = require_module_action_or_403(request.user, MODULE_NAME, PERMISSION_VIEW)
    if permission_response:
        return permission_response

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    purchases = list(get_report_queryset_for_request(request))
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 42

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(42, y, ui("Supplier Purchases Report"))
    y -= 22
    pdf.setFont("Helvetica", 9)
    pdf.drawString(42, y, f"{ui('Total purchases')}: ${money(sum((p.total for p in purchases), Decimal('0.00')))}")
    y -= 22

    pdf.setFont("Helvetica-Bold", 8)
    headers = [ui(value) for value in ["Date", "Purchase", "Supplier", "Total", "Paid", "Balance"]]
    x_positions = [42, 92, 165, 345, 420, 490]
    for x, header in zip(x_positions, headers):
        pdf.drawString(x, y, header)
    y -= 10
    pdf.line(42, y, width - 42, y)
    y -= 14

    pdf.setFont("Helvetica", 8)
    for purchase in purchases[:55]:
        if y < 55:
            pdf.showPage()
            y = height - 42
            pdf.setFont("Helvetica", 8)
        supplier_name = (purchase.id_supplier.company_name or "")[:28]
        values = [
            purchase.purchase_date.strftime("%Y-%m-%d") if purchase.purchase_date else "",
            purchase.purchase_number or "",
            supplier_name,
            f"${purchase.total}",
            f"${purchase.paid_amount}",
            f"${purchase.balance_due}",
        ]
        for x, value in zip(x_positions, values):
            pdf.drawString(x, y, str(value))
        y -= 14

    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="supplier_purchases_report.pdf"'
    response["Cache-Control"] = "no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    return response


class SupplierViewSet(TenantModelViewSet):
    module_name = MODULE_NAME
    queryset = Supplier.objects.select_related("id_company").all()
    serializer_class = SupplierSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return supplier_list_for_user(self.request.user)

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return
        serializer.save(id_company=self.request.user.id_company, created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        if not user_can_access_supplier_object(self.request.user, instance):
            raise PermissionDenied("You can only update suppliers from your company.")
        serializer.save(updated_by=self.request.user)


class SupplierOfferViewSet(TenantModelViewSet):
    module_name = MODULE_NAME
    queryset = SupplierOffer.objects.select_related("id_company", "id_supplier").all()
    serializer_class = SupplierOfferSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return supplier_offer_list_for_user(self.request.user)


class SupplierPurchaseViewSet(TenantModelViewSet):
    module_name = MODULE_NAME
    queryset = SupplierPurchase.objects.select_related("id_company", "id_supplier").prefetch_related("items").all()
    serializer_class = SupplierPurchaseSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return supplier_purchase_list_for_user(self.request.user)


class SupplierDocumentViewSet(TenantModelViewSet):
    module_name = MODULE_NAME
    queryset = SupplierDocument.objects.select_related("id_company", "id_supplier", "id_purchase").all()
    serializer_class = SupplierDocumentSerializer
    tenant_filter_path = "id_company"
    tenant_create_field = "id_company"

    def get_queryset(self):
        return supplier_document_list_for_user(self.request.user)
