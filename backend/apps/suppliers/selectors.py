from .models import Supplier, SupplierDocument, SupplierOffer, SupplierPurchase


def _company_filter(queryset, user):
    if not user or not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def supplier_list_for_user(user):
    queryset = Supplier.objects.select_related("id_company", "created_by", "updated_by").all()
    return _company_filter(queryset, user).order_by("company_name")


def supplier_get_for_user(user, id_supplier):
    return supplier_list_for_user(user).filter(id_supplier=id_supplier).first()


def supplier_offer_list_for_user(user):
    queryset = SupplierOffer.objects.select_related("id_company", "id_supplier", "created_by", "updated_by").all()
    return _company_filter(queryset, user).order_by("id_supplier__company_name", "name")


def supplier_offer_get_for_user(user, id_supplier_offer):
    return supplier_offer_list_for_user(user).filter(id_supplier_offer=id_supplier_offer).first()


def supplier_purchase_list_for_user(user):
    queryset = SupplierPurchase.objects.select_related("id_company", "id_supplier", "created_by", "updated_by").prefetch_related("items", "documents").all()
    return _company_filter(queryset, user).order_by("-purchase_date", "-id_supplier_purchase")


def supplier_purchase_get_for_user(user, id_supplier_purchase):
    return supplier_purchase_list_for_user(user).filter(id_supplier_purchase=id_supplier_purchase).first()


def supplier_document_list_for_user(user):
    queryset = SupplierDocument.objects.select_related("id_company", "id_supplier", "id_purchase", "uploaded_by").all()
    return _company_filter(queryset, user).order_by("-created_at", "-id_supplier_document")
