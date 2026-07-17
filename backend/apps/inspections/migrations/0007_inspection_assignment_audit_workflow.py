import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inspections", "0006_inspectionassignment_inspection_notes"),
        ("projects", "0005_project_audit_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="inspectionassignment",
            name="id_project",
            field=models.ForeignKey(
                blank=True,
                db_column="id_project",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="source_inspection_assignments",
                to="projects.project",
            ),
        ),
        migrations.AddField(
            model_name="inspectionassignment",
            name="submitted_for_audit_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inspectionassignment",
            name="audit_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="inspectionassignment",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("in_progress", "In Progress"),
                    ("audit", "Audit"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="inspection",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("in_progress", "In Progress"),
                    ("audit", "Audit"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=50,
            ),
        ),
    ]
