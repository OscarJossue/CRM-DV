from datetime import date

import django.db.models.deletion
from django.db import migrations, models


def populate_required_event_fields(apps, schema_editor):
    CalendarEvent = apps.get_model("calendar_events", "CalendarEvent")
    CalendarEvent.objects.filter(title__isnull=True).update(title="Calendar event")
    CalendarEvent.objects.filter(event_date__isnull=True).update(event_date=date.today())



class Migration(migrations.Migration):

    dependencies = [
        ("calendar_events", "0001_initial"),
        ("clients", "0005_normalize_client_code_format"),
        ("estimates", "0004_estimate_public_review_flow"),
        ("inspections", "0006_inspectionassignment_inspection_notes"),
        ("invoices", "0004_invoice_client_billing_dni"),
        ("opportunities", "0003_normalize_opportunity_code_format"),
        ("payments", "0004_alter_payment_amount"),
    ]

    operations = [
        migrations.RunPython(
            populate_required_event_fields,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="calendarevent",
            name="title",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name="calendarevent",
            name="event_date",
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name="calendarevent",
            name="status",
            field=models.CharField(
                choices=[
                    ("scheduled", "Scheduled"),
                    ("in_progress", "In Progress"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                default="scheduled",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="category",
            field=models.CharField(
                choices=[
                    ("task", "Task"),
                    ("appointment", "Appointment"),
                    ("meeting", "Meeting"),
                    ("call", "Call"),
                    ("follow_up", "Follow-up"),
                    ("deadline", "Deadline"),
                    ("reminder", "Reminder"),
                    ("other", "Other"),
                ],
                default="task",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="priority",
            field=models.CharField(
                choices=[
                    ("low", "Low"),
                    ("normal", "Normal"),
                    ("high", "High"),
                    ("urgent", "Urgent"),
                ],
                default="normal",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="related_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "No linked record"),
                    ("project", "Project"),
                    ("inspection", "Inspection"),
                    ("estimate", "Estimate"),
                    ("invoice", "Invoice"),
                    ("payment", "Payment"),
                    ("client", "Client"),
                    ("opportunity", "Opportunity"),
                ],
                default="",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="id_client",
            field=models.ForeignKey(
                blank=True,
                db_column="id_client",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calendar_events",
                to="clients.client",
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="id_estimate",
            field=models.ForeignKey(
                blank=True,
                db_column="id_estimate",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calendar_events",
                to="estimates.estimate",
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="id_inspection_assignment",
            field=models.ForeignKey(
                blank=True,
                db_column="id_inspection_assignment",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calendar_events",
                to="inspections.inspectionassignment",
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="id_invoice",
            field=models.ForeignKey(
                blank=True,
                db_column="id_invoice",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calendar_events",
                to="invoices.invoice",
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="id_opportunity",
            field=models.ForeignKey(
                blank=True,
                db_column="id_opportunity",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calendar_events",
                to="opportunities.lead",
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="id_payment",
            field=models.ForeignKey(
                blank=True,
                db_column="id_payment",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="calendar_events",
                to="payments.payment",
            ),
        ),
        migrations.AddIndex(
            model_name="calendarevent",
            index=models.Index(
                fields=["id_company", "event_date"],
                name="calendar_company_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="calendarevent",
            index=models.Index(
                fields=["id_assigned_user", "status"],
                name="calendar_assignee_status_idx",
            ),
        ),
        migrations.AlterModelOptions(
            name="calendarevent",
            options={"ordering": ["event_date", "start_time", "title"]},
        ),
    ]
