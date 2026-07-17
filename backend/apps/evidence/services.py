import uuid

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils.text import get_valid_filename

from .models import EvidenceFile


def save_evidence_upload(*, uploaded_file, project):
    original_name = get_valid_filename(uploaded_file.name)
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    storage_path = f"evidence/project_{project.id_project}/{unique_name}"

    saved_path = default_storage.save(storage_path, uploaded_file)

    return default_storage.url(saved_path)


@transaction.atomic
def evidence_file_create(*, user, id_project, file_type=None, file_url=None, description=None, file_upload=None):
    final_file_url = file_url

    if file_upload:
        final_file_url = save_evidence_upload(
            uploaded_file=file_upload,
            project=id_project,
        )

    evidence = EvidenceFile.objects.create(
        id_project=id_project,
        id_user=user,
        file_type=file_type,
        file_url=final_file_url,
        description=description,
    )

    return evidence


@transaction.atomic
def evidence_file_update(evidence, **data):
    file_upload = data.pop("file_upload", None)

    allowed_fields = [
        "id_project",
        "file_type",
        "file_url",
        "description",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(evidence, field, data[field])

    if file_upload:
        evidence.file_url = save_evidence_upload(
            uploaded_file=file_upload,
            project=evidence.id_project,
        )

    evidence.full_clean()
    evidence.save()

    return evidence


def create_evidence(**data):
    return EvidenceFile.objects.create(**data)


def update_evidence(instance, **data):
    return evidence_file_update(instance, **data)
