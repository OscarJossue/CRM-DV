from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Employee
from .models.choices import STATUS_ACTIVE, STATUS_INACTIVE


_UNSET = object()


def employee_validate_company_user(company, user_account):
    if not company:
        raise ValidationError("Company is required.")
    if not user_account:
        raise ValidationError("User account is required.")
    if company.status != STATUS_ACTIVE:
        raise ValidationError("Cannot create employees for an inactive company.")
    if user_account.id_company_id != company.id_company:
        raise ValidationError("The selected user does not belong to this company.")


@transaction.atomic
def sync_employee_profile(user_account, identification=_UNSET, position=_UNSET):
    """Create or synchronize the compatibility employee profile for a user."""
    if not user_account or not user_account.pk or not user_account.id_company_id:
        return None

    hire_date = (
        user_account.created_at.date()
        if getattr(user_account, "created_at", None)
        else timezone.localdate()
    )
    employee, created = Employee.objects.get_or_create(
        id_user=user_account,
        defaults={
            "id_company": user_account.id_company,
            "hire_date": hire_date,
            "status": user_account.status,
            "identification": None if identification is _UNSET else identification,
            "position": None if position is _UNSET else position,
        },
    )

    changed = []
    if employee.id_company_id != user_account.id_company_id:
        employee.id_company = user_account.id_company
        changed.append("id_company")
    if employee.status != user_account.status:
        employee.status = user_account.status
        changed.append("status")
    if not employee.hire_date:
        employee.hire_date = hire_date
        changed.append("hire_date")
    if identification is not _UNSET and employee.identification != identification:
        employee.identification = identification
        changed.append("identification")
    if position is not _UNSET and employee.position != position:
        employee.position = position
        changed.append("position")
    if not employee.position and employee.category:
        employee.position = employee.category
        changed.append("position")

    if changed and not created:
        employee.save(update_fields=list(dict.fromkeys(changed)))
    return employee


@transaction.atomic
def employee_create(**data):
    company = data.get("id_company")
    user_account = data.get("id_user")
    employee_validate_company_user(company, user_account)

    status = data.get("status")
    if status is not None:
        user_account.status = status
        user_account.is_active = status == STATUS_ACTIVE
        user_account.save(update_fields=["status", "is_active"])

    employee = sync_employee_profile(
        user_account,
        identification=data.get("identification"),
        position=data.get("position"),
    )

    # Preserve old operational metadata for integrations that still supply it.
    changed = []
    for field in ("schedule", "hourly_rate"):
        if field in data and getattr(employee, field) != data[field]:
            setattr(employee, field, data[field])
            changed.append(field)
    if changed:
        employee.save(update_fields=changed)
    return employee


@transaction.atomic
def employee_update(employee, **data):
    employee_validate_company_user(employee.id_company, employee.id_user)

    status = data.get("status")
    if status is not None:
        employee.id_user.status = status
        employee.id_user.is_active = status == STATUS_ACTIVE
        employee.id_user.save(update_fields=["status", "is_active"])

    profile_kwargs = {}
    if "identification" in data:
        profile_kwargs["identification"] = data["identification"]
    if "position" in data:
        profile_kwargs["position"] = data["position"]
    employee = sync_employee_profile(employee.id_user, **profile_kwargs)

    changed = []
    for field in ("schedule", "hourly_rate"):
        if field in data and getattr(employee, field) != data[field]:
            setattr(employee, field, data[field])
            changed.append(field)
    if changed:
        employee.save(update_fields=changed)
    return employee


@transaction.atomic
def employee_activate(employee):
    employee.id_user.status = STATUS_ACTIVE
    employee.id_user.is_active = True
    employee.id_user.save(update_fields=["status", "is_active"])
    return sync_employee_profile(employee.id_user)


@transaction.atomic
def employee_deactivate(employee):
    employee.id_user.status = STATUS_INACTIVE
    employee.id_user.is_active = False
    employee.id_user.save(update_fields=["status", "is_active"])
    return sync_employee_profile(employee.id_user)
