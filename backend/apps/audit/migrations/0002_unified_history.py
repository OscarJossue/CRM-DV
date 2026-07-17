import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="systemlog",
            options={"ordering": ["-created_at", "-id_log"]},
        ),
        migrations.AddField(
            model_name="systemlog",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("updated", "Updated"),
                    ("deleted", "Deleted"),
                    ("status_changed", "Status changed"),
                    ("voided", "Voided"),
                    ("cancelled", "Cancelled"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("sent", "Sent"),
                    ("file_uploaded", "File uploaded"),
                    ("payment_registered", "Payment registered"),
                    ("permissions_updated", "Permissions updated"),
                    ("login", "Signed in"),
                    ("logout", "Signed out"),
                    ("export", "Exported"),
                    ("system", "System event"),
                ],
                db_index=True,
                default="system",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="actor_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="actor_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="changes",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="object_id",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="object_label",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="object_type",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="request_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="result",
            field=models.CharField(
                choices=[("success", "Successful"), ("failure", "Failed")],
                default="success",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="severity",
            field=models.CharField(
                choices=[
                    ("info", "Information"),
                    ("warning", "Warning"),
                    ("critical", "Critical"),
                    ("security", "Security"),
                ],
                db_index=True,
                default="info",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="systemlog",
            name="user_agent",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="systemlog",
            name="action",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name="systemlog",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="systemlog",
            name="module",
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True),
        ),
        migrations.AddIndex(
            model_name="systemlog",
            index=models.Index(fields=["id_company", "-created_at"], name="slog_company_created_idx"),
        ),
        migrations.AddIndex(
            model_name="systemlog",
            index=models.Index(fields=["id_user", "-created_at"], name="slog_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="systemlog",
            index=models.Index(fields=["module", "-created_at"], name="slog_module_created_idx"),
        ),
        migrations.AddIndex(
            model_name="systemlog",
            index=models.Index(fields=["action_type", "-created_at"], name="slog_action_created_idx"),
        ),
    ]
