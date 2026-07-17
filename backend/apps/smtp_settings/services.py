from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

from .models import SmtpSetting
from .security import CredentialDecryptionError, decrypt_smtp_password


def get_or_create_smtp_setting(company):
    smtp_setting, created = SmtpSetting.objects.get_or_create(
        id_company=company,
        defaults={
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "use_tls": True,
            "use_ssl": False,
            "smtp_username": "",
            "smtp_password": "",
            "default_from_email": "",
            "from_name": str(company),
            "is_active": False,
        },
    )

    return smtp_setting


def get_active_smtp_setting_for_company(company):
    if not company:
        return None

    return SmtpSetting.objects.filter(
        id_company=company,
        is_active=True,
    ).first()


def validate_smtp_setting(smtp_setting):
    if not smtp_setting:
        raise ValueError("SMTP settings were not found for this company.")

    if not smtp_setting.is_active:
        raise ValueError("SMTP settings are not active for this company.")

    smtp_host = (smtp_setting.smtp_host or "").strip()
    smtp_username = (smtp_setting.smtp_username or "").strip()
    try:
        smtp_password = decrypt_smtp_password(smtp_setting.smtp_password)
    except CredentialDecryptionError as exc:
        raise ValueError(str(exc)) from exc
    default_from_email = (smtp_setting.default_from_email or "").strip()
    smtp_port = smtp_setting.smtp_port

    if not smtp_host:
        raise ValueError("SMTP host is required.")

    if smtp_host.startswith(("http://", "https://")):
        raise ValueError("SMTP host must be only the server name. Example: mail.yourdomain.com")

    if not smtp_port:
        raise ValueError("SMTP port is required.")

    if not smtp_username:
        raise ValueError("SMTP username is required.")

    if not smtp_password:
        raise ValueError("SMTP password is required.")

    if not default_from_email:
        raise ValueError("Default from email is required.")

    if smtp_setting.use_tls and smtp_setting.use_ssl:
        raise ValueError("Use TLS and Use SSL cannot both be enabled.")

    if smtp_port in [80, 443]:
        raise ValueError("Port 443/80 is for websites, not SMTP. Use 465 with SSL or 587 with TLS.")

    if smtp_port == 465 and not smtp_setting.use_ssl:
        raise ValueError("Port 465 must use SSL enabled and TLS disabled.")

    if smtp_port == 465 and smtp_setting.use_tls:
        raise ValueError("Port 465 must use SSL, not TLS.")

    if smtp_port == 587 and not smtp_setting.use_tls:
        raise ValueError("Port 587 must use TLS enabled and SSL disabled.")

    if smtp_port == 587 and smtp_setting.use_ssl:
        raise ValueError("Port 587 must use TLS, not SSL.")

    return True


def build_smtp_connection(smtp_setting):
    validate_smtp_setting(smtp_setting)

    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=(smtp_setting.smtp_host or "").strip(),
        port=smtp_setting.smtp_port,
        username=(smtp_setting.smtp_username or "").strip(),
        password=decrypt_smtp_password(smtp_setting.smtp_password),
        use_tls=smtp_setting.use_tls,
        use_ssl=smtp_setting.use_ssl,
        timeout=20,
    )


def get_from_email(smtp_setting):
    default_from_email = (smtp_setting.default_from_email or "").strip()
    from_name = (smtp_setting.from_name or "").strip()

    if from_name:
        return f"{from_name} <{default_from_email}>"

    return default_from_email


def send_company_email(
    company,
    subject,
    text_body,
    to_emails,
    html_body=None,
    attachments=None,
    cc_emails=None,
    bcc_emails=None,
):
    """
    Sends an email using the active SMTP configuration of the company.

    Kept backward-compatible with the previous signature and extended with
    attachments so estimates can attach their PDF without breaking invoices,
    projects, inspections or contracts.
    """
    smtp_setting = get_active_smtp_setting_for_company(company)
    validate_smtp_setting(smtp_setting)

    if isinstance(to_emails, str):
        to_emails = [to_emails]

    if isinstance(cc_emails, str):
        cc_emails = [cc_emails]

    if isinstance(bcc_emails, str):
        bcc_emails = [bcc_emails]

    to_emails = [email for email in (to_emails or []) if email]
    cc_emails = [email for email in (cc_emails or []) if email]
    bcc_emails = [email for email in (bcc_emails or []) if email]

    if not to_emails:
        raise ValueError("At least one recipient email is required.")

    connection = build_smtp_connection(smtp_setting)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=get_from_email(smtp_setting),
        to=to_emails,
        cc=cc_emails,
        bcc=bcc_emails,
        connection=connection,
    )

    if html_body:
        email.attach_alternative(html_body, "text/html")

    for attachment in attachments or []:
        if not attachment:
            continue

        filename, content, mimetype = attachment
        email.attach(filename, content, mimetype)

    return email.send(fail_silently=False)


def test_smtp_setting(smtp_setting, recipient_email):
    try:
        validate_smtp_setting(smtp_setting)

        subject = "SMTP Test Email"
        text_body = (
            "This is a SMTP test email from your CRM. "
            "If you received this message, your email configuration is working."
        )

        connection = build_smtp_connection(smtp_setting)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=get_from_email(smtp_setting),
            to=[recipient_email],
            connection=connection,
        )

        email.attach_alternative(
            """
            <h2>SMTP Test Email</h2>
            <p>This is a SMTP test email from your CRM.</p>
            <p>If you received this message, your email configuration is working.</p>
            """,
            "text/html",
        )

        email.send(fail_silently=False)

        smtp_setting.last_test_status = "success"
        smtp_setting.last_test_message = "SMTP test email sent successfully."
        smtp_setting.last_tested_at = timezone.now()
        smtp_setting.save(
            update_fields=[
                "last_test_status",
                "last_test_message",
                "last_tested_at",
                "updated_at",
            ]
        )

        return True, "SMTP test email sent successfully."

    except Exception as error:
        error_message = str(error)

        if smtp_setting:
            smtp_setting.last_test_status = "failed"
            smtp_setting.last_test_message = (
                f"SMTP test failed using {smtp_setting.smtp_host}:{smtp_setting.smtp_port} "
                f"TLS={smtp_setting.use_tls} SSL={smtp_setting.use_ssl}. Error: {error_message}"
            )
            smtp_setting.last_tested_at = timezone.now()
            smtp_setting.save(
                update_fields=[
                    "last_test_status",
                    "last_test_message",
                    "last_tested_at",
                    "updated_at",
                ]
            )

        return False, error_message
