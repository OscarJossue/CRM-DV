from django.db import transaction
from django.utils import timezone

from apps.accounts.contractor_access import user_is_contractor_only
from apps.core.field_photos import MAX_FIELD_PHOTOS, optimize_field_photo
from apps.core.template_permissions import (
    PERMISSION_APPROVE,
    PERMISSION_EDIT,
    user_can_module_action,
)

from .models import Inspection, InspectionAssignment, InspectionAssignmentGalleryImage
from .models.choices import (
    INSPECTION_STATUS_CANCELLED,
    INSPECTION_STATUS_COMPLETED,
    INSPECTION_STATUS_IN_PROGRESS,
    INSPECTION_STATUS_REVIEW,
)


@transaction.atomic
def inspection_create(**data):
    inspection = Inspection(**data)
    inspection.full_clean()
    inspection.save()
    return inspection


@transaction.atomic
def inspection_update(inspection, **data):
    allowed_fields = [
        "id_project",
        "id_inspector",
        "inspection_date",
        "damage_description",
        "materials",
        "photos",
        "estimated_time",
        "status",
    ]
    for field in allowed_fields:
        if field in data:
            setattr(inspection, field, data[field])
    inspection.full_clean()
    inspection.save()
    return inspection


@transaction.atomic
def inspection_approve(inspection):
    inspection.status = INSPECTION_STATUS_COMPLETED
    inspection.save(update_fields=["status", "updated_at"])
    return inspection


def user_can_submit_inspection_work(user, assignment):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not getattr(user, "id_company_id", None):
        return False
    if assignment.id_company_id != user.id_company_id:
        return False
    if user_can_module_action(user, "inspections", PERMISSION_EDIT):
        return True
    return user_is_contractor_only(user) and assignment.inspector_id == user.pk


def user_can_review_inspection(user, assignment):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return (
        getattr(user, "id_company_id", None) == assignment.id_company_id
        and user_can_module_action(user, "inspections", PERMISSION_APPROVE)
    )


def inspection_has_field_submission(assignment):
    annotated = getattr(assignment, "has_field_evidence", None)
    if annotated is not None:
        return bool(annotated or assignment.submitted_for_audit_at)
    return bool(
        assignment.submitted_for_audit_at
        or assignment.gallery_images.exclude(file="").exists()
    )


def inspection_assignment_submission_requirements(assignment, user=None):
    has_photo = assignment.gallery_images.exclude(file="").exists()
    has_note = bool((assignment.inspection_notes or "").strip())
    return {"has_photo": has_photo, "has_note": has_note, "ready": has_photo}


@transaction.atomic
def submit_inspection_assignment_for_review(
    assignment,
    user,
    *,
    notes=None,
    recommendations=None,
    uploads=None,
):
    assignment = InspectionAssignment.objects.select_for_update().get(pk=assignment.pk)
    if not user_can_submit_inspection_work(user, assignment):
        raise PermissionError("You do not have permission to submit this inspection.")
    if assignment.status in {INSPECTION_STATUS_COMPLETED, INSPECTION_STATUS_CANCELLED}:
        raise ValueError("Approved or cancelled inspections are locked.")
    if assignment.status == INSPECTION_STATUS_REVIEW:
        raise ValueError("This inspection is already under review.")

    uploads = list(uploads or [])
    existing_count = assignment.gallery_images.exclude(file="").count()
    remaining = max(0, MAX_FIELD_PHOTOS - existing_count)
    if len(uploads) > remaining:
        raise ValueError(f"You can add only {remaining} more photo(s).")
    if not assignment.gallery_images.exclude(file="").exists() and not uploads:
        raise ValueError("Add at least one inspection photo before submitting.")

    optimized_uploads = [
        {
            "file": optimize_field_photo(
                row["file"], prefix=f"inspection-{assignment.id_assignment}"
            ),
            "description": (row.get("description") or "").strip() or None,
        }
        for row in uploads
    ]

    if notes is not None:
        assignment.inspection_notes = (notes or "").strip()
    if recommendations is not None:
        assignment.recommendations = (recommendations or "").strip()

    for row in optimized_uploads:
        InspectionAssignmentGalleryImage.objects.create(
            assignment=assignment,
            category="after",
            file=row["file"],
            title=None,
            description=row["description"],
            uploaded_by=user,
        )

    assignment.status = INSPECTION_STATUS_REVIEW
    assignment.submitted_for_audit_at = timezone.now()
    assignment.audit_completed_at = None
    assignment.review_notes = None
    assignment.reviewed_by = None
    assignment.save(
        update_fields=[
            "inspection_notes",
            "recommendations",
            "status",
            "submitted_for_audit_at",
            "audit_completed_at",
            "review_notes",
            "reviewed_by",
            "updated_at",
        ]
    )
    return assignment


