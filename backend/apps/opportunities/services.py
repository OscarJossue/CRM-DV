from django.db import transaction

from apps.projects.models import Project

from .models import Lead
from .models.choices import OPPORTUNITY_STATUS_WON


@transaction.atomic
def lead_create(**data):
    lead = Lead(**data)
    lead.full_clean()
    lead.save()

    return lead


@transaction.atomic
def lead_update(lead, **data):
    allowed_fields = [
        "id_company",
        "id_client",
        "id_assigned_user",
        "id_converted_project",
        "source",
        "status",
        "notes",
        "next_follow_up_date",
        "approximate_value",
        "project_description",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(lead, field, data[field])

    lead.full_clean()
    lead.save()

    return lead


@transaction.atomic
def convert_lead_to_project(lead, user=None):
    if lead.id_converted_project_id:
        raise ValueError("This opportunity has already been converted to a project.")

    if not lead.id_client_id:
        raise ValueError("This opportunity must have a client before conversion.")

    if lead.status not in [
        OPPORTUNITY_STATUS_WON
    ]:
        raise ValueError("Only won opportunities can be converted to project.")

    client = lead.id_client
    project_name = lead.name or f"Project for {client.name}"

    project = Project.objects.create(
        id_company=lead.id_company,
        id_client=client,
        id_opportunity=lead,
        id_inspector=lead.id_assigned_user,
        name=project_name,
        project_address=lead.address or client.address,
        description=lead.project_description,
        status="pending",
        progress=0,
        contract_amount=lead.approximate_value or 0,
        created_by=user if user and user.is_authenticated else None,
        updated_by=user if user and user.is_authenticated else None,
    )

    lead.status = OPPORTUNITY_STATUS_CONVERTED
    lead.id_converted_project = project
    lead.save(
        update_fields=[
            "status",
            "id_converted_project",
            "updated_at",
        ]
    )

    return project


def convert_lead_to_client(lead, user=None):
    return convert_lead_to_project(
        lead=lead,
        user=user,
    )