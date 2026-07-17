from django.db import models


class Client(models.Model):
    id_client = models.BigAutoField(primary_key=True)

    id_company = models.ForeignKey(
        "companies.Company",
        db_column="id_company",
        on_delete=models.CASCADE,
        related_name="clients",
    )

    client_code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        blank=True,
        null=True,
    )

    name = models.CharField(max_length=150)

    first_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    middle_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    last_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    second_last_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    dni = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Optional tax or identity document number.",
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    email = models.EmailField(
        max_length=150,
        blank=True,
        null=True,
    )

    address = models.TextField(
        blank=True,
        null=True,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    state = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "client"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["id_company", "name"], name="client_company_name_idx"),
            models.Index(fields=["client_code"], name="client_code_idx"),
            models.Index(fields=["email"], name="client_email_idx"),
            models.Index(fields=["phone"], name="client_phone_idx"),
            models.Index(fields=["id_company", "dni"], name="client_company_dni_idx"),
        ]

    @property
    def full_name(self):
        return " ".join(
            filter(
                None,
                [
                    self.first_name,
                    self.middle_name,
                    self.last_name,
                    self.second_last_name,
                ],
            )
        ).strip()

    def save(self, *args, **kwargs):
        if self.full_name:
            self.name = self.full_name

        super().save(*args, **kwargs)

        if not self.client_code:
            self.client_code = f"CLI-{self.id_client:06d}"

            Client.objects.filter(
                id_client=self.id_client,
            ).update(
                client_code=self.client_code,
            )

    def __str__(self):
        if self.client_code:
            return f"{self.client_code} - {self.name}"

        return self.name
