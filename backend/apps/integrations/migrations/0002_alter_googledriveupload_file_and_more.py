# Generated to keep local makemigrations output stable.
import apps.integrations.models.entities
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="googledriveupload",
            name="file",
            field=models.FileField(max_length=600, upload_to=apps.integrations.models.entities.integration_upload_path),
        ),
        migrations.AlterField(
            model_name="integrationlog",
            name="started_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
