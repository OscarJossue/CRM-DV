from django.db import transaction

from apps.clients.models import Client

from .models import Lead
from .models.choices import LEAD_STATUS_CONVERTED


@transaction.atomic
def lead_create(**data):
    return Lead.objects.create(**data)


@transaction.atomic
def lead_update(lead, **data):
    allowed_fields = [
        "id_company",
        "id_assigned_user",
        "id_converted_client",
        "name",
        "phone",
        "email",
        "source",
        "address",
        "status",
        "notes",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(lead, field, data[field])

    lead.full_clean()
    lead.save()

    return lead


@transaction.atomic
def convert_lead_to_client(lead: Lead):
    if lead.id_converted_client_id:
        return lead.id_converted_client

    client = Client.objects.create(
        id_company=lead.id_company,
        name=lead.name,
        phone=lead.phone,
        email=lead.email,
        address=lead.address,
        notes=lead.notes,
    )

    lead.id_converted_client = client
    lead.status = LEAD_STATUS_CONVERTED
    lead.save(update_fields=["id_converted_client", "status"])

    return client
