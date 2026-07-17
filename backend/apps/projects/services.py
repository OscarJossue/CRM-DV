from django.db import transaction
from django.utils import timezone

from apps.accounts.contractor_access import user_is_contractor_only
from apps.core.field_photos import MAX_FIELD_PHOTOS, optimize_field_photo
from apps.core.template_permissions import (
    PERMISSION_APPROVE,
    PERMISSION_EDIT,
    user_can_module_action,
)

from .models import (
    Project,
    ProjectAssignment,
    ProjectEvidence,
    ProjectGalleryImage,
    ProjectNote,
)
from .models.choices import (
    PROJECT_STATUS_CANCELLED,
    PROJECT_STATUS_COMPLETED,
    PROJECT_STATUS_IN_PROGRESS,
    PROJECT_STATUS_REVIEW,
)


@transaction.atomic
def project_create(**data):
    project = Project(**data)
    project.full_clean()
    project.save()
    return project


@transaction.atomic
def project_update(project, **data):
    allowed_fields = [
        "id_company",
        "id_client",
        "id_opportunity",
        "id_inspector",
        "invoice_status",
        "name",
        "project_address",
        "google_maps_url",
        "description",
        "project_notes",
        "contractor_observations",
        "contractor_recommendations",
        "status",
        "progress",
        "contract_amount",
        "start_date",
        "end_date",
        "created_by",
        "updated_by",
    ]
    for field in allowed_fields:
        if field in data:
            setattr(project, field, data[field])
    project.full_clean()
    project.save()
    return project


@transaction.atomic
def project_assignment_create(**data):
    assignment = ProjectAssignment(**data)
    assignment.full_clean()
    assignment.save()
    return assignment


@transaction.atomic
def project_assignment_update(assignment, **data):
    allowed_fields = ["id_project", "id_user", "task", "progress", "status"]
    for field in allowed_fields:
        if field in data:
            setattr(assignment, field, data[field])
    assignment.full_clean()
    assignment.save()
    return assignment


def user_is_assigned_to_project(user, project):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return (
        project.id_inspector_id == getattr(user, "pk", None)
        or ProjectAssignment.objects.filter(id_project=project, id_user=user).exists()
    )


def user_can_submit_project_work(user, project):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not getattr(user, "id_company_id", None) or project.id_company_id != user.id_company_id:
        return False
    if user_can_module_action(user, "projects", PERMISSION_EDIT):
        return True
    return user_is_contractor_only(user) and user_is_assigned_to_project(user, project)


def user_can_review_project(user, project):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return (
        getattr(user, "id_company_id", None) == project.id_company_id
        and user_can_module_action(user, "projects", PERMISSION_APPROVE)
    )


def project_has_field_submission(project):
    """True after the contractor has created any project evidence.

    This remains true after corrections are requested, so a record can never
    become deletable again after its first field submission.
    """
    annotated = getattr(project, "has_field_evidence", None)
    if annotated is not None:
        return bool(annotated or project.submitted_for_audit_at)
    return bool(
        project.submitted_for_audit_at
        or ProjectEvidence.objects.filter(id_project=project).exclude(file="").exists()
        or ProjectGalleryImage.objects.filter(project=project).exclude(image="").exists()
    )


def project_submission_requirements(project, user=None):
    has_photo = (
        ProjectEvidence.objects.filter(id_project=project).exclude(file="").exists()
        or ProjectGalleryImage.objects.filter(project=project).exclude(image="").exists()
    )
    has_note = bool((project.contractor_observations or "").strip()) or ProjectNote.objects.filter(
        id_project=project
    ).exclude(note="").exists()
    return {"has_photo": has_photo, "has_note": has_note, "ready": has_photo}


@transaction.atomic
def submit_project_for_review(
    project,
    user,
    *,
    observations=None,
    recommendations=None,
    uploads=None,
):
    project = Project.objects.select_for_update().get(pk=project.pk)
    if not user_can_submit_project_work(user, project):
        raise PermissionError("You do not have permission to submit this project.")
    if project.status in {PROJECT_STATUS_COMPLETED, PROJECT_STATUS_CANCELLED}:
        raise ValueError("Closed or cancelled projects are locked.")
    if project.status == PROJECT_STATUS_REVIEW:
        raise ValueError("This project is already under review.")

    uploads = list(uploads or [])
    existing_count = (
        ProjectEvidence.objects.filter(id_project=project).exclude(file="").count()
        + ProjectGalleryImage.objects.filter(project=project).exclude(image="").count()
    )
    remaining = max(0, MAX_FIELD_PHOTOS - existing_count)
    if len(uploads) > remaining:
        raise ValueError(f"You can add only {remaining} more photo(s).")
    has_existing_photo = (
        ProjectEvidence.objects.filter(id_project=project).exclude(file="").exists()
        or ProjectGalleryImage.objects.filter(project=project).exclude(image="").exists()
    )
    if not has_existing_photo and not uploads:
        raise ValueError("Add at least one project photo before submitting.")

    optimized_uploads = [
        {
            "file": optimize_field_photo(
                row["file"], prefix=f"project-{project.id_project}"
            ),
            "description": (row.get("description") or "").strip() or None,
        }
        for row in uploads
    ]

    if observations is not None:
        project.contractor_observations = (observations or "").strip()
    if recommendations is not None:
        project.contractor_recommendations = (recommendations or "").strip()

    for row in optimized_uploads:
        ProjectEvidence.objects.create(
            id_project=project,
            title=None,
            file=row["file"],
            description=row["description"],
            uploaded_by=user,
        )

    project.status = PROJECT_STATUS_REVIEW
    project.submitted_for_audit_at = timezone.now()
    project.audit_completed_at = None
    project.review_notes = None
    project.reviewed_by = None
    project.updated_by = user
    project.save(
        update_fields=[
            "contractor_observations",
            "contractor_recommendations",
            "status",
            "submitted_for_audit_at",
            "audit_completed_at",
            "review_notes",
            "reviewed_by",
            "updated_by",
            "updated_at",
        ]
    )
    return project


