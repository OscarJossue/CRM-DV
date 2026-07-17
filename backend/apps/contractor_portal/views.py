from __future__ import annotations

from collections import Counter
from types import SimpleNamespace
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.contractor_access import user_is_contractor_only
from apps.core.field_photos import (
    MAX_FIELD_PHOTOS,
    collect_photo_slots,
    ensure_media_storage_ready,
)
from apps.inspections.models import InspectionAssignment, InspectionAssignmentGalleryImage
from apps.inspections.models.choices import INSPECTION_MANUAL_STATUS_VALUES
from apps.inspections.services import submit_inspection_assignment_for_review
from apps.projects.models import Project, ProjectAssignment, ProjectEvidence, ProjectGalleryImage
from apps.projects.models.choices import PROJECT_MANUAL_STATUS_VALUES
from apps.projects.services import submit_project_for_review


SUPPORTED_LANGUAGES = {"en", "es"}
LANGUAGE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
CONTRACTOR_VISIBLE_STATUSES = ("pending", "in_progress", "review", "completed")
PORTAL_STATUS_VALUES = CONTRACTOR_VISIBLE_STATUSES

PORTAL_TEXT = {
    "en": {
        "portal": "Field Work",
        "my_inspections": "My inspections",
        "my_projects": "My projects",
        "logout": "Log out",
        "language": "Language",
        "assigned_work": "Assigned field work",
        "inspection_empty": "You do not have assigned inspections.",
        "project_empty": "You do not have assigned projects.",
        "open": "Open",
        "location": "Location",
        "date": "Date",
        "instructions": "Instructions",
        "open_maps": "Open in Google Maps",
        "back_inspections": "Back to inspections",
        "back_projects": "Back to projects",
        "observations": "Observations",
        "recommendations": "Recommendations",
        "optional": "optional",
        "photos": "Photos",
        "photo_help": "Add up to five photos. Each image is converted to lightweight WebP.",
        "camera": "Camera",
        "gallery": "Gallery",
        "description": "Description",
        "description_optional": "Optional description",
        "add_photo": "Add another photo",
        "remove": "Remove",
        "submit_inspection": "Save and send inspection",
        "submit_project": "Save and send project",
        "sending": "Sending…",
        "submitted_photos": "Submitted photos",
        "no_description": "No description",
        "no_photos": "No photos submitted yet.",
        "review_locked": "This work was sent for review and is temporarily locked.",
        "approved_locked": "This work is approved and cannot be edited.",
        "void_locked": "This work is void and cannot be edited.",
        "corrections": "Corrections requested",
        "inspection_sent": "Inspection saved and sent for review.",
        "project_sent": "Project saved and sent for review.",
        "storage_error": "The photo storage is not available. Rebuild the containers so the media volume permissions are repaired.",
        "invalid_access": "This contractor portal is only available to contractor accounts.",
        "status_draft": "Draft",
        "status_pending": "Pending",
        "status_in_progress": "In progress",
        "status_review": "Under review",
        "status_completed": "Approved",
        "status_cancelled": "Void",
        "client": "Client",
        "contact": "Contact",
        "remaining": "available",
        "work_information": "Work information",
        "work_notes": "Work notes",
        "notes_help": "Add only the information needed to document the work.",
        "observations_placeholder": "What did you find or complete?",
        "recommendations_placeholder": "Optional recommendations for the office team",
        "ready_to_send": "Ready to send",
        "submit_help": "Your notes and photos will be sent together for review.",
        "no_file_selected": "No photo selected",
        "photo": "Work photo",
        "now": "Now",
        "scheduled_for": "Scheduled inspection",
        "sent_for_audit": "Last sent for audit",
        "approved_at": "Audit completed",
        "not_sent_yet": "Not sent yet",
        "filter_by_status": "Filter by status",
        "filter_all": "All",
        "filter_audit": "Audit",
        "start_date": "Start date",
        "end_date": "End date",
        "delete_photo": "Delete photo",
        "delete_photo_confirm": "Delete this photo? You can upload a replacement before sending the work for audit.",
        "photo_deleted": "Photo deleted. You can upload a replacement before sending the work for audit.",
        "photo_delete_forbidden": "This photo cannot be deleted after the work has been sent for audit.",
    },
    "es": {
        "portal": "Trabajo de campo",
        "my_inspections": "Mis inspecciones",
        "my_projects": "Mis proyectos",
        "logout": "Cerrar sesión",
        "language": "Idioma",
        "assigned_work": "Trabajos de campo asignados",
        "inspection_empty": "No tienes inspecciones asignadas.",
        "project_empty": "No tienes proyectos asignados.",
        "open": "Abrir",
        "location": "Ubicación",
        "date": "Fecha",
        "instructions": "Instrucciones",
        "open_maps": "Abrir en Google Maps",
        "back_inspections": "Volver a inspecciones",
        "back_projects": "Volver a proyectos",
        "observations": "Observaciones",
        "recommendations": "Recomendaciones",
        "optional": "opcional",
        "photos": "Fotos",
        "photo_help": "Agrega hasta cinco fotos. Cada imagen se convierte a WebP liviano.",
        "camera": "Cámara",
        "gallery": "Galería",
        "description": "Descripción",
        "description_optional": "Descripción opcional",
        "add_photo": "Agregar otra foto",
        "remove": "Quitar",
        "submit_inspection": "Guardar y enviar inspección",
        "submit_project": "Guardar y enviar proyecto",
        "sending": "Enviando…",
        "submitted_photos": "Fotos enviadas",
        "no_description": "Sin descripción",
        "no_photos": "Todavía no se han enviado fotos.",
        "review_locked": "Este trabajo fue enviado a revisión y está bloqueado temporalmente.",
        "approved_locked": "Este trabajo está aprobado y no se puede editar.",
        "void_locked": "Este trabajo está anulado y no se puede editar.",
        "corrections": "Correcciones solicitadas",
        "inspection_sent": "La inspección se guardó y se envió a revisión.",
        "project_sent": "El proyecto se guardó y se envió a revisión.",
        "storage_error": "El almacenamiento de fotos no está disponible. Reconstruye los contenedores para reparar los permisos del volumen media.",
        "invalid_access": "Este portal está disponible únicamente para cuentas de contratista.",
        "status_draft": "Borrador",
        "status_pending": "Pendiente",
        "status_in_progress": "En progreso",
        "status_review": "En revisión",
        "status_completed": "Aprobado",
        "status_cancelled": "Anulado",
        "client": "Cliente",
        "contact": "Contacto",
        "remaining": "disponibles",
        "work_information": "Información del trabajo",
        "work_notes": "Notas del trabajo",
        "notes_help": "Agrega únicamente la información necesaria para documentar el trabajo.",
        "observations_placeholder": "¿Qué encontraste o qué trabajo realizaste?",
        "recommendations_placeholder": "Recomendaciones opcionales para el equipo de oficina",
        "ready_to_send": "Listo para enviar",
        "submit_help": "Las notas y fotos se enviarán juntas para revisión.",
        "no_file_selected": "Ninguna foto seleccionada",
        "photo": "Foto del trabajo",
        "now": "Ahora",
        "scheduled_for": "Inspección programada",
        "sent_for_audit": "Último envío a auditoría",
        "approved_at": "Auditoría completada",
        "not_sent_yet": "Aún no enviada",
        "filter_by_status": "Filtrar por estado",
        "filter_all": "Todas",
        "filter_audit": "Auditoría",
        "start_date": "Fecha de inicio",
        "end_date": "Fecha final",
        "delete_photo": "Eliminar foto",
        "delete_photo_confirm": "¿Eliminar esta foto? Podrás subir otra antes de enviar el trabajo a auditoría.",
        "photo_deleted": "Foto eliminada. Puedes subir otra antes de enviar el trabajo a auditoría.",
        "photo_delete_forbidden": "Esta foto no se puede eliminar después de enviar el trabajo a auditoría.",
    },
}


