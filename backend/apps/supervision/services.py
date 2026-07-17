from django.db import transaction
from django.utils import timezone

from .models import Supervision


@transaction.atomic
def supervision_create(**data):
    supervision = Supervision(**data)
    supervision.full_clean()
    supervision.save()
    return supervision


@transaction.atomic
def supervision_update(supervision, **data):
    allowed_fields = [
        "id_project",
        "id_inspection_assignment",
        "id_supervisor",
        "observations",
        "approved",
        "rejected",
        "rejection_reason",
        "final_audit",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(supervision, field, data[field])

    supervision.full_clean()
    supervision.save()
    return supervision


def _reset_pending_audit(supervision, supervisor=None):
    supervision.id_supervisor = supervisor or supervision.id_supervisor
    supervision.approved = False
    supervision.rejected = False
    supervision.rejection_reason = ""
    supervision.final_audit = False
    supervision.save(
        update_fields=[
            "id_supervisor",
            "approved",
            "rejected",
            "rejection_reason",
            "final_audit",
            "updated_at",
        ]
    )
    return supervision


@transaction.atomic
def queue_project_for_audit(project, submitted_by=None):
    """Create or reopen the single active audit queue item for a project."""
    supervision = (
        Supervision.objects.select_for_update()
        .filter(id_project=project, final_audit=False)
        .order_by("-created_at")
        .first()
    )
    if supervision:
        return _reset_pending_audit(supervision)

    return supervision_create(id_project=project, id_supervisor=None)


@transaction.atomic
def queue_inspection_for_audit(assignment, submitted_by=None):
    """Create or reopen the single active audit queue item for an inspection assignment."""
    supervision = (
        Supervision.objects.select_for_update()
        .filter(id_inspection_assignment=assignment, final_audit=False)
        .order_by("-created_at")
        .first()
    )
    if supervision:
        return _reset_pending_audit(supervision)

    return supervision_create(id_inspection_assignment=assignment, id_supervisor=None)


@transaction.atomic
def supervision_approve(supervision):
    supervision.approved = True
    supervision.rejected = False
    supervision.rejection_reason = ""
    supervision.full_clean()
    supervision.save(
        update_fields=[
            "approved",
            "rejected",
            "rejection_reason",
            "updated_at",
        ]
    )
    return supervision


@transaction.atomic
def supervision_reject(supervision, reason=""):
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A rejection reason is required.")

    supervision.approved = False
    supervision.rejected = True
    supervision.final_audit = False
    supervision.rejection_reason = reason
    supervision.observations = reason
    supervision.full_clean()
    supervision.save(
        update_fields=[
            "approved",
            "rejected",
            "final_audit",
            "rejection_reason",
            "observations",
            "updated_at",
        ]
    )

    if supervision.id_project_id:
        project = supervision.id_project
        project.status = "in_progress"
        project.submitted_for_audit_at = None
        project.audit_completed_at = None
        project.save(
            update_fields=[
                "status",
                "submitted_for_audit_at",
                "audit_completed_at",
                "updated_at",
            ]
        )
    else:
        assignment = supervision.id_inspection_assignment
        assignment.status = "in_progress"
        assignment.submitted_for_audit_at = None
        assignment.audit_completed_at = None
        assignment.save(
            update_fields=[
                "status",
                "submitted_for_audit_at",
                "audit_completed_at",
                "updated_at",
            ]
        )

    return supervision


@transaction.atomic
def supervision_mark_final_audit(supervision):
    target = supervision.id_project or supervision.id_inspection_assignment
    if not target or target.status != "audit":
        raise ValueError("Only work currently waiting for audit can be completed.")

    supervision.approved = True
    supervision.rejected = False
    supervision.rejection_reason = ""
    supervision.final_audit = True
    supervision.full_clean()
    supervision.save(
        update_fields=[
            "approved",
            "rejected",
            "rejection_reason",
            "final_audit",
            "updated_at",
        ]
    )

    completed_at = timezone.now()
    if supervision.id_project_id:
        project = supervision.id_project
        project.status = "completed"
        project.audit_completed_at = completed_at
        project.progress = 100
        project.save(
            update_fields=[
                "status",
                "audit_completed_at",
                "progress",
                "updated_at",
            ]
        )
        project.assignments.exclude(status="cancelled").update(status="completed", progress=100)
    else:
        assignment = supervision.id_inspection_assignment
        assignment.status = "completed"
        assignment.audit_completed_at = completed_at
        assignment.save(
            update_fields=[
                "status",
                "audit_completed_at",
                "updated_at",
            ]
        )

    return supervision


def create_supervision(**data):
    return supervision_create(**data)


def update_supervision(instance, **data):
    return supervision_update(instance, **data)
