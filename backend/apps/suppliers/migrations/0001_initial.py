# Manually prepared for the Suppliers module integration.

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone

import apps.suppliers.models.entities


MODULE_SUPPLIERS = "suppliers"


def seed_suppliers_module(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    CompanyModule = apps.get_model("company_modules", "CompanyModule")
    Role = apps.get_model("accounts", "Role")
    RolePermission = apps.get_model("accounts", "RolePermission")

    for company in Company.objects.all():
        CompanyModule.objects.get_or_create(
            id_company=company,
            module=MODULE_SUPPLIERS,
            defaults={"is_enabled": True},
        )

    privileged_keywords = ("owner", "admin", "super", "manager")

    for role in Role.objects.select_related("id_company").all():
        role_name = (role.name or "").lower()
        privileged = any(keyword in role_name for keyword in privileged_keywords)
        RolePermission.objects.get_or_create(
            id_role=role,
            module=MODULE_SUPPLIERS,
            defaults={
                "can_view": True,
                "can_create": True,
                "can_edit": True,
                "can_delete": privileged,
                "can_approve": privileged,
            },
        )


def unseed_suppliers_module(apps, schema_editor):
    CompanyModule = apps.get_model("company_modules", "CompanyModule")
    RolePermission = apps.get_model("accounts", "RolePermission")
    CompanyModule.objects.filter(module=MODULE_SUPPLIERS).delete()
    RolePermission.objects.filter(module=MODULE_SUPPLIERS).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0005_alter_rolepermission_module"),
        ("companies", "0006_remove_company_website"),
        ("company_modules", "0005_alter_companymodule_module"),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id_supplier", models.BigAutoField(primary_key=True, serialize=False)),
                ("supplier_code", models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ("company_name", models.CharField(db_index=True, max_length=255)),
                ("contact_name", models.CharField(blank=True, max_length=180, null=True)),
                ("email", models.EmailField(blank=True, max_length=180, null=True)),
                ("phone", models.CharField(blank=True, max_length=50, null=True)),
                ("address", models.TextField(blank=True, null=True)),
                ("city", models.CharField(blank=True, max_length=120, null=True)),
                ("state", models.CharField(blank=True, max_length=120, null=True)),
                ("zip_code", models.CharField(blank=True, max_length=30, null=True)),
                ("country", models.CharField(blank=True, max_length=120, null=True)),
                ("website", models.URLField(blank=True, max_length=255, null=True)),
                ("tax_id", models.CharField(blank=True, max_length=80, null=True)),
                ("supplier_type", models.CharField(choices=[("materials", "Materials"), ("services", "Services"), ("equipment", "Equipment"), ("transportation", "Transportation"), ("office", "Office"), ("software", "Software"), ("marketing", "Marketing"), ("other", "Other")], db_index=True, default="other", max_length=60)),
                ("status", models.CharField(choices=[("active", "Active"), ("inactive", "Inactive"), ("blocked", "Blocked")], db_index=True, default="active", max_length=30)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_suppliers", to=settings.AUTH_USER_MODEL)),
                ("id_company", models.ForeignKey(db_column="id_company", on_delete=django.db.models.deletion.CASCADE, related_name="suppliers", to="companies.company")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_suppliers", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "supplier",
                "ordering": ["company_name"],
            },
        ),
        migrations.CreateModel(
            name="SupplierOffer",
            fields=[
                ("id_supplier_offer", models.BigAutoField(primary_key=True, serialize=False)),
                ("offer_type", models.CharField(choices=[("product", "Product"), ("service", "Service"), ("material", "Material"), ("equipment", "Equipment"), ("rental", "Rental"), ("other", "Other")], db_index=True, default="product", max_length=50)),
                ("name", models.CharField(db_index=True, max_length=255)),
                ("category", models.CharField(choices=[("materials", "Materials"), ("tools", "Tools"), ("equipment", "Equipment"), ("labor", "Labor"), ("transportation", "Transportation"), ("rentals", "Rentals"), ("office", "Office"), ("software", "Software"), ("marketing", "Marketing"), ("other", "Other")], db_index=True, default="other", max_length=60)),
                ("description", models.TextField(blank=True, null=True)),
                ("unit", models.CharField(blank=True, max_length=50, null=True)),
                ("estimated_price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("status", models.CharField(choices=[("active", "Active"), ("inactive", "Inactive"), ("blocked", "Blocked")], db_index=True, default="active", max_length=30)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_supplier_offers", to=settings.AUTH_USER_MODEL)),
                ("id_company", models.ForeignKey(db_column="id_company", on_delete=django.db.models.deletion.CASCADE, related_name="supplier_offers", to="companies.company")),
                ("id_supplier", models.ForeignKey(db_column="id_supplier", on_delete=django.db.models.deletion.CASCADE, related_name="offers", to="suppliers.supplier")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_supplier_offers", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "supplier_offer",
                "ordering": ["id_supplier__company_name", "name"],
            },
        ),
        migrations.CreateModel(
            name="SupplierPurchase",
            fields=[
                ("id_supplier_purchase", models.BigAutoField(primary_key=True, serialize=False)),
                ("purchase_number", models.CharField(blank=True, db_index=True, max_length=50, null=True)),
                ("external_document_number", models.CharField(blank=True, max_length=120, null=True)),
                ("purchase_date", models.DateField(db_index=True, default=timezone.localdate)),
                ("category", models.CharField(choices=[("materials", "Materials"), ("tools", "Tools"), ("equipment", "Equipment"), ("labor", "Labor"), ("transportation", "Transportation"), ("rentals", "Rentals"), ("office", "Office"), ("software", "Software"), ("marketing", "Marketing"), ("other", "Other")], db_index=True, default="other", max_length=60)),
                ("description", models.TextField(blank=True, null=True)),
                ("subtotal", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("tax_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("discount_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("paid_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("balance_due", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("status", models.CharField(choices=[("draft", "Draft"), ("pending", "Pending"), ("completed", "Completed"), ("cancelled", "Cancelled")], db_index=True, default="draft", max_length=30)),
                ("payment_status", models.CharField(choices=[("unpaid", "Unpaid"), ("partial", "Partially Paid"), ("paid", "Paid")], db_index=True, default="unpaid", max_length=30)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_supplier_purchases", to=settings.AUTH_USER_MODEL)),
                ("id_company", models.ForeignKey(db_column="id_company", on_delete=django.db.models.deletion.CASCADE, related_name="supplier_purchases", to="companies.company")),
                ("id_supplier", models.ForeignKey(db_column="id_supplier", on_delete=django.db.models.deletion.RESTRICT, related_name="purchases", to="suppliers.supplier")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_supplier_purchases", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "supplier_purchase",
                "ordering": ["-purchase_date", "-id_supplier_purchase"],
            },
        ),
        migrations.CreateModel(
            name="SupplierPurchaseItem",
            fields=[
                ("id_supplier_purchase_item", models.BigAutoField(primary_key=True, serialize=False)),
                ("item_name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                ("quantity", models.DecimalField(decimal_places=2, default=Decimal("1.00"), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("unit", models.CharField(blank=True, max_length=50, null=True)),
                ("unit_price", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("tax_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id_offer", models.ForeignKey(blank=True, db_column="id_supplier_offer", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="purchase_items", to="suppliers.supplieroffer")),
                ("id_purchase", models.ForeignKey(db_column="id_supplier_purchase", on_delete=django.db.models.deletion.CASCADE, related_name="items", to="suppliers.supplierpurchase")),
            ],
            options={
                "db_table": "supplier_purchase_item",
                "ordering": ["id_supplier_purchase_item"],
            },
        ),
        migrations.CreateModel(
            name="SupplierDocument",
            fields=[
                ("id_supplier_document", models.BigAutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("document_type", models.CharField(choices=[("receipt", "Receipt"), ("supplier_invoice", "Supplier Invoice"), ("quote", "Quote"), ("contract", "Contract"), ("warranty", "Warranty"), ("other", "Other")], db_index=True, default="receipt", max_length=50)),
                ("file", models.FileField(max_length=500, upload_to=apps.suppliers.models.entities.supplier_document_upload_path)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("id_company", models.ForeignKey(db_column="id_company", on_delete=django.db.models.deletion.CASCADE, related_name="supplier_documents", to="companies.company")),
                ("id_purchase", models.ForeignKey(blank=True, db_column="id_supplier_purchase", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="suppliers.supplierpurchase")),
                ("id_supplier", models.ForeignKey(blank=True, db_column="id_supplier", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="suppliers.supplier")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_supplier_documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "supplier_document",
                "ordering": ["-created_at", "-id_supplier_document"],
            },
        ),
        migrations.AddIndex(model_name="supplier", index=models.Index(fields=["id_company", "status"], name="supplier_company_status_idx")),
        migrations.AddIndex(model_name="supplier", index=models.Index(fields=["id_company", "supplier_type"], name="supplier_company_type_idx")),
        migrations.AddIndex(model_name="supplier", index=models.Index(fields=["company_name"], name="supplier_company_name_idx")),
        migrations.AddConstraint(model_name="supplier", constraint=models.UniqueConstraint(condition=(models.Q(supplier_code__isnull=False) & ~models.Q(supplier_code="")), fields=("id_company", "supplier_code"), name="uniq_sup_code_company")),
        migrations.AddConstraint(model_name="supplier", constraint=models.UniqueConstraint(fields=("id_company", "company_name"), name="uniq_sup_name_company")),
        migrations.AddIndex(model_name="supplieroffer", index=models.Index(fields=["id_company", "category"], name="supplier_offer_category_idx")),
        migrations.AddIndex(model_name="supplieroffer", index=models.Index(fields=["id_company", "status"], name="supplier_offer_status_idx")),
        migrations.AddIndex(model_name="supplierpurchase", index=models.Index(fields=["id_company", "status"], name="supplier_purchase_status_idx")),
        migrations.AddIndex(model_name="supplierpurchase", index=models.Index(fields=["id_company", "payment_status"], name="sup_purch_pay_idx")),
        migrations.AddIndex(model_name="supplierpurchase", index=models.Index(fields=["id_company", "purchase_date"], name="supplier_purchase_date_idx")),
        migrations.AddConstraint(model_name="supplierpurchase", constraint=models.UniqueConstraint(condition=(models.Q(purchase_number__isnull=False) & ~models.Q(purchase_number="")), fields=("id_company", "purchase_number"), name="uniq_sup_purch_num_company")),
        migrations.AddIndex(model_name="supplierdocument", index=models.Index(fields=["id_company", "document_type"], name="supplier_document_type_idx")),
        migrations.AddIndex(model_name="supplierdocument", index=models.Index(fields=["id_company", "created_at"], name="supplier_document_date_idx")),
        migrations.RunPython(seed_suppliers_module, reverse_code=unseed_suppliers_module),
    ]
