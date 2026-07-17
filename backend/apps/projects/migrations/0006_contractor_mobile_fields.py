from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0005_project_audit_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="contractor_observations",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="contractor_recommendations",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="google_maps_url",
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
    ]