submit_inspection_assignment_for_audit = submit_inspection_assignment_for_review


@transaction.atomic
def approve_inspection_assignment(assignment, reviewer):
    assignment = InspectionAssignment.objects.select_for_update().get(pk=assignment.pk)
    if not user_can_review_inspection(reviewer, assignment):
        raise PermissionError("You do not have permission to approve this inspection.")
    if assignment.status != INSPECTION_STATUS_REVIEW:
        raise ValueError("Only an inspection under review can be approved.")
    if not assignment.gallery_images.exclude(file="").exists():
        raise ValueError("The inspection needs at least one photo before approval.")

    assignment.status = INSPECTION_STATUS_COMPLETED
    assignment.audit_completed_at = timezone.now()
    assignment.reviewed_by = reviewer
    assignment.review_notes = None
    assignment.save(
        update_fields=[
            "status",
            "audit_completed_at",
            "reviewed_by",
            "review_notes",
            "updated_at",
        ]
    )
    return assignment


@transaction.atomic
def close_inspection(assignment, user):
    """Close an inspection manually without requiring an audit submission."""
    assignment = InspectionAssignment.objects.select_for_update().get(pk=assignment.pk)
    if not user_can_review_inspection(user, assignment):
        raise PermissionError("You do not have permission to close this inspection.")
    if assignment.status == INSPECTION_STATUS_CANCELLED:
        raise ValueError("A cancelled inspection cannot be closed.")
    if assignment.status == INSPECTION_STATUS_COMPLETED:
        return assignment

    assignment.status = INSPECTION_STATUS_COMPLETED
    assignment.audit_completed_at = timezone.now()
    assignment.reviewed_by = user
    assignment.save(
        update_fields=[
            "status",
            "audit_completed_at",
            "reviewed_by",
            "updated_at",
        ]
    )
    return assignment


@transaction.atomic
def request_inspection_corrections(assignment, reviewer, reason):
    assignment = InspectionAssignment.objects.select_for_update().get(pk=assignment.pk)
    if not user_can_review_inspection(reviewer, assignment):
        raise PermissionError("You do not have permission to review this inspection.")
    if assignment.status != INSPECTION_STATUS_REVIEW:
        raise ValueError("Corrections can only be requested while the inspection is under review.")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Write the correction reason.")

    assignment.status = INSPECTION_STATUS_IN_PROGRESS
    assignment.review_notes = reason
    assignment.reviewed_by = reviewer
    # Preserve the last submitted timestamp for the contractor and audit trail.
    assignment.audit_completed_at = None
    assignment.save(
        update_fields=[
            "status",
            "review_notes",
            "reviewed_by",
            "audit_completed_at",
            "updated_at",
        ]
    )
    return assignment


@transaction.atomic
def cancel_inspection(assignment, user, reason):
    assignment = InspectionAssignment.objects.select_for_update().get(pk=assignment.pk)
    if not user_can_review_inspection(user, assignment):
        raise PermissionError("You do not have permission to cancel this inspection.")
    if assignment.status == INSPECTION_STATUS_CANCELLED:
        raise ValueError("This inspection is already cancelled.")
    if not inspection_has_field_submission(assignment):
        raise ValueError("This inspection has no field submission yet. Delete it instead.")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Write the cancellation reason.")

    assignment.status = INSPECTION_STATUS_CANCELLED
    assignment.cancellation_reason = reason
    assignment.cancelled_by = user
    assignment.cancelled_at = timezone.now()
    assignment.save(
        update_fields=[
            "status",
            "cancellation_reason",
            "cancelled_by",
            "cancelled_at",
            "updated_at",
        ]
    )
    return assignment


cancel_approved_inspection = cancel_inspection
