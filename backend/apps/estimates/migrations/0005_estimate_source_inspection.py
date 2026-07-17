import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("estimates", "0004_estimate_public_review_flow"),
        ("inspections", "0007_inspection_assignment_audit_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="estimate",
            name="id_inspection_assignment",
            field=models.ForeignKey(
                blank=True,
                db_column="id_inspection_assignment",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="estimates",
                to="inspections.inspectionassignment",
            ),
        ),
    ]
