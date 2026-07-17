# backend/apps/user_activities/selectors.py

from apps.projects.models import Project, ProjectAssignment
from apps.inspections.models import Inspection, InspectionAssignment
from datetime import datetime
from django.utils import timezone

PENDING_STATUSES = [
    "pending",
    "assigned",
    "scheduled",
    "in_progress",
    "on_hold",
]

COMPLETED_STATUSES = [
    "completed",
    "done",
    "approved",
    "completed_inspection",
]


MANAGEMENT_ROLE_KEYWORDS = [
    "owner",
    "admin",
    "administrator",
    "secretary",
    "manager",
    "supervisor",
]


def _get_user_role_name(user):
    role = getattr(user, "role", None)

    if not role:
        role = getattr(user, "id_role", None)

    if not role:
        return ""

    return (
        getattr(role, "name", "")
        or getattr(role, "role_name", "")
        or str(role)
    ).strip().lower()


def _user_can_see_company_activities(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    role_name = _get_user_role_name(user)

    return any(
        keyword in role_name
        for keyword in MANAGEMENT_ROLE_KEYWORDS
    )


def _build_detail_url(company_slug, module_name, object_id):
    if company_slug:
        return f"/{company_slug}/{module_name}/{object_id}/"

    return f"/{module_name}/{object_id}/"
def _build_assignment_detail_url(company_slug, assignment_id):
    if company_slug:
        return f"/{company_slug}/inspections/{assignment_id}/"

    return f"/inspections/{assignment_id}/"


def get_user_activities(user, company_slug=None):
    activities = []

    projects = (
        Project.objects.select_related(
            "id_company",
            "id_client",
            "id_inspector",
        )
        .all()
        .order_by("-created_at")
    )

    project_assignments = (
        ProjectAssignment.objects.select_related(
            "id_project",
            "id_project__id_company",
            "id_project__id_client",
            "id_user",
        )
        .all()
        .order_by("-assigned_at")
    )

    inspections = (
        Inspection.objects.select_related(
            "id_project",
            "id_project__id_company",
            "id_project__id_client",
            "id_inspector",
        )
        .all()
        .order_by("-inspection_date")
    )

    inspection_assignments = (
        InspectionAssignment.objects.select_related(
            "client",
            "client__id_company",
            "inspector",
            "inspector__id_company",
        )
        .all()
        .order_by("-inspection_date", "-created_at")
    )

    can_see_company_activities = _user_can_see_company_activities(user)

    if not user.is_superuser:
        if not getattr(user, "id_company_id", None):
            return []

        projects = projects.filter(
            id_company_id=user.id_company_id,
        )

        project_assignments = project_assignments.filter(
            id_project__id_company_id=user.id_company_id,
        )

        inspections = inspections.filter(
            id_project__id_company_id=user.id_company_id,
        )

        inspection_assignments = inspection_assignments.filter(
            client__id_company_id=user.id_company_id,
        )

        if not can_see_company_activities:
            projects = projects.filter(
                id_inspector=user,
            )

            project_assignments = project_assignments.filter(
                id_user=user,
            )

            inspections = inspections.filter(
                id_inspector=user,
            )

            inspection_assignments = inspection_assignments.filter(
                inspector=user,
            )

    for project in projects:
        activities.append({
            "type": "Project",
            "code": project.project_code or f"P_{project.id_project:05d}",
            "title": project.project_name,
            "client": project.id_client,
            "status": project.status,
            "user": (
                project.id_inspector.email
                if project.id_inspector
                else "Unassigned"
            ),
            "created_at": project.created_at,
            "detail_url": _build_detail_url(
                company_slug,
                "projects",
                project.id_project,
            ),
        })

    for assignment in project_assignments:
        project = assignment.id_project

        if not project:
            continue

        activities.append({
            "type": "Project",
            "code": project.project_code or f"P_{project.id_project:05d}",
            "title": f"Assigned Project: {project.project_name}",
            "client": project.id_client,
            "status": assignment.status,
            "user": (
                assignment.id_user.email
                if assignment.id_user
                else "Unassigned"
            ),
            "created_at": assignment.assigned_at or project.created_at,
            "detail_url": _build_detail_url(
                company_slug,
                "projects",
                project.id_project,
            ),
        })

    for inspection in inspections:
        activities.append({
            "type": "Inspection",
            "code": (
                getattr(
                    inspection,
                    "inspection_code",
                    f"I_{inspection.id_inspection:05d}",
                )
            ),
            "title": "Inspection",
            "client": (
                inspection.id_project.id_client
                if inspection.id_project
                else None
            ),
            "status": inspection.status,
            "user": (
                inspection.id_inspector.email
                if inspection.id_inspector
                else "Unassigned"
            ),
            "created_at": inspection.inspection_date,
            "detail_url": _build_detail_url(
                company_slug,
                "inspections",
                inspection.id_inspection,
            ),
        })

    for assignment in inspection_assignments:
        activities.append({
            "type": "Inspection",
            "code": f"IA_{assignment.id_assignment:05d}",
            "title": "Inspection",
            "client": assignment.client,
            "status": assignment.status,
            "user": (
                assignment.inspector.email
                if assignment.inspector
                else "Unassigned"
            ),
            "created_at": assignment.inspection_date or assignment.created_at,
            "detail_url": _build_assignment_detail_url(
                company_slug,
                assignment.id_assignment,
            ),
        })

    fallback_date = timezone.make_aware(datetime.min)

    activities.sort(
        key=lambda item: item.get("created_at") or fallback_date,
        reverse=True,
    )

    return activities



def get_user_activities_dashboard(user, company_slug=None):
    activities = get_user_activities(
        user=user,
        company_slug=company_slug,
    )

    pending = [
        item for item in activities
        if item["status"] in PENDING_STATUSES
    ]

    completed = [
        item for item in activities
        if item["status"] in COMPLETED_STATUSES
    ]

    in_progress = [
        item for item in activities
        if item["status"] == "in_progress"
    ]

    project_activities = [
        item for item in activities
        if item["type"] == "Project"
    ]

    inspection_activities = [
        item for item in activities
        if item["type"] == "Inspection"
    ]

    recent_notifications = pending[:8]
    recent_completed = completed[:8]

    return {
        "activities": activities,
        "pending": pending,
        "completed": completed,
        "in_progress": in_progress,
        "project_activities": project_activities,
        "inspection_activities": inspection_activities,
        "recent_notifications": recent_notifications,
        "recent_completed": recent_completed,
        "total": len(activities),
        "pending_count": len(pending),
        "completed_count": len(completed),
        "in_progress_count": len(in_progress),
        "project_count": len(project_activities),
        "inspection_count": len(inspection_activities),
    }