def _normalise_language(value):
    language = (value or "").strip().lower().split("-")[0]
    return language if language in SUPPORTED_LANGUAGES else ""


def _language_for_request(request):
    # The portal language is personal to the contractor. The session/cookie
    # makes a switch visible immediately, while the account field keeps it on
    # future logins and other devices.
    session_language = _normalise_language(
        request.session.get("contractor_portal_language")
    )
    cookie_language = _normalise_language(
        request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    )
    user_language = _normalise_language(
        getattr(request.user, "preferred_language", "")
    )
    company = getattr(request.user, "id_company", None)
    company_language = _normalise_language(
        getattr(company, "default_language", "")
    )
    return session_language or cookie_language or user_language or company_language or "en"


def _labels(request):
    return PORTAL_TEXT[_language_for_request(request)]


def _portal_company(request, company_slug):
    if not user_is_contractor_only(request.user):
        return None
    company = getattr(request.user, "id_company", None)
    if not company or company.slug != company_slug:
        raise Http404("Company not found.")
    return company


def _guard(request, company_slug):
    company = _portal_company(request, company_slug)
    if company is None:
        labels = _labels(request)
        return None, HttpResponseForbidden(labels["invalid_access"])
    return company, None


def _url(name, company, **kwargs):
    return reverse(
        f"company_contractor_portal:{name}",
        kwargs={"company_slug": company.slug, **kwargs},
    )


