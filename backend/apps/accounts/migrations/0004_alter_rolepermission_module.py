# Generated manually for merged SaaS + company CRM account modules

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_rolepermission_module"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rolepermission",
            name="module",
            field=models.CharField(
                max_length=100,
                choices=[
                    ("dashboard", "Dashboard"),
                    ("companies", "Companies"),
                    ("company_modules", "Company Modules"),
                    ("roles", "Roles"),
                    ("users", "Users"),
                    ("employees", "Employees"),
                    ("notifications", "Notifications"),
                    ("system_logs", "System Logs"),
                    ("clients", "Clients"),
                    ("leads", "Leads"),
                    ("opportunities", "Opportunities"),
                    ("projects", "Projects"),
                    ("inspections", "Inspections"),
                    ("estimates", "Estimates"),
                    ("invoices", "Invoices"),
                    ("payments", "Payments"),
                    ("contracts", "Contracts"),
                    ("evidence", "Evidence"),
                    ("supervision", "Supervision"),
                    ("calendar_events", "Calendar Events"),
                    ("reports", "Reports"),
                    ("smtp_settings", "SMTP Settings"),
                    ("platform_dashboard", "Platform Dashboard"),
                    ("platform_companies", "Platform Companies"),
                    ("platform_plans", "Platform Plans"),
                    ("platform_subscriptions", "Platform Subscriptions"),
                    ("platform_documents", "Platform Documents"),
                    ("platform_payments", "Platform Payments"),
                    ("platform_calendar", "Platform Calendar"),
                    ("platform_email", "Platform Email"),
                    ("platform_notifications", "Platform Notifications"),
                    ("platform_audit", "Platform Audit"),
                    ("platform_metrics", "Platform Metrics"),
                    ("platform_system_monitor", "Platform System Monitor"),
                ],
            ),
        ),
    ]
