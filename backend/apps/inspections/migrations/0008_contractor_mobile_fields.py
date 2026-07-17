from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inspections", "0007_inspection_assignment_audit_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="inspectionassignment",
            name="google_maps_url",
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name="inspectionassignment",
            name="recommendations",
            field=models.TextField(blank=True, null=True),
        ),
    ]