def _base_context(request, company, active):
    labels = _labels(request)
    return {
        "company": company,
        "labels": labels,
        "portal_language": _language_for_request(request),
        "active_portal_tab": active,
        "portal_home_url": _url("home", company),
        "portal_inspection_list_url": _url("inspection_list", company),
        "portal_project_list_url": _url("project_list", company),
        "portal_language_url": _url("language", company),
    }


def _status_label(labels, status):
    return labels.get(f"status_{status}", str(status).replace("_", " ").title())


def _status_filter_options(labels, base_url, selected_status, counts):
    definitions = [
        ("pending", labels["status_pending"]),
        ("in_progress", labels["status_in_progress"]),
        ("review", labels["filter_audit"]),
        ("completed", labels["status_completed"]),
    ]
    return [
        SimpleNamespace(
            value=value,
            label=label,
            count=counts.get(value, 0),
            active=selected_status == value,
            url=f"{base_url}?status={value}",
        )
        for value, label in definitions
    ]


def _delete_file_field(field):
    if not field:
        return
    try:
        field.delete(save=False)
    except (OSError, ValueError):
        # The database row should still be removable when the underlying file
        # was already cleaned up or the storage backend is temporarily missing.
        pass


def _photo_url(field):
    try:
        return field.url if field else ""
    except (ValueError, OSError):
        return ""


def _lock_message(labels, status):
    if status == "review":
        return labels["review_locked"]
    if status == "completed":
        return labels["approved_locked"]
    if status == "cancelled":
        return labels["void_locked"]
    return ""


@login_required(login_url="/login/")
@never_cache
@require_GET
def portal_home(request, company_slug):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied
    return redirect(_url("inspection_list", company))


