from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("suppliers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplieroffer",
            name="product_code",
            field=models.CharField(blank=True, db_index=True, max_length=80, null=True),
        ),
    ]
