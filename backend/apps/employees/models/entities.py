from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .choices import STATUS_ACTIVE, STATUS_CHOICES


class Employee(models.Model):
    """Employment metadata linked one-to-one with the CRM user account.

    UserAccount is the single identity/login record. This model remains as a
    compatibility profile so existing project data and integrations keep their
    historical employee relationship without exposing a second CRUD module.
    """

    id_employee = models.BigAutoField(primary_key=True)
    id_user = models.OneToOneField(
        "accounts.UserAccount",
        db_column="id_user",
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="employees",
    )
    identification = models.CharField(max_length=50, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    # Legacy field kept only to preserve previous records. New forms use
    # ``position`` as the single Position / Category value.
    category = models.CharField(max_length=100, blank=True, null=True, editable=False)
    schedule = models.CharField(max_length=100, blank=True, null=True)
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
    )
    hire_date = models.DateField(default=timezone.localdate, editable=False)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    class Meta:
        db_table = "employee"
        ordering = ["id_user__first_name", "id_user__last_name"]
        indexes = [
            models.Index(fields=["status"], name="employee_status_idx"),
            models.Index(fields=["position"], name="employee_position_idx"),
        ]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return self.id_user.get_full_name()

    @property
    def job_title(self):
        return self.position or self.category