submit_project_for_audit = submit_project_for_review


@transaction.atomic
def approve_project(project, reviewer):
    """Approve the submitted evidence and close the project in one action."""
    project = Project.objects.select_for_update().get(pk=project.pk)
    if not user_can_review_project(reviewer, project):
        raise PermissionError("You do not have permission to approve this project.")
    if project.status != PROJECT_STATUS_REVIEW:
        raise ValueError("Only a project under review can be approved and closed.")
    requirements = project_submission_requirements(project)
    if not requirements["has_photo"]:
        raise ValueError("The project needs at least one photo before approval.")

    project.status = PROJECT_STATUS_COMPLETED
    project.progress = 100
    project.end_date = timezone.localdate()
    project.audit_completed_at = timezone.now()
    project.reviewed_by = reviewer
    project.review_notes = None
    project.updated_by = reviewer
    project.save(
        update_fields=[
            "status",
            "progress",
            "end_date",
            "audit_completed_at",
            "reviewed_by",
            "review_notes",
            "updated_by",
            "updated_at",
        ]
    )
    ProjectAssignment.objects.filter(id_project=project).update(
        status="completed", progress=100
    )
    return project


@transaction.atomic
def close_project(project, user):
    """Close a project manually from the administrator workflow.

    Manual closure is intentionally separate from audit approval: an authorized
    administrator can freeze a project at any stage without fabricating contractor
    evidence. The final date and progress are always normalized.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    if not user_can_review_project(user, project):
        raise PermissionError("You do not have permission to close this project.")
    if project.status == PROJECT_STATUS_CANCELLED:
        raise ValueError("A cancelled project cannot be closed.")
    if project.status == PROJECT_STATUS_COMPLETED:
        return project

    project.status = PROJECT_STATUS_COMPLETED
    project.progress = 100
    project.end_date = timezone.localdate()
    project.audit_completed_at = timezone.now()
    project.reviewed_by = user
    project.updated_by = user
    project.save(
        update_fields=[
            "status",
            "progress",
            "end_date",
            "audit_completed_at",
            "reviewed_by",
            "updated_by",
            "updated_at",
        ]
    )
    ProjectAssignment.objects.filter(id_project=project).update(
        status="completed", progress=100
    )
    return project


@transaction.atomic
def request_project_corrections(project, reviewer, reason):
    project = Project.objects.select_for_update().get(pk=project.pk)
    if not user_can_review_project(reviewer, project):
        raise PermissionError("You do not have permission to review this project.")
    if project.status != PROJECT_STATUS_REVIEW:
        raise ValueError("Corrections can only be requested while the project is under review.")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Write the correction reason.")

    project.status = PROJECT_STATUS_IN_PROGRESS
    project.review_notes = reason
    project.reviewed_by = reviewer
    # Keep submitted_for_audit_at as the immutable last-submission timestamp.
    project.audit_completed_at = None
    project.updated_by = reviewer
    project.save(
        update_fields=[
            "status",
            "review_notes",
            "reviewed_by",
            "audit_completed_at",
            "updated_by",
            "updated_at",
        ]
    )
    ProjectAssignment.objects.filter(id_project=project).update(status="in_progress")
    return project


@transaction.atomic
def cancel_project(project, user, reason):
    project = Project.objects.select_for_update().get(pk=project.pk)
    if not user_can_review_project(user, project):
        raise PermissionError("You do not have permission to cancel this project.")
    if project.status == PROJECT_STATUS_CANCELLED:
        raise ValueError("This project is already cancelled.")
    if not project_has_field_submission(project):
        raise ValueError("This project has no field submission yet. Delete it instead.")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Write the cancellation reason.")

    project.status = PROJECT_STATUS_CANCELLED
    project.cancellation_reason = reason
    project.cancelled_by = user
    project.cancelled_at = timezone.now()
    project.updated_by = user
    project.save(
        update_fields=[
            "status",
            "cancellation_reason",
            "cancelled_by",
            "cancelled_at",
            "updated_by",
            "updated_at",
        ]
    )
    ProjectAssignment.objects.filter(id_project=project).update(status="cancelled")
    return project


# Backward-compatible import used by older routes/tests.
cancel_approved_project = cancel_project


def create_projects(**data):
    return project_create(**data)


def update_projects(instance, **data):
    return project_update(instance, **data)
