from django.db import transaction

from .models import Client


def normalize_client_name(data):
    first_name = (data.get("first_name") or "").strip()
    middle_name = (data.get("middle_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    second_last_name = (data.get("second_last_name") or "").strip()
    name = (data.get("name") or "").strip()

    full_name = " ".join(
        filter(
            None,
            [
                first_name,
                middle_name,
                last_name,
                second_last_name,
            ],
        )
    ).strip()

    if full_name:
        data["name"] = full_name
    elif name:
        data["name"] = name

    return data


@transaction.atomic
def client_create(**data):
    data = normalize_client_name(data)

    client = Client(**data)
    client.full_clean()
    client.save()

    return client


@transaction.atomic
def client_update(client, **data):
    allowed_fields = [
        "id_company",
        "name",
        "first_name",
        "middle_name",
        "last_name",
        "second_last_name",
        "dni",
        "phone",
        "email",
        "address",
        "city",
        "state",
        "notes",
    ]

    clean_data = {}

    for field in allowed_fields:
        if field in data:
            clean_data[field] = data[field]
            setattr(client, field, data[field])

    normalize_client_name(clean_data)

    if clean_data.get("name"):
        client.name = clean_data["name"]

    client.full_clean()
    client.save()

    return client


def create_clients(**data):
    return client_create(**data)


def update_clients(instance, **data):
    return client_update(instance, **data)