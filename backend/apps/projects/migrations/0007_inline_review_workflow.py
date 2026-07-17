import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def normalize_project_statuses(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Project.objects.filter(status="audit").update(status="review")
    Project.objects.filter(status="active").update(status="pending")
    Project.objects.filter(status="on_hold").update(status="in_progress")
    Project.objects.filter(status__isnull=True).update(status="draft")
    Project.objects.filter(status="").update(status="draft")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0006_contractor_mobile_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="review_notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                db_column="reviewed_by_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_projects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="cancellation_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="cancelled_by",
            field=models.ForeignKey(
                blank=True,
                db_column="cancelled_by_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cancelled_projects",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(normalize_project_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="project",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("pending", "Pending"),
                    ("in_progress", "In Progress"),
                    ("review", "Under Review"),
                    ("completed", "Approved"),
                    ("cancelled", "Void"),
                ],
                default="draft",
                max_length=50,
            ),
        ),
    ]
