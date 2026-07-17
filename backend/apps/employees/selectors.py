from .models import Employee


def employee_list_for_user(user):
    queryset = Employee.objects.select_related(
        "id_user",
        "id_company",
        "id_user__id_role",
    ).all().order_by(
        "id_user__first_name",
        "id_user__last_name",
    )

    if not user.is_authenticated:
        return queryset.none()

    if user.is_superuser:
        return queryset

    return queryset.filter(id_company=user.id_company_id)


def employee_get_for_user(user, id_employee):
    return employee_list_for_user(user).filter(id_employee=id_employee).first()


def employee_get_by_id(id_employee):
    return Employee.objects.filter(id_employee=id_employee).first()
