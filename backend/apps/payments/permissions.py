from apps.core.permissions import HasModulePermission


class PaymentPermission(HasModulePermission):
    pass


def user_can_access_payment(user, payment):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    user_company_id = getattr(user, "id_company_id", None)

    if not user_company_id:
        return False

    if payment.id_company_id and payment.id_company_id == user_company_id:
        return True

    if payment.id_invoice_id and payment.id_invoice.id_company_id == user_company_id:
        return True

    if payment.allocations.filter(id_company_id=user_company_id).exists():
        return True

    if payment.financial_movements.filter(id_company_id=user_company_id).exists():
        return True

    if payment.credit_movements.filter(id_company_id=user_company_id).exists():
        return True

    return False
