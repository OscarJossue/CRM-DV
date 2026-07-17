# Generated manually for Google Ads / Google Guaranteed leads inbox.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0001_initial"),
        ("leads", "0001_initial"),
        ("integrations", "0003_encrypted_company_google_credentials"),
    ]

    operations = [
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="lead_webhook_key_payload",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="auto_create_crm_leads",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="auto_create_crm_leads_from_lsa",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="auto_reply_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="auto_reply_message",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="googleintegrationconnection",
            name="last_ads_lead_sync_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="integrationlog",
            name="tool",
            field=models.CharField(choices=[("calendar", "Calendar / Meet"), ("drive", "Google Drive"), ("sheets", "Google Sheets"), ("analytics", "Google Analytics"), ("ads", "Google Ads"), ("ads_leads", "Google Ads / LSA Leads"), ("oauth", "Google Connection")], db_index=True, default="oauth", max_length=40),
        ),
        migrations.CreateModel(
            name="GoogleAdsLead",
            fields=[
                ("id_ads_lead", models.BigAutoField(primary_key=True, serialize=False)),
                ("source", models.CharField(choices=[("google_ads_webhook", "Google Ads Lead Form Webhook"), ("google_local_services", "Google Guaranteed / Local Services Ads"), ("google_lead_form_api", "Google Ads Lead Form API")], db_index=True, default="google_ads_webhook", max_length=60)),
                ("external_lead_id", models.CharField(blank=True, max_length=120, null=True)),
                ("external_resource_name", models.CharField(blank=True, max_length=255, null=True)),
                ("customer_id", models.CharField(blank=True, max_length=40, null=True)),
                ("campaign_id", models.CharField(blank=True, max_length=80, null=True)),
                ("adgroup_id", models.CharField(blank=True, max_length=80, null=True)),
                ("form_id", models.CharField(blank=True, max_length=80, null=True)),
                ("gcl_id", models.CharField(blank=True, max_length=160, null=True)),
                ("lead_type", models.CharField(blank=True, max_length=60, null=True)),
                ("lead_status", models.CharField(blank=True, max_length=60, null=True)),
                ("crm_status", models.CharField(choices=[("new", "New"), ("contacted", "Contacted"), ("booked", "Booked"), ("lost", "Lost"), ("archived", "Archived")], db_index=True, default="new", max_length=40)),
                ("category_id", models.CharField(blank=True, max_length=160, null=True)),
                ("customer_name", models.CharField(blank=True, max_length=180, null=True)),
                ("phone", models.CharField(blank=True, max_length=60, null=True)),
                ("email", models.EmailField(blank=True, max_length=180, null=True)),
                ("address", models.TextField(blank=True, null=True)),
                ("city", models.CharField(blank=True, max_length=100, null=True)),
                ("state", models.CharField(blank=True, max_length=100, null=True)),
                ("postal_code", models.CharField(blank=True, max_length=40, null=True)),
                ("country", models.CharField(blank=True, max_length=100, null=True)),
                ("service_interest", models.CharField(blank=True, max_length=180, null=True)),
                ("message", models.TextField(blank=True, null=True)),
                ("conversation_text", models.TextField(blank=True, null=True)),
                ("last_reply_message", models.TextField(blank=True, null=True)),
                ("last_reply_at", models.DateTimeField(blank=True, null=True)),
                ("lead_charged", models.BooleanField(default=False)),
                ("lead_feedback_submitted", models.BooleanField(default=False)),
                ("is_test", models.BooleanField(default=False)),
                ("received_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("synced_at", models.DateTimeField(blank=True, null=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("raw_conversations", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("connection", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ads_leads", to="integrations.googleintegrationconnection")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_google_ads_leads", to=settings.AUTH_USER_MODEL)),
                ("crm_lead", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="google_ads_sources", to="leads.lead")),
                ("id_company", models.ForeignKey(db_column="id_company", on_delete=django.db.models.deletion.CASCADE, related_name="google_ads_leads", to="companies.company")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_google_ads_leads", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "integration_google_ads_lead",
                "ordering": ["-received_at", "-created_at"],
                "indexes": [
                    models.Index(fields=["id_company", "source"], name="gads_lead_company_src_idx"),
                    models.Index(fields=["id_company", "crm_status"], name="gads_lead_company_stat_idx"),
                    models.Index(fields=["external_resource_name"], name="gads_lead_resource_idx"),
                ],
                "constraints": [models.UniqueConstraint(fields=("id_company", "source", "external_lead_id"), name="uniq_google_lead_ext")],
            },
        ),
        migrations.CreateModel(
            name="GoogleAdsLeadReply",
            fields=[
                ("id_reply", models.BigAutoField(primary_key=True, serialize=False)),
                ("channel", models.CharField(choices=[("crm_note", "CRM Note"), ("email", "Email"), ("phone", "Phone Call"), ("whatsapp", "WhatsApp"), ("google_message", "Google Message")], db_index=True, default="crm_note", max_length=40)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("logged", "Logged in CRM"), ("sent", "Sent"), ("error", "Error")], db_index=True, default="logged", max_length=30)),
                ("subject", models.CharField(blank=True, max_length=220, null=True)),
                ("message", models.TextField()),
                ("external_response_id", models.CharField(blank=True, max_length=255, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("ads_lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="integrations.googleadslead")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("id_company", models.ForeignKey(db_column="id_company", on_delete=django.db.models.deletion.CASCADE, related_name="google_ads_lead_replies", to="companies.company")),
            ],
            options={
                "db_table": "integration_google_ads_lead_reply",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["id_company", "channel"], name="gads_reply_company_chan_idx"),
                    models.Index(fields=["status"], name="gads_reply_status_idx"),
                ],
            },
        ),
    ]
