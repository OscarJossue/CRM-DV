from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0004_client_dni"),
        ("invoices", "0003_invoice_pdf_header_dark_invoiceitem_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="client_billing_dni",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
