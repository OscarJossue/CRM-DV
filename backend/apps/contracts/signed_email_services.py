from django.core.mail import EmailMultiAlternatives
from apps.contracts.models import Contract
from apps.contracts.services import build_contract_pdf_bytes, get_contract_pdf_filename
from apps.core.ui_translation import translate_ui_text as ui, use_company_language


def _safe_email(value):
    value = (value or "").strip()
    return value if "@" in value else ""


def get_contract_customer_email(contract):
    email = _safe_email(getattr(contract, "client_email", ""))

    if email:
        return email

    client = getattr(contract, "id_client", None)

    if client:
        email = _safe_email(getattr(client, "email", ""))
        if email:
            return email

    return ""


@use_company_language
def send_contract_signed_customer_email(contract, public_contract_url=""):
    customer_email = get_contract_customer_email(contract)

    if not customer_email:
        return 0

    company = getattr(contract, "id_company", None)
    company_name = getattr(company, "name", "") or ui("CRM Team")

    contract_number = (
        getattr(contract, "contract_number", "")
        or getattr(contract, "id_contract", "")
    )

    customer_name = (
        getattr(contract, "client_name", "")
        or ui("Customer")
    )

    subject = f"{ui('{ui("Contract Signed Successfully")}')} - {contract_number}"

    text_body = (
        f"{ui('Hello')} {customer_name},\n\n"
        f"{ui('Your contract')} {contract_number} {ui('has been signed successfully.')}\n\n"
        f"{ui('Status')}: {ui(contract.get_status_display() if hasattr(contract, 'get_status_display') else contract.status)}\n"
    )

    if public_contract_url:
        text_body += f"\n{ui('View contract')}:\n{public_contract_url}\n"

    html_body = f"""
    <div style="margin:0;padding:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#111827;">
      <div style="max-width:680px;margin:0 auto;padding:28px 18px;">
        <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;overflow:hidden;">
          <div style="background:#166534;color:#ffffff;padding:24px;">
            <h1 style="margin:0;font-size:24px;line-height:1.25;">{ui("Contract Signed Successfully")}</h1>
            <p style="margin:8px 0 0;color:#dcfce7;">{company_name}</p>
          </div>

          <div style="padding:24px;">
            <p style="margin:0 0 14px;font-size:16px;line-height:1.6;">
              {ui("Hello")} <strong>{customer_name}</strong>,
            </p>

            <p style="margin:0 0 14px;font-size:16px;line-height:1.6;">
              {ui("Your contract")} <strong>{contract_number}</strong> {ui("has been approved and signed successfully.")}
            </p>

            <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:14px;padding:16px;margin:18px 0;">
              <p style="margin:0 0 8px;"><strong>{ui("Contract")}:</strong> {contract_number}</p>
              <p style="margin:0;"><strong>{ui("Status")}:</strong> {ui(contract.get_status_display() if hasattr(contract, "get_status_display") else contract.status)}</p>
            </div>
    """

    if public_contract_url:
        html_body += f"""
            <p style="margin:24px 0;text-align:center;">
              <a href="{public_contract_url}" target="_blank" style="display:inline-block;background:#166534;color:#ffffff;text-decoration:none;padding:13px 22px;border-radius:999px;font-weight:800;">
                {ui("View Signed Contract")}
              </a>
            </p>
        """

    html_body += """
          </div>
        </div>
      </div>
    </div>
    """

    try:
        from apps.smtp_settings.services import (
            build_smtp_connection,
            get_active_smtp_setting_for_company,
            get_from_email,
            validate_smtp_setting,
        )

        smtp_setting = get_active_smtp_setting_for_company(company)
        validate_smtp_setting(smtp_setting)

        connection = build_smtp_connection(smtp_setting)
        from_email = get_from_email(smtp_setting)

    except Exception as error:
        raise ValueError(f"SMTP service is not available or not configured: {error}")

    contract = (
        Contract.objects
        .select_related(
            "id_company",
            "id_client",
            "id_project",
            "id_estimate",
        )
        .prefetch_related(
            "evidence_photos",
        )
        .get(pk=contract.pk)
    )

    pdf_bytes = build_contract_pdf_bytes(contract)
    filename = get_contract_pdf_filename(contract)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[customer_email],
        connection=connection,
    )

    email.attach_alternative(html_body, "text/html")

    email.attach(
        filename,
        pdf_bytes,
        "application/pdf",
    )

    return email.send()