import os

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from .choices import (
    COMPANY_LANGUAGE_CHOICES,
    COMPANY_PLAN_CHOICES,
    COMPANY_STATUS_CHOICES,
    LANGUAGE_ENGLISH,
    PLAN_STARTER,
    STATUS_ACTIVE,
)


def company_logo_upload_path(instance, filename):
    base_name, extension = os.path.splitext(filename)
    company_id = instance.id_company or "new"
    clean_extension = extension.lower()
    return f"companies/logos/{company_id}/logo{clean_extension}"


def build_unique_company_slug(instance):
    base_slug = slugify(instance.name or "")

    if not base_slug:
        base_slug = "company"

    slug = base_slug
    counter = 2

    queryset = Company.objects.filter(slug=slug)

    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

        queryset = Company.objects.filter(slug=slug)

        if instance.pk:
            queryset = queryset.exclude(pk=instance.pk)

    return slug


class Company(models.Model):
    id_company = models.BigAutoField(primary_key=True)

    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(
        max_length=180,
        unique=True,
        db_index=True,
        blank=True,
    )

    legal_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(max_length=180, blank=True, null=True)
    phone = models.CharField(max_length=40, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=120, blank=True, null=True)
    state = models.CharField(max_length=120, blank=True, null=True)
    country = models.CharField(max_length=120, blank=True, null=True)

    logo = models.ImageField(
        upload_to=company_logo_upload_path,
        blank=True,
        null=True,
        max_length=500,
    )

    description = models.TextField(blank=True, null=True)

    default_language = models.CharField(
        max_length=10,
        choices=COMPANY_LANGUAGE_CHOICES,
        default=LANGUAGE_ENGLISH,
        db_index=True,
        help_text="Default interface language for this company workspace.",
    )

    plan = models.CharField(
        max_length=100,
        choices=COMPANY_PLAN_CHOICES,
        default=PLAN_STARTER,
        db_index=True,
    )

    status = models.CharField(
        max_length=50,
        choices=COMPANY_STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )

    user_limit = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1)],
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "company"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status"], name="company_status_idx"),
            models.Index(fields=["plan"], name="company_plan_idx"),
            models.Index(fields=["name"], name="company_name_idx"),
            models.Index(fields=["slug"], name="company_slug_idx"),
        ]

    def __str__(self):
        return self.name

    @property
    def is_active_company(self):
        return self.status == STATUS_ACTIVE

    @property
    def workspace_path(self):
        if not self.slug:
            return None

        return f"/{self.slug}/dashboard/"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = build_unique_company_slug(self)
        else:
            self.slug = slugify(self.slug)

        super().save(*args, **kwargs)