@login_required(login_url="/login/")
@never_cache
@require_POST
def portal_language(request, company_slug):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied

    selected = _normalise_language(request.POST.get("language")) or "en"

    # Update the database directly and the in-memory user instance. This avoids
    # stale related-object caches and makes the preference reliable even when
    # the account was loaded by middleware before this view runs.
    request.user.__class__.objects.filter(pk=request.user.pk).update(
        preferred_language=selected
    )
    request.user.preferred_language = selected

    request.session["contractor_portal_language"] = selected
    request.session.modified = True
    translation.activate(selected)
    request.LANGUAGE_CODE = selected
    request.crm_language = selected

    fallback = _url("inspection_list", company)
    candidate = (request.POST.get("next") or "").strip()
    if not (
        candidate
        and url_has_allowed_host_and_scheme(
            candidate,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
        and candidate.startswith(f"/{company.slug}/field-work/")
    ):
        candidate = fallback

    response = redirect(candidate)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        selected,
        max_age=LANGUAGE_COOKIE_MAX_AGE,
        path="/",
        secure=request.is_secure(),
        httponly=False,
        samesite="Lax",
    )
    response["Content-Language"] = selected
    response["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@login_required(login_url="/login/")
@never_cache
@require_GET
def inspection_list(request, company_slug):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied

    due_ids = InspectionAssignment.objects.filter(
        client__id_company=company,
        inspector=request.user,
        status="pending",
        inspection_date__date__lte=timezone.localdate(),
    ).values_list("id_assignment", flat=True)
    InspectionAssignment.objects.filter(id_assignment__in=due_ids).update(status="in_progress")

    base_queryset = (
        InspectionAssignment.objects.select_related("client")
        .filter(
            client__id_company=company,
            inspector=request.user,
            status__in=CONTRACTOR_VISIBLE_STATUSES,
        )
        .order_by("-inspection_date", "-created_at")
    )
    selected_status = (request.GET.get("status") or "").strip()
    if selected_status not in PORTAL_STATUS_VALUES:
        selected_status = ""

    counts = Counter(base_queryset.values_list("status", flat=True))
    assignments = list(base_queryset.filter(status=selected_status) if selected_status else base_queryset)
    labels = _labels(request)
    for assignment in assignments:
        assignment.portal_url = _url(
            "inspection_detail", company, id_assignment=assignment.id_assignment
        )
        assignment.portal_status = _status_label(labels, assignment.status)

    context = _base_context(request, company, "inspections")
    context.update(
        {
            "assignments": assignments,
            "page_title": labels["my_inspections"],
            "selected_status": selected_status,
            "status_filters": _status_filter_options(
                labels, _url("inspection_list", company), selected_status, counts
            ),
            "total_assignments": sum(counts.values()),
        }
    )
    return render(request, "contractor_portal/inspection_list.html", context)


def _inspection_for_user(request, company, id_assignment):
    return get_object_or_404(
        InspectionAssignment.objects.select_related("client", "inspector").prefetch_related(
            "gallery_images__uploaded_by"
        ),
        id_assignment=id_assignment,
        client__id_company=company,
        inspector=request.user,
        status__in=CONTRACTOR_VISIBLE_STATUSES,
    )


@login_required(login_url="/login/")
@never_cache
@require_GET
def inspection_detail(request, company_slug, id_assignment):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied
    assignment = _inspection_for_user(request, company, id_assignment)
    labels = _labels(request)
    editable = assignment.status in INSPECTION_MANUAL_STATUS_VALUES

    photos = []
    for image in assignment.gallery_images.exclude(file="").order_by("-uploaded_at"):
        can_delete = editable and image.uploaded_by_id in {None, request.user.pk}
        photos.append(
            SimpleNamespace(
                url=_photo_url(image.file),
                description=(image.description or "").strip(),
                uploaded_at=image.uploaded_at,
                can_delete=can_delete,
                delete_url=(
                    _url(
                        "inspection_photo_delete",
                        company,
                        id_assignment=assignment.id_assignment,
                        id_image=image.id_image,
                    )
                    if can_delete
                    else ""
                ),
            )
        )

    context = _base_context(request, company, "inspections")
    context.update(
        {
            "page_title": labels["my_inspections"],
            "assignment": assignment,
            "status_label": _status_label(labels, assignment.status),
            "editable": editable,
            "lock_message": _lock_message(labels, assignment.status),
            "photos": photos,
            "photo_count": len(photos),
            "photo_limit": MAX_FIELD_PHOTOS,
            "photo_remaining": max(0, MAX_FIELD_PHOTOS - len(photos)),
            "submit_url": _url(
                "inspection_submit", company, id_assignment=assignment.id_assignment
            ),
            "back_url": _url("inspection_list", company),
        }
    )
    return render(request, "contractor_portal/inspection_detail.html", context)


@login_required(login_url="/login/")
@require_POST
def inspection_submit(request, company_slug, id_assignment):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied
    assignment = _inspection_for_user(request, company, id_assignment)
    labels = _labels(request)
    detail_url = _url("inspection_detail", company, id_assignment=assignment.id_assignment)

    try:
        ensure_media_storage_ready()
        submit_inspection_assignment_for_review(
            assignment,
            request.user,
            notes=request.POST.get("inspection_notes"),
            recommendations=request.POST.get("recommendations"),
            uploads=collect_photo_slots(request),
        )
    except OSError:
        messages.error(request, labels["storage_error"])
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, labels["inspection_sent"])
    return redirect(detail_url)


