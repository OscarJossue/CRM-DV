from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models

from .choices import (
    LANGUAGE_CHOICES,
    LANGUAGE_ENGLISH,
    MODULE_CHOICES,
    STATUS_ACTIVE,
    STATUS_CHOICES,
)


class Role(models.Model):
    id_role = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="roles",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    is_contractor_only = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "Restricts users in this role to assigned inspections/projects, "
            "evidence uploads, notes and submit-for-audit actions."
        ),
    )

    class Meta:
        db_table = "role"
        unique_together = ("id_company", "name")
        ordering = ["id_company__name", "name"]
        indexes = [
            models.Index(fields=["status"], name="role_status_idx"),
            models.Index(fields=["name"], name="role_name_idx"),
        ]

    def __str__(self):
        return f"{self.name} - {self.id_company.name}"

    @property
    def is_active_role(self):
        return self.status == STATUS_ACTIVE


class RolePermission(models.Model):
    id_permission = models.BigAutoField(primary_key=True)
    id_role = models.ForeignKey(
        Role,
        db_column="id_role",
        on_delete=models.CASCADE,
        related_name="permissions",
    )
    module = models.CharField(max_length=100, choices=MODULE_CHOICES)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False)

    class Meta:
        db_table = "role_permission"
        unique_together = ("id_role", "module")
        ordering = ["module"]
        indexes = [
            models.Index(fields=["module"], name="role_perm_module_idx"),
        ]

    def __str__(self):
        return f"{self.id_role.name} - {self.get_module_display()}"


class UserAccountManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)

        is_platform_user = bool(user.is_staff or user.is_superuser)
        if is_platform_user:
            if user.id_company_id is not None or user.id_role_id is not None:
                raise ValueError(
                    "Platform users cannot be assigned to a tenant company or tenant role."
                )
        elif user.id_company_id is None:
            raise ValueError("Company is required for tenant users.")

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["id_company"] = None
        extra_fields["id_role"] = None
        extra_fields.setdefault("first_name", "Super")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("status", STATUS_ACTIVE)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class UserAccount(AbstractBaseUser, PermissionsMixin):
    id_user = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="user_accounts",
        null=True,
        blank=True,
        help_text="Required for tenant users; empty for platform staff and superusers.",
    )
    id_role = models.ForeignKey(
        Role,
        db_column="id_role",
        on_delete=models.RESTRICT,
        related_name="users",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(max_length=150, unique=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_company_owner = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Allows this user to manage company-level workspace settings.",
    )
    preferred_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default=LANGUAGE_ENGLISH,
        help_text="Personal interface language used by platform administrators.",
    )
    last_login = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserAccountManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]

    class Meta:
        db_table = "user_account"
        ordering = ["first_name", "last_name"]
        indexes = [
            models.Index(fields=["status"], name="user_status_idx"),
            models.Index(fields=["email"], name="user_email_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(is_staff=True, id_company__isnull=True)
                    | models.Q(
                        is_staff=False,
                        is_superuser=False,
                        id_company__isnull=False,
                    )
                ),
                name="user_company_scope_ck",
            ),
        ]

    def clean(self):
        super().clean()

        if self.is_superuser and not self.is_staff:
            raise ValidationError({"is_staff": "A superuser must also be platform staff."})

        if self.is_staff:
            if self.id_company_id is not None:
                raise ValidationError(
                    {"id_company": "Platform users cannot belong to a tenant company."}
                )
            if self.id_role_id is not None:
                raise ValidationError(
                    {"id_role": "Platform users cannot use a tenant company role."}
                )
        elif self.id_company_id and self.id_role_id:
            role_company_id = getattr(self.id_role, "id_company_id", None)
            if role_company_id != self.id_company_id:
                raise ValidationError(
                    {"id_role": "The selected role must belong to the same company."}
                )

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def get_short_name(self):
        return self.first_name or self.email

    @property
    def employment_profile(self):
        """Return the linked employee profile without raising when legacy data is incomplete."""
        try:
            return self.employee_profile
        except ObjectDoesNotExist:
            return None

    @property
    def identification(self):
        profile = self.employment_profile
        return profile.identification if profile else None

    @property
    def position(self):
        profile = self.employment_profile
        if not profile:
            return None
        return profile.position or profile.category

    @property
    def hire_date(self):
        profile = self.employment_profile
        return profile.hire_date if profile else None
