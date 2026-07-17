from django.urls import path

from .views import (
    EmployeeCreateView,
    EmployeeDetailView,
    EmployeeListView,
    EmployeeUpdateView,
    employee_activate_view,
    employee_deactivate_view,
)

app_name = "employees"

urlpatterns = [
    path("", EmployeeListView.as_view(), name="employee_list"),
    path("create/", EmployeeCreateView.as_view(), name="employee_create"),
    path("<int:id_employee>/", EmployeeDetailView.as_view(), name="employee_detail"),
    path("<int:id_employee>/edit/", EmployeeUpdateView.as_view(), name="employee_update"),
    path("<int:id_employee>/activate/", employee_activate_view, name="employee_activate"),
    path("<int:id_employee>/deactivate/", employee_deactivate_view, name="employee_deactivate"),
]