@login_required(login_url="/login/")
@require_POST
def inspection_photo_delete(request, company_slug, id_assignment, id_image):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied
    assignment = _inspection_for_user(request, company, id_assignment)
    labels = _labels(request)
    detail_url = _url("inspection_detail", company, id_assignment=assignment.id_assignment)

    if assignment.status not in INSPECTION_MANUAL_STATUS_VALUES:
        return HttpResponseForbidden(labels["photo_delete_forbidden"])

    image = get_object_or_404(
        InspectionAssignmentGalleryImage,
        id_image=id_image,
        assignment=assignment,
    )
    if image.uploaded_by_id not in {None, request.user.pk}:
        return HttpResponseForbidden(labels["photo_delete_forbidden"])

    _delete_file_field(image.file)
    image.delete()
    messages.success(request, labels["photo_deleted"])
    return redirect(f"{detail_url}#photos")


@login_required(login_url="/login/")
@never_cache
@require_GET
def project_list(request, company_slug):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied

    base_queryset = (
        Project.objects.select_related("id_client")
        .filter(id_company=company, status__in=CONTRACTOR_VISIBLE_STATUSES)
        .filter(Q(id_inspector=request.user) | Q(assignments__id_user=request.user))
        .distinct()
        .order_by("-created_at")
    )
    selected_status = (request.GET.get("status") or "").strip()
    if selected_status not in PORTAL_STATUS_VALUES:
        selected_status = ""

    counts = Counter(base_queryset.values_list("status", flat=True))
    projects = list(base_queryset.filter(status=selected_status) if selected_status else base_queryset)
    labels = _labels(request)
    for project in projects:
        project.portal_url = _url("project_detail", company, id_project=project.id_project)
        project.portal_status = _status_label(labels, project.status)

    context = _base_context(request, company, "projects")
    context.update(
        {
            "projects": projects,
            "page_title": labels["my_projects"],
            "selected_status": selected_status,
            "status_filters": _status_filter_options(
                labels, _url("project_list", company), selected_status, counts
            ),
            "total_projects": sum(counts.values()),
        }
    )
    return render(request, "contractor_portal/project_list.html", context)


def _project_for_user(request, company, id_project):
    return get_object_or_404(
        Project.objects.select_related("id_client", "id_inspector").filter(
            Q(id_inspector=request.user) | Q(assignments__id_user=request.user),
            id_project=id_project,
            id_company=company,
            status__in=CONTRACTOR_VISIBLE_STATUSES,
        ).distinct()
    )


