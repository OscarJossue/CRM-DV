from django.db import models
from django.utils import timezone


class SmtpSetting(models.Model):
    id_smtp_setting = models.BigAutoField(primary_key=True)

    id_company = models.OneToOneField(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="smtp_setting",
    )

    smtp_host = models.CharField(
        max_length=255,
        default="smtp.gmail.com",
    )

    smtp_port = models.PositiveIntegerField(
        default=587,
    )

    use_tls = models.BooleanField(
        default=True,
    )

    use_ssl = models.BooleanField(
        default=False,
    )

    smtp_username = models.EmailField(
        max_length=255,
        blank=True,
        default="",
    )

    smtp_password = models.TextField(
        blank=True,
        default="",
    )

    default_from_email = models.EmailField(
        max_length=255,
        blank=True,
        default="",
    )

    from_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(
        default=False,
    )

    last_test_status = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    last_test_message = models.TextField(
        blank=True,
        null=True,
    )

    last_tested_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "smtp_setting"
        verbose_name = "SMTP Setting"
        verbose_name_plural = "SMTP Settings"

    def __str__(self):
        return f"SMTP - {self.id_company}"