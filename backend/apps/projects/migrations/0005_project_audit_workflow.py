import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0004_project_project_notes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="submitted_for_audit_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="audit_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="projectgalleryimage",
            name="uploaded_by",
            field=models.ForeignKey(
                blank=True,
                db_column="uploaded_by_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="project_gallery_uploads",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
