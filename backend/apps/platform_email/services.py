from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

from .models import PlatformEmailLog
from .models.choices import EMAIL_STATUS_FAILED, EMAIL_STATUS_SENT, EMAIL_TYPE_TEST


def get_platform_email_connection():
    return get_connection(
        backend=getattr(
            settings,
            "PLATFORM_EMAIL_BACKEND",
            "django.core.mail.backends.console.EmailBackend",
        ),
        host=getattr(settings, "PLATFORM_EMAIL_HOST", ""),
        port=getattr(settings, "PLATFORM_EMAIL_PORT", 587),
        username=getattr(settings, "PLATFORM_EMAIL_HOST_USER", ""),
        password=getattr(settings, "PLATFORM_EMAIL_HOST_PASSWORD", ""),
        use_tls=getattr(settings, "PLATFORM_EMAIL_USE_TLS", True),
        use_ssl=getattr(settings, "PLATFORM_EMAIL_USE_SSL", False),
        timeout=20,
    )


def attach_inline_image(email, image_path, content_id, filename=None):
    path = Path(image_path)

    if not path.exists() or not path.is_file():
        return False

    suffix = path.suffix.lower().replace(".", "")

    if suffix == "jpg":
        suffix = "jpeg"

    if suffix not in ["png", "jpeg", "gif", "webp"]:
        suffix = "png"

    with path.open("rb") as image_file:
        image = MIMEImage(image_file.read(), _subtype=suffix)

    image.add_header("Content-ID", f"<{content_id}>")
    image.add_header(
        "Content-Disposition",
        "inline",
        filename=filename or path.name,
    )

    email.attach(image)

    return True


def send_platform_email(
    *,
    recipient_email,
    subject,
    message,
    company=None,
    email_type=EMAIL_TYPE_TEST,
):
    email_log = PlatformEmailLog.objects.create(
        id_company=company,
        recipient_email=recipient_email,
        subject=subject,
        message=message,
        email_type=email_type,
    )

    try:
        connection = get_platform_email_connection()

        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=getattr(
                settings,
                "PLATFORM_DEFAULT_FROM_EMAIL",
                "CEO Marketing CRM <noreply@ceomarketingusa.com>",
            ),
            to=[recipient_email],
            connection=connection,
        )

        sent_count = email.send(fail_silently=False)

        if sent_count:
            email_log.status = EMAIL_STATUS_SENT
            email_log.sent_at = timezone.now()
            email_log.save(update_fields=["status", "sent_at"])
        else:
            email_log.status = EMAIL_STATUS_FAILED
            email_log.error_message = "SMTP backend did not send the message."
            email_log.save(update_fields=["status", "error_message"])

    except Exception as error:
        email_log.status = EMAIL_STATUS_FAILED
        email_log.error_message = str(error)
        email_log.save(update_fields=["status", "error_message"])

    return email_log


def send_platform_html_email(
    *,
    recipient_email,
    subject,
    message,
    html_message,
    company=None,
    email_type="platform_document",
    inline_images=None,
):
    email_log = PlatformEmailLog.objects.create(
        id_company=company,
        recipient_email=recipient_email,
        subject=subject,
        message=message,
        email_type=email_type,
    )

    try:
        connection = get_platform_email_connection()

        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=getattr(
                settings,
                "PLATFORM_DEFAULT_FROM_EMAIL",
                "CEO Marketing CRM <noreply@ceomarketingusa.com>",
            ),
            to=[recipient_email],
            connection=connection,
        )

        email.mixed_subtype = "related"
        email.attach_alternative(html_message, "text/html")

        for inline_image in inline_images or []:
            attach_inline_image(
                email=email,
                image_path=inline_image.get("path"),
                content_id=inline_image.get("cid"),
                filename=inline_image.get("filename"),
            )

        sent_count = email.send(fail_silently=False)

        if sent_count:
            email_log.status = EMAIL_STATUS_SENT
            email_log.sent_at = timezone.now()
            email_log.save(update_fields=["status", "sent_at"])
        else:
            email_log.status = EMAIL_STATUS_FAILED
            email_log.error_message = "SMTP backend did not send the HTML message."
            email_log.save(update_fields=["status", "error_message"])

    except Exception as error:
        email_log.status = EMAIL_STATUS_FAILED
        email_log.error_message = str(error)
        email_log.save(update_fields=["status", "error_message"])

    return email_log