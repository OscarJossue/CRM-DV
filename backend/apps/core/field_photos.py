"""Validation and storage helpers for contractor field-photo uploads."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_FIELD_PHOTOS = 5
MAX_FIELD_PHOTO_BYTES = 10 * 1024 * 1024
MAX_FIELD_PHOTO_DIMENSION = 1440
FIELD_PHOTO_WEBP_QUALITY = 68


def ensure_media_storage_ready():
    """Verify the mounted media volume is writable before processing uploads.

    Container startup repairs ownership, while this preflight turns a storage
    problem into a controlled form error instead of a raw operating-system
    exception after the user has selected several phone photos.
    """
    media_root = Path(settings.MEDIA_ROOT)
    probe_dir = media_root / ".write-check"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_file = probe_dir / f"{uuid4().hex}.tmp"
    try:
        probe_file.write_bytes(b"ok")
    finally:
        try:
            probe_file.unlink(missing_ok=True)
        except OSError:
            pass
    return True


def validate_field_photo(uploaded_file):
    """Return an error message for invalid uploads, otherwise an empty string."""
    if not uploaded_file:
        return "Select a photo."

    if getattr(uploaded_file, "size", 0) > MAX_FIELD_PHOTO_BYTES:
        return "Each photo must be 10 MB or smaller."

    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type and not content_type.startswith("image/"):
        return "Only image files are allowed."

    try:
        image = Image.open(uploaded_file)
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return "One of the selected files is not a valid image."
    finally:
        try:
            uploaded_file.seek(0)
        except (AttributeError, OSError):
            pass

    return ""


def optimize_field_photo(uploaded_file, *, prefix="field-photo"):
    """Convert an uploaded image to a resized, metadata-free WebP file.

    The original upload is never written to storage. This keeps contractor
    evidence small and predictable regardless of whether it came from a phone
    camera or the desktop file picker.
    """
    validation_error = validate_field_photo(uploaded_file)
    if validation_error:
        raise ValueError(validation_error)

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source:
            image = ImageOps.exif_transpose(source)
            image.load()

            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            image = image.convert("RGBA" if has_alpha else "RGB")
            image.thumbnail(
                (MAX_FIELD_PHOTO_DIMENSION, MAX_FIELD_PHOTO_DIMENSION),
                Image.Resampling.LANCZOS,
            )

            output = BytesIO()
            image.save(
                output,
                format="WEBP",
                quality=FIELD_PHOTO_WEBP_QUALITY,
                method=6,
                optimize=True,
            )
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValueError("The selected photo could not be converted to WebP.") from error
    finally:
        try:
            uploaded_file.seek(0)
        except (AttributeError, OSError):
            pass

    safe_prefix = "".join(character for character in prefix if character.isalnum() or character in {"-", "_"})
    safe_prefix = safe_prefix.strip("-_ ") or "field-photo"
    original_stem = Path(getattr(uploaded_file, "name", "photo")).stem
    original_stem = "".join(character for character in original_stem if character.isalnum() or character in {"-", "_"})[:40]
    filename = f"{safe_prefix}-{original_stem or 'photo'}-{uuid4().hex[:12]}.webp"
    return ContentFile(output.getvalue(), name=filename)


def collect_photo_slots(request, limit=MAX_FIELD_PHOTOS):
    """Collect numbered photo/description pairs posted by contractor UIs."""
    rows = []
    for index in range(1, limit + 1):
        uploaded_file = request.FILES.get(f"photo_{index}")
        if not uploaded_file:
            continue
        rows.append(
            {
                "index": index,
                "file": uploaded_file,
                "description": (request.POST.get(f"description_{index}") or "").strip(),
            }
        )
    return rows