@login_required(login_url="/login/")
@never_cache
@require_GET
def project_detail(request, company_slug, id_project):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied
    project = _project_for_user(request, company, id_project)
    labels = _labels(request)
    editable = project.status in PROJECT_MANUAL_STATUS_VALUES

    photos = []
    for evidence in ProjectEvidence.objects.filter(id_project=project).exclude(file=""):
        can_delete = editable and evidence.uploaded_by_id in {None, request.user.pk}
        photos.append(
            SimpleNamespace(
                url=_photo_url(evidence.file),
                description=(evidence.description or "").strip(),
                uploaded_at=evidence.uploaded_at,
                can_delete=can_delete,
                delete_url=(
                    _url(
                        "project_photo_delete",
                        company,
                        id_project=project.id_project,
                        photo_kind="evidence",
                        id_photo=evidence.id_project_evidence,
                    )
                    if can_delete
                    else ""
                ),
            )
        )
    for image in ProjectGalleryImage.objects.filter(project=project).exclude(image=""):
        can_delete = editable and image.uploaded_by_id in {None, request.user.pk}
        photos.append(
            SimpleNamespace(
                url=_photo_url(image.image),
                description="",
                uploaded_at=image.uploaded_at,
                can_delete=can_delete,
                delete_url=(
                    _url(
                        "project_photo_delete",
                        company,
                        id_project=project.id_project,
                        photo_kind="gallery",
                        id_photo=image.id_project_gallery_image,
                    )
                    if can_delete
                    else ""
                ),
            )
        )
    photos.sort(key=lambda row: row.uploaded_at, reverse=True)

    context = _base_context(request, company, "projects")
    context.update(
        {
            "page_title": labels["my_projects"],
            "project": project,
            "status_label": _status_label(labels, project.status),
            "editable": editable,
            "lock_message": _lock_message(labels, project.status),
            "photos": photos,
            "photo_count": len(photos),
            "photo_limit": MAX_FIELD_PHOTOS,
            "photo_remaining": max(0, MAX_FIELD_PHOTOS - len(photos)),
            "submit_url": _url("project_submit", company, id_project=project.id_project),
            "back_url": _url("project_list", company),
        }
    )
    return render(request, "contractor_portal/project_detail.html", context)


@login_required(login_url="/login/")
@require_POST
def project_submit(request, company_slug, id_project):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied
    project = _project_for_user(request, company, id_project)
    labels = _labels(request)
    detail_url = _url("project_detail", company, id_project=project.id_project)

    try:
        ensure_media_storage_ready()
        submit_project_for_review(
            project,
            request.user,
            observations=request.POST.get("contractor_observations"),
            recommendations=request.POST.get("contractor_recommendations"),
            uploads=collect_photo_slots(request),
        )
    except OSError:
        messages.error(request, labels["storage_error"])
    except (ValueError, PermissionError) as error:
        messages.error(request, str(error))
    else:
        messages.success(request, labels["project_sent"])
    return redirect(detail_url)

@login_required(login_url="/login/")
@require_POST
def project_photo_delete(request, company_slug, id_project, photo_kind, id_photo):
    company, denied = _guard(request, company_slug)
    if denied:
        return denied
    project = _project_for_user(request, company, id_project)
    labels = _labels(request)
    detail_url = _url("project_detail", company, id_project=project.id_project)

    if project.status not in PROJECT_MANUAL_STATUS_VALUES:
        return HttpResponseForbidden(labels["photo_delete_forbidden"])

    if photo_kind == "evidence":
        photo = get_object_or_404(
            ProjectEvidence,
            id_project=project,
            id_project_evidence=id_photo,
        )
        file_field = photo.file
    elif photo_kind == "gallery":
        photo = get_object_or_404(
            ProjectGalleryImage,
            project=project,
            id_project_gallery_image=id_photo,
        )
        file_field = photo.image
    else:
        raise Http404("Photo not found.")

    if photo.uploaded_by_id not in {None, request.user.pk}:
        return HttpResponseForbidden(labels["photo_delete_forbidden"])

    _delete_file_field(file_field)
    photo.delete()
    messages.success(request, labels["photo_deleted"])
    return redirect(f"{detail_url}#photos")

