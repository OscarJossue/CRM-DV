import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("supervision", "0001_initial"),
        ("inspections", "0007_inspection_assignment_audit_workflow"),
        ("projects", "0005_project_audit_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="supervision",
            name="id_project",
            field=models.ForeignKey(
                blank=True,
                db_column="id_project",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="supervisions",
                to="projects.project",
            ),
        ),
        migrations.AlterField(
            model_name="supervision",
            name="id_supervisor",
            field=models.ForeignKey(
                blank=True,
                db_column="id_supervisor",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="supervisions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="supervision",
            name="id_inspection_assignment",
            field=models.ForeignKey(
                blank=True,
                db_column="id_inspection_assignment",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="supervisions",
                to="inspections.inspectionassignment",
            ),
        ),
        migrations.AddField(
            model_name="supervision",
            name="rejected",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="supervision",
            name="rejection_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="supervision",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddIndex(
            model_name="supervision",
            index=models.Index(
                fields=["approved", "final_audit", "rejected"],
                name="supervision_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="supervision",
            index=models.Index(fields=["id_supervisor"], name="supervision_supervisor_idx"),
        ),
        migrations.AddConstraint(
            model_name="supervision",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(id_project__isnull=False, id_inspection_assignment__isnull=True)
                    | models.Q(id_project__isnull=True, id_inspection_assignment__isnull=False)
                ),
                name="supervision_exactly_one_target_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="supervision",
            constraint=models.CheckConstraint(
                condition=~models.Q(approved=True, rejected=True),
                name="supervision_not_approved_and_rejected_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="supervision",
            constraint=models.CheckConstraint(
                condition=models.Q(final_audit=False)
                | models.Q(approved=True, rejected=False),
                name="supervision_final_requires_approved_ck",
            ),
        ),
    ]
