import os
import uuid

from django.core import signing
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename


TEMP_COMPANY_LOGO_FOLDER = "temp_uploads/company_logos"
TEMP_COMPANY_LOGO_MAX_AGE_SECONDS = 60 * 60 * 4
TEMP_COMPANY_LOGO_SIGNING_SALT = "companies.temp.company.logo"


def save_company_logo_to_temp(uploaded_file):
    if not uploaded_file:
        return ""

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    original_name = get_valid_filename(uploaded_file.name or "logo")
    base_name, extension = os.path.splitext(original_name)

    extension = extension.lower() or ".upload"
    temp_filename = f"{uuid.uuid4().hex}{extension}"
    temp_path = f"{TEMP_COMPANY_LOGO_FOLDER}/{temp_filename}"

    saved_path = default_storage.save(temp_path, uploaded_file)

    token = signing.dumps(
        {
            "path": saved_path,
            "name": original_name,
        },
        salt=TEMP_COMPANY_LOGO_SIGNING_SALT,
    )

    return token


def get_temp_company_logo_data(token):
    token = (token or "").strip()

    if not token:
        return None

    try:
        data = signing.loads(
            token,
            salt=TEMP_COMPANY_LOGO_SIGNING_SALT,
            max_age=TEMP_COMPANY_LOGO_MAX_AGE_SECONDS,
        )
    except signing.BadSignature:
        return None

    temp_path = data.get("path")
    original_name = data.get("name") or "logo"

    if not temp_path:
        return None

    if not temp_path.startswith(f"{TEMP_COMPANY_LOGO_FOLDER}/"):
        return None

    if not default_storage.exists(temp_path):
        return None

    return {
        "token": token,
        "path": temp_path,
        "name": original_name,
        "url": default_storage.url(temp_path),
    }


def get_temp_company_logo_context(token):
    temp_logo = get_temp_company_logo_data(token)

    if not temp_logo:
        return {
            "logo_temp_token": "",
            "temp_logo_url": "",
            "temp_logo_name": "",
        }

    return {
        "logo_temp_token": temp_logo["token"],
        "temp_logo_url": temp_logo["url"],
        "temp_logo_name": temp_logo["name"],
    }


def delete_temp_company_logo(token):
    temp_logo = get_temp_company_logo_data(token)

    if not temp_logo:
        return False

    try:
        default_storage.delete(temp_logo["path"])
        return True
    except Exception:
        return False


def apply_temp_company_logo_to_instance(company, token, save=True):
    temp_logo = get_temp_company_logo_data(token)

    if not company or not temp_logo:
        return False

    original_name = get_valid_filename(temp_logo["name"] or "logo")
    base_name, extension = os.path.splitext(original_name)

    if not extension:
        extension = os.path.splitext(temp_logo["path"])[1]

    extension = extension.lower() or ".png"
    final_filename = f"logo{extension}"

    with default_storage.open(temp_logo["path"], "rb") as source_file:
        company.logo.save(
            final_filename,
            File(source_file),
            save=False,
        )

    if save:
        company.save(update_fields=["logo"])

    delete_temp_company_logo(token)

    return True