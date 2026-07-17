import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def normalize_inspection_statuses(apps, schema_editor):
    Inspection = apps.get_model("inspections", "Inspection")
    InspectionAssignment = apps.get_model("inspections", "InspectionAssignment")
    Inspection.objects.filter(status="audit").update(status="review")
    InspectionAssignment.objects.filter(status="audit").update(status="review")


class Migration(migrations.Migration):
    dependencies = [
        ("inspections", "0008_contractor_mobile_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="inspectionassignment",
            name="review_notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inspectionassignment",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                db_column="reviewed_by_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_inspection_assignments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="inspectionassignment",
            name="cancellation_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inspectionassignment",
            name="cancelled_by",
            field=models.ForeignKey(
                blank=True,
                db_column="cancelled_by_id",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cancelled_inspection_assignments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="inspectionassignment",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(normalize_inspection_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="inspectionassignment",
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
        migrations.AlterField(
            model_name="inspection",
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
