from django.db import migrations, models


def encrypt_existing_plaintext_tokens(apps, schema_editor):
    try:
        from apps.integrations.services.security import encrypt_text
    except Exception:
        return
    Connection = apps.get_model("integrations", "GoogleIntegrationConnection")
    for connection in Connection.objects.exclude(developer_token__isnull=True).exclude(developer_token=""):
        try:
            connection.developer_token_payload = encrypt_text(connection.developer_token)
            connection.developer_token = ""
            connection.save(update_fields=["developer_token_payload", "developer_token"])
        except Exception:
            # Keep migration safe; the runtime model can still read the legacy plaintext fallback.
            continue


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0002_alter_googledriveupload_file_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="oauth_client_id_payload",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="oauth_client_secret_payload",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="developer_token_payload",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(encrypt_existing_plaintext_tokens, migrations.RunPython.noop),
    ]
