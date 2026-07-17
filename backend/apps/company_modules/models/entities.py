from django.db import models

from apps.accounts.models.choices import MODULE_CHOICES


class CompanyModule(models.Model):
    id_company_module = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="company_modules",
    )
    module = models.CharField(max_length=100, choices=MODULE_CHOICES)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "company_module"
        unique_together = ("id_company", "module")
        ordering = ["id_company__name", "module"]

    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"{self.id_company.name} - {self.module} - {status}"
