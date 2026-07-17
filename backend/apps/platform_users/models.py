from django.db import models

from .constants import PLATFORM_MODULE_CHOICES


class PlatformUserPermission(models.Model):
    id_permission = models.BigAutoField(primary_key=True)

    id_user = models.ForeignKey(
        "accounts.UserAccount",
        db_column="id_user",
        on_delete=models.CASCADE,
        related_name="platform_permissions",
    )

    module = models.CharField(
        max_length=100,
        choices=PLATFORM_MODULE_CHOICES,
        db_index=True,
    )

    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_user_permission"
        unique_together = ("id_user", "module")
        ordering = ["module"]
        indexes = [
            models.Index(fields=["module"], name="plat_user_perm_module_idx"),
        ]

    def __str__(self):
        return f"{self.id_user.email} - {self.module}"