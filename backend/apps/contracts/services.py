import io
import os

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.formats import date_format

from apps.core.ui_translation import get_company_language, translate_ui_text as ui, use_company_language

from .models import Contract

from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from .models.choices import (
    CONTRACT_EDITABLE_STATUSES,
    CONTRACT_SENDABLE_STATUSES,
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_CANCELLED,
    CONTRACT_STATUS_COMPLETED,
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_GENERATED,
    CONTRACT_STATUS_PENDING,
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_SIGNED,
    CONTRACT_STATUS_VOID,
)
DEFAULT_PAYMENT_TERMS = """1. If full payment is not received within thirty (30) days of job completion, all workmanship guarantees shall become void. However, if minor work remains to be done, no more than 2% of the total contract price may be withheld by the Customer pending full job completion. After thirty (30) days, a one and one-half (1 1/2) percent interest monthly interest charge will accrue on any outstanding balance. Any costs or expenses incurred to collect any unpaid balance for professional roofing services rendered shall become the responsibility of the Customer.

2. Our estimate for materials and labor is firm as quoted. However, when any roof tear-off is involved, our price may be increased due to unforeseen and/or hidden damage. In the event that unforeseen or hidden damage is discovered, the Customer will be notified as soon as reasonably possible under the circumstances and the Customer shall become fully responsible for the additional costs of materials and/or labor occasioned by the unforeseen or hidden damage.

3. In the event that the Customer requests any additional work not covered within the original proposal/contract, the Customer shall promptly give written notice of the same. All extra work must be agreed upon in writing and signed by both parties before such work is commenced. Pricing and payment terms for such extra work shall be as agreed upon by the parties at that time."""

DEFAULT_CANCELLATION_TERMS = """1. This proposal/contract may be cancelled by the Customer within three (3) business days following the signing hereof by giving written notice. If the Customer cancels this agreement after the permitted cancellation period, the Customer shall remain responsible for all costs, materials, labor, services, scheduling, administrative costs, and any work already performed or committed in connection with this agreement.

2. In the event the contractor is unable to complete the performance of obligations under this agreement due to an occurrence outside the control of the parties, including but not limited to unforeseen circumstances, labor or material shortages, acts of God, delays caused by weather, supplier delays, or other conditions beyond reasonable control, the Customer shall be liable only for the actual labor and materials already furnished, which payment shall be due within three (3) business days of such cancellation."""

DEFAULT_GUARANTEE_TERMS = """The following limited guarantee is provided in connection with this agreement for professional services:

1. Materials are subject to the warranty, if any, provided by the manufacturer of the materials used. The contractor does not guarantee or warrant materials beyond any manufacturer warranty that may apply.

2. Workmanship provided in connection with this contract is guaranteed to be free from defects for the period stated in the contract from the date of completion of the project. This guarantee shall cover only work performed by the contractor and shall not apply to damage caused by storms, weather conditions, improper maintenance, misuse, neglect, structural defects, pre-existing conditions, acts of God, work performed by others, or any condition outside the contractor's control.

3. The limited guarantee provided under this contract shall become effective only upon completion of the work required to be performed and payment in full of all amounts due under the terms of this agreement. In the event that the Customer fails to pay in full, the sums due and owing for professional services rendered, the limited guarantee shall be deemed null, void, and of no force or legal effect."""

DEFAULT_MISCELLANEOUS_TERMS = """1. Any dispute arising hereunder shall be governed by the laws of the applicable state where the work is performed and where the agreement was executed. The parties further agree that jurisdiction and venue shall be proper in the appropriate court having authority over the matter.

2. This document constitutes the entire agreement of the parties relating to the professional services described. The parties acknowledge and agree that this proposal/contract correctly states all terms of the agreement between the parties relating to the services to be provided. This agreement may only be modified in a written document executed by both parties and/or their authorized representative."""

DEFAULT_PAYMENT_TERMS_ES = """1. Si el pago total no se recibe dentro de los treinta (30) días posteriores a la finalización del trabajo, todas las garantías de mano de obra quedarán sin efecto. Sin embargo, si queda trabajo menor por completar, el Cliente podrá retener no más del 2 % del precio total del contrato hasta la finalización completa del trabajo. Después de treinta (30) días, se acumulará un cargo mensual por intereses de uno y medio por ciento (1 1/2 %) sobre cualquier saldo pendiente. Cualquier costo o gasto incurrido para cobrar un saldo no pagado por servicios profesionales de techado será responsabilidad del Cliente.

2. Nuestra estimación de materiales y mano de obra es firme según lo cotizado. Sin embargo, cuando el trabajo incluya el retiro de un techo, el precio podrá aumentar debido a daños imprevistos u ocultos. Si se descubre algún daño imprevisto u oculto, se notificará al Cliente tan pronto como sea razonablemente posible según las circunstancias, y el Cliente será plenamente responsable de los costos adicionales de materiales y/o mano de obra ocasionados por dicho daño.

3. Si el Cliente solicita trabajo adicional no incluido en la propuesta o contrato original, deberá notificarlo por escrito de manera oportuna. Todo trabajo adicional deberá acordarse por escrito y ser firmado por ambas partes antes de comenzar. El precio y las condiciones de pago de dicho trabajo adicional serán los que acuerden las partes en ese momento."""

DEFAULT_CANCELLATION_TERMS_ES = """1. El Cliente podrá cancelar esta propuesta o contrato dentro de los tres (3) días hábiles posteriores a su firma mediante notificación escrita. Si el Cliente cancela este acuerdo después del período permitido, seguirá siendo responsable de todos los costos, materiales, mano de obra, servicios, programación, costos administrativos y cualquier trabajo ya realizado o comprometido en relación con este acuerdo.

2. Si el contratista no puede completar sus obligaciones bajo este acuerdo debido a un hecho fuera del control de las partes, incluyendo, entre otros, circunstancias imprevistas, escasez de mano de obra o materiales, caso fortuito o fuerza mayor, demoras por condiciones climáticas, demoras de proveedores u otras condiciones fuera de un control razonable, el Cliente será responsable únicamente de la mano de obra y los materiales efectivamente suministrados. Dicho pago vencerá dentro de los tres (3) días hábiles posteriores a la cancelación."""

DEFAULT_GUARANTEE_TERMS_ES = """La siguiente garantía limitada se proporciona en relación con este acuerdo de servicios profesionales:

1. Los materiales están sujetos a la garantía, si existiere, proporcionada por el fabricante de los materiales utilizados. El contratista no garantiza los materiales más allá de cualquier garantía del fabricante que resulte aplicable.

2. La mano de obra realizada bajo este contrato se garantiza libre de defectos durante el período indicado en el contrato, contado desde la fecha de finalización del proyecto. Esta garantía cubre únicamente el trabajo realizado por el contratista y no se aplica a daños causados por tormentas, condiciones climáticas, mantenimiento inadecuado, uso indebido, negligencia, defectos estructurales, condiciones preexistentes, caso fortuito o fuerza mayor, trabajo realizado por terceros o cualquier condición fuera del control del contratista.

3. La garantía limitada de este contrato entrará en vigor únicamente cuando se complete el trabajo requerido y se paguen en su totalidad todos los montos adeudados conforme a este acuerdo. Si el Cliente no paga íntegramente las sumas adeudadas por los servicios profesionales prestados, la garantía limitada se considerará nula, sin efecto y sin fuerza legal."""

DEFAULT_MISCELLANEOUS_TERMS_ES = """1. Cualquier disputa derivada de este acuerdo se regirá por las leyes del estado aplicable donde se realice el trabajo y se haya celebrado el acuerdo. Las partes también acuerdan que la jurisdicción y competencia territorial corresponderán al tribunal apropiado con autoridad sobre el asunto.

2. Este documento constituye el acuerdo completo entre las partes respecto de los servicios profesionales descritos. Las partes reconocen y aceptan que esta propuesta o contrato expresa correctamente todas las condiciones acordadas en relación con los servicios que se prestarán. Este acuerdo solo podrá modificarse mediante un documento escrito firmado por ambas partes y/o sus representantes autorizados."""

MONEY_QUANTIZE = Decimal("0.01")


def money(value):
    if value in [None, ""]:
        value = Decimal("0.00")

    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            value = Decimal("0.00")

    return value.quantize(
        MONEY_QUANTIZE,
        rounding=ROUND_HALF_UP,
    )


def first_value(obj, field_names, default=""):
    if not obj:
        return default

    for field_name in field_names:
        value = getattr(obj, field_name, None)

        if value not in [None, ""]:
            return str(value)

    return default


def get_contract_company(contract):
    if getattr(contract, "id_company", None):
        return contract.id_company

    if getattr(contract, "id_project", None) and getattr(contract.id_project, "id_company", None):
        return contract.id_project.id_company

    if getattr(contract, "id_client", None) and getattr(contract.id_client, "id_company", None):
        return contract.id_client.id_company

    return None


def generate_contract_number(company):
    last_contract = (
        Contract.objects.filter(id_company=company)
        .exclude(contract_number__isnull=True)
        .exclude(contract_number="")
        .order_by("-id_contract")
        .first()
    )

    if not last_contract or not last_contract.contract_number:
        return "CON-000001"

    try:
        last_number = int(str(last_contract.contract_number).replace("CON-", ""))
    except (TypeError, ValueError):
        last_number = last_contract.id_contract or 0

    return f"CON-{last_number + 1:06d}"


def sync_contract_company(contract):
    company = get_contract_company(contract)

    if not company:
        raise ValueError("Contract company is required.")

    contract.id_company = company

    return contract


def sync_contract_company_snapshot(contract):
    company = contract.id_company

    if not company:
        return contract

    if not contract.company_name:
        contract.company_name = first_value(
            company,
            ["name", "company_name", "legal_name", "commercial_name"],
        )

    if not contract.company_phone:
        contract.company_phone = first_value(
            company,
            ["phone", "phone_number", "main_phone", "company_phone"],
        )

    if not contract.company_email:
        contract.company_email = first_value(
            company,
            ["email", "company_email", "contact_email"],
        )

    if not contract.company_address:
        contract.company_address = first_value(
            company,
            ["address", "company_address", "street_address", "full_address"],
        )

    if not contract.company_license:
        contract.company_license = first_value(
            company,
            ["license", "license_number", "company_license", "contractor_license"],
        )

    return contract


def sync_contract_client_snapshot(contract):
    client = contract.id_client

    if not client:
        return contract

    if not contract.client_name:
        contract.client_name = first_value(
            client,
            ["name", "legal_name", "commercial_name", "full_name"],
        )

    if not contract.client_phone:
        contract.client_phone = first_value(
            client,
            ["phone", "phone_number", "mobile", "main_phone"],
        )

    if not contract.client_alt_phone:
        contract.client_alt_phone = first_value(
            client,
            ["alt_phone", "secondary_phone", "other_phone"],
        )

    if not contract.client_email:
        contract.client_email = first_value(
            client,
            ["email", "contact_email", "billing_email"],
        )

    if not contract.client_street_address:
        contract.client_street_address = first_value(
            client,
            ["street_address", "address", "billing_address"],
        )

    if not contract.client_city:
        contract.client_city = first_value(
            client,
            ["city", "billing_city"],
        )

    if not contract.client_state:
        contract.client_state = first_value(
            client,
            ["state", "billing_state"],
        )

    if not contract.client_zip_code:
        contract.client_zip_code = first_value(
            client,
            ["zip_code", "zipcode", "postal_code", "billing_zip_code"],
        )

    return contract


def sync_contract_project_snapshot(contract):
    project = contract.id_project

    if not project:
        return contract

    if not contract.project_name:
        contract.project_name = first_value(
            project,
            ["name", "project_name", "title"],
        )

    if not contract.project_address:
        contract.project_address = first_value(
            project,
            ["address", "project_address", "location", "job_address"],
        )

    if not contract.project_description:
        contract.project_description = first_value(
            project,
            ["description", "scope", "notes"],
        )

    return contract


def sync_contract_snapshots(contract):
    sync_contract_company(contract)
    sync_contract_company_snapshot(contract)
    sync_contract_client_snapshot(contract)
    sync_contract_project_snapshot(contract)

    return contract


def reset_contract_financial_fields(contract):
    contract.contract_price = Decimal("0.00")
    contract.initial_payment = Decimal("0.00")
    contract.balance_due = Decimal("0.00")
    contract.state_sales_tax_rate = Decimal("0.000")
    contract.local_sales_tax_rate = Decimal("0.000")
    contract.state_sales_tax_amount = Decimal("0.00")
    contract.local_sales_tax_amount = Decimal("0.00")
    contract.total_amount_due = Decimal("0.00")

    return contract


def ensure_contract_company_matches(contract):
    if not contract.id_company:
        raise ValueError("Contract company is required.")

    if contract.id_client and contract.id_client.id_company_id != contract.id_company_id:
        raise ValueError("Client must belong to the contract company.")

    if contract.id_project and contract.id_project.id_company_id != contract.id_company_id:
        raise ValueError("Project must belong to the contract company.")

    if (
        contract.id_client
        and contract.id_project
        and contract.id_project.id_client_id
        and contract.id_project.id_client_id != contract.id_client_id
    ):
        raise ValueError("Project must belong to the selected client.")

    return True


def ensure_contract_can_be_edited(contract):
    if contract.status not in CONTRACT_EDITABLE_STATUSES:
        raise ValueError("Only draft contracts can be edited.")

    return True


def prepare_contract(contract, user=None, is_create=False):
    sync_contract_snapshots(contract)
    ensure_contract_company_matches(contract)
    reset_contract_financial_fields(contract)

    if is_create and not contract.contract_number:
        contract.contract_number = generate_contract_number(contract.id_company)

    if user and user.is_authenticated:
        if is_create and not contract.created_by:
            contract.created_by = user

        contract.updated_by = user

    now = timezone.now()
    contract.updated_at = now
    contract.last_modified_at = now

    return contract


@transaction.atomic
def contract_create_instance(contract, user=None):
    prepare_contract(
        contract=contract,
        user=user,
        is_create=True,
    )

    contract.full_clean()
    contract.save()

    return contract


@transaction.atomic
def contract_update_instance(contract, user=None):
    ensure_contract_can_be_edited(contract)

    prepare_contract(
        contract=contract,
        user=user,
        is_create=False,
    )

    contract.full_clean()
    contract.save()

    return contract


@transaction.atomic
def contract_create(**data):
    user = data.pop("user", None)
    contract = Contract(**data)

    return contract_create_instance(
        contract=contract,
        user=user,
    )


@transaction.atomic
def contract_update(contract, **data):
    user = data.pop("user", None)

    allowed_fields = [
        "id_client",
        "id_project",
        "contract_title",
        "contract_date",
        "expiration_date",
        "company_name",
        "company_phone",
        "company_email",
        "company_address",
        "company_license",
        "client_name",
        "client_phone",
        "client_alt_phone",
        "client_email",
        "client_street_address",
        "client_city",
        "client_state",
        "client_zip_code",
        "project_name",
        "project_address",
        "project_description",
        "project_photo",
        "pdf_header_dark",
        "work_to_be_done",
        "additional_work",
        "work_not_to_be_done",
        "special_instructions",
        "consumer_notice",
        "cancellation_notice",
        "terms",
        "company_representative_name",
        "company_representative_title",
        "customer_signature_name",
        "signed_date",
        "payment_terms",
        "cancellation_terms",
        "guarantee_terms",
        "miscellaneous_terms",
    ]

    for field in allowed_fields:
        if field in data:
            setattr(contract, field, data[field])

    return contract_update_instance(
        contract=contract,
        user=user,
    )


@transaction.atomic
def contract_mark_generated(contract, user=None):
    if contract.status not in [
        CONTRACT_STATUS_DRAFT,
        CONTRACT_STATUS_PENDING,
        CONTRACT_STATUS_GENERATED,
    ]:
        raise ValueError("Only draft contracts can be generated.")

    prepare_contract(
        contract=contract,
        user=user,
        is_create=False,
    )

    contract.status = CONTRACT_STATUS_GENERATED
    contract.generated_at = timezone.now()

    contract.full_clean()
    contract.save()

    return contract


@transaction.atomic
def contract_mark_sent(contract, user=None):
    if contract.status not in CONTRACT_SENDABLE_STATUSES:
        raise ValueError("Only generated, sent, viewed, or approved contracts can be sent.")

    contract.status = CONTRACT_STATUS_SENT
    contract.sent_at = timezone.now()

    if user and user.is_authenticated:
        contract.sent_by = user
        contract.updated_by = user

    contract.updated_at = timezone.now()
    contract.last_modified_at = timezone.now()

    contract.full_clean()
    contract.save(
        update_fields=[
            "status",
            "sent_at",
            "sent_by",
            "updated_by",
            "updated_at",
            "last_modified_at",
        ]
    )

    return contract

@transaction.atomic
def contract_mark_signed(contract, user=None):
    if contract.status == CONTRACT_STATUS_VOID:
        raise ValueError("Voided contracts cannot be signed.")

    contract.status = CONTRACT_STATUS_SIGNED

    if not contract.signed_date:
        contract.signed_date = timezone.localdate()

    if not contract.customer_signed_at:
        contract.customer_signed_at = timezone.now()

    if user and user.is_authenticated:
        contract.updated_by = user

    contract.updated_at = timezone.now()
    contract.last_modified_at = timezone.now()

    contract.full_clean()
    contract.save(
        update_fields=[
            "status",
            "signed_date",
            "customer_signed_at",
            "updated_by",
            "updated_at",
            "last_modified_at",
        ]
    )

    return contract


@transaction.atomic
def contract_void(contract, user=None, reason=""):
    if contract.status == CONTRACT_STATUS_VOID:
        return contract

    if contract.status == CONTRACT_STATUS_SIGNED:
        raise ValueError("Signed contracts cannot be voided from this action.")

    contract.status = CONTRACT_STATUS_VOID
    contract.voided_at = timezone.now()
    contract.void_reason = (reason or "").strip()

    if user and user.is_authenticated:
        contract.voided_by = user
        contract.updated_by = user

    contract.updated_at = timezone.now()
    contract.last_modified_at = timezone.now()

    contract.full_clean()
    contract.save(
        update_fields=[
            "status",
            "voided_at",
            "voided_by",
            "void_reason",
            "updated_by",
            "updated_at",
            "last_modified_at",
        ]
    )

    return contract


@transaction.atomic
def contract_activate(contract):
    contract.status = CONTRACT_STATUS_ACTIVE
    contract.updated_at = timezone.now()
    contract.last_modified_at = timezone.now()
    contract.full_clean()
    contract.save(
        update_fields=[
            "status",
            "updated_at",
            "last_modified_at",
        ]
    )

    return contract


@transaction.atomic
def contract_complete(contract):
    contract.status = CONTRACT_STATUS_COMPLETED
    contract.updated_at = timezone.now()
    contract.last_modified_at = timezone.now()
    contract.full_clean()
    contract.save(
        update_fields=[
            "status",
            "updated_at",
            "last_modified_at",
        ]
    )

    return contract


@transaction.atomic
def contract_cancel(contract):
    contract.status = CONTRACT_STATUS_CANCELLED
    contract.updated_at = timezone.now()
    contract.last_modified_at = timezone.now()
    contract.full_clean()
    contract.save(
        update_fields=[
            "status",
            "updated_at",
            "last_modified_at",
        ]
    )

    return contract


def get_contract_pdf_filename(contract):
    number = contract.contract_number or f"CON-{contract.id_contract}"

    return f"{number}.pdf"


def draw_wrapped_text(canvas, text, x, y, max_width, line_height, font_name="Helvetica", font_size=9):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    if not text:
        return y

    canvas.setFont(font_name, font_size)

    words = str(text).replace("\r", "").split()
    line = ""

    for word in words:
        test_line = f"{line} {word}".strip()

        if stringWidth(test_line, font_name, font_size) <= max_width:
            line = test_line
        else:
            canvas.drawString(x, y, line)
            y -= line_height
            line = word

    if line:
        canvas.drawString(x, y, line)
        y -= line_height

    return y

def draw_pdf_paragraph(pdf, text, x, y_top, width, style):
    text = (text or "").strip()

    if not text:
        return y_top

    safe_text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\r", "")
        .replace("\n\n", "<br/><br/>")
        .replace("\n", "<br/>")
    )

    paragraph = Paragraph(safe_text, style)
    paragraph_width, paragraph_height = paragraph.wrap(width, 1000)
    paragraph.drawOn(pdf, x, y_top - paragraph_height)

    return y_top - paragraph_height
def draw_contract_terms_page(pdf, contract, width, height, margin, inch):
    pdf.showPage()

    y = height - margin
    content_width = width - (margin * 2)

    title_style = ParagraphStyle(
        name="ContractTermsTitle",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        name="ContractTermsBody",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.8,
        alignment=TA_JUSTIFY,
        spaceAfter=10,
    )

    is_spanish = get_company_language(contract) == "es"
    sections = [
        (
            ui("Payment Terms and Conditions").upper(),
            contract.payment_terms or (DEFAULT_PAYMENT_TERMS_ES if is_spanish else DEFAULT_PAYMENT_TERMS),
        ),
        (
            ui("Cancellation").upper(),
            contract.cancellation_terms or (DEFAULT_CANCELLATION_TERMS_ES if is_spanish else DEFAULT_CANCELLATION_TERMS),
        ),
        (
            ui("Guarantee").upper(),
            contract.guarantee_terms or (DEFAULT_GUARANTEE_TERMS_ES if is_spanish else DEFAULT_GUARANTEE_TERMS),
        ),
        (
            ui("Miscellaneous Terms").upper(),
            contract.miscellaneous_terms or (DEFAULT_MISCELLANEOUS_TERMS_ES if is_spanish else DEFAULT_MISCELLANEOUS_TERMS),
        ),
    ]

    for title, text in sections:
        y = draw_pdf_paragraph(
            pdf=pdf,
            text=title,
            x=margin,
            y_top=y,
            width=content_width,
            style=title_style,
        )

        y -= 0.06 * inch

        y = draw_pdf_paragraph(
            pdf=pdf,
            text=text,
            x=margin,
            y_top=y,
            width=content_width,
            style=body_style,
        )

        y -= 0.10 * inch

        if y < margin + 0.75 * inch:
            pdf.showPage()
            y = height - margin

    return y

def _contract_safe_image_path(value):
    if not value:
        return None
    try:
        path = value.path if hasattr(value, "path") else str(value)
    except (ValueError, NotImplementedError, AttributeError):
        return None
    return path if path and os.path.exists(path) else None


def _contract_company_logo_path(contract):
    company = getattr(contract, "id_company", None)
    logo = getattr(company, "logo", None)
    return _contract_safe_image_path(logo)


@use_company_language
def build_contract_pdf_bytes(contract):
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
    except Exception as error:
        raise ValueError(f"{ui('ReportLab is required to generate contract PDFs')}: {error}")

    prepare_contract(
        contract=contract,
        user=None,
        is_create=False,
    )

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    margin = 0.45 * inch
    y = height - margin

    use_dark_header = bool(getattr(contract, "pdf_header_dark", False))
    if use_dark_header:
        pdf.setFillColorRGB(0.05, 0.08, 0.16)
        pdf.rect(0, height - 1.25 * inch, width, 1.25 * inch, fill=1, stroke=0)
        text_color = (1, 1, 1)
    else:
        pdf.setFillColorRGB(1, 1, 1)
        pdf.rect(0, height - 1.25 * inch, width, 1.25 * inch, fill=1, stroke=0)
        pdf.setStrokeColorRGB(0.88, 0.90, 0.94)
        pdf.line(0, height - 1.25 * inch, width, height - 1.25 * inch)
        text_color = (0.05, 0.08, 0.16)

    logo_path = _contract_company_logo_path(contract)
    header_x = margin
    if logo_path:
        try:
            pdf.setFillColorRGB(1, 1, 1)
            pdf.roundRect(margin, height - 1.03 * inch, 1.18 * inch, 0.70 * inch, 6, fill=1, stroke=0)
            image = ImageReader(logo_path)
            image_width, image_height = image.getSize()
            max_width = 0.94 * inch
            max_height = 0.48 * inch
            scale = min(max_width / image_width, max_height / image_height)
            draw_width = image_width * scale
            draw_height = image_height * scale
            pdf.drawImage(image, margin + (1.18 * inch - draw_width) / 2, height - 1.03 * inch + (0.70 * inch - draw_height) / 2, width=draw_width, height=draw_height, mask="auto")
            header_x = margin + 1.38 * inch
        except Exception:
            header_x = margin

    pdf.setFillColorRGB(*text_color)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(header_x, height - 0.42 * inch, contract.company_name or ui("Company"))

    pdf.setFont("Helvetica", 8)
    pdf.drawString(header_x, height - 0.65 * inch, contract.company_phone or "")
    pdf.drawString(header_x, height - 0.82 * inch, contract.company_email or "")
    pdf.drawString(header_x, height - 0.99 * inch, contract.company_address or "")

    pdf.setFillColorRGB(*text_color)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(width - margin, height - 0.42 * inch, contract.contract_number or f"{ui('Contract')} {contract.id_contract}")

    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(width - margin, height - 0.65 * inch, f"{ui('Date')}: {date_format(contract.contract_date, format='DATE_FORMAT', use_l10n=True) if contract.contract_date else '-'}")
    pdf.drawRightString(width - margin, height - 0.82 * inch, f"{ui('Status')}: {ui(contract.get_status_display())}")

    y = height - 1.55 * inch

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin, y, ui("Customer Information"))
    y -= 0.18 * inch

    pdf.setFont("Helvetica", 8)
    pdf.drawString(margin, y, f"{ui('Customer Name')}: {contract.client_name or '-'}")
    pdf.drawString(width / 2, y, f"{ui('Phone')}: {contract.client_phone or '-'}")
    y -= 0.16 * inch

    pdf.drawString(margin, y, f"{ui('Email')}: {contract.client_email or '-'}")
    pdf.drawString(width / 2, y, f"{ui('Alternate Phone')}: {contract.client_alt_phone or '-'}")
    y -= 0.16 * inch

    pdf.drawString(margin, y, f"{ui('Address')}: {contract.client_full_address or '-'}")
    y -= 0.28 * inch

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin, y, ui("Description of Project and Materials"))
    y -= 0.18 * inch

    pdf.setFont("Helvetica", 8)
    pdf.drawString(margin, y, f"{ui('Project')}: {contract.project_name or '-'}")
    y -= 0.15 * inch

    pdf.drawString(margin, y, f"{ui('Project Address')}: {contract.project_address or '-'}")
    y -= 0.22 * inch

    project_photo_path = _contract_safe_image_path(getattr(contract, "project_photo", None))
    if project_photo_path:
        try:
            image = ImageReader(project_photo_path)
            image_width, image_height = image.getSize()
            max_width = 2.1 * inch
            max_height = 1.35 * inch
            scale = min(max_width / image_width, max_height / image_height)
            draw_width = image_width * scale
            draw_height = image_height * scale
            if y - draw_height < 1.3 * inch:
                pdf.showPage()
                y = height - margin
            pdf.drawImage(image, margin, y - draw_height, width=draw_width, height=draw_height, mask="auto")
            y -= draw_height + 0.18 * inch
        except Exception:
            pass

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, f"{ui('Work to be done')}:")
    y -= 0.15 * inch
    y = draw_wrapped_text(
        pdf,
        contract.work_to_be_done or contract.project_description or contract.terms or "-",
        margin,
        y,
        width - (margin * 2),
        11,
        "Helvetica",
        8,
    )

    y -= 0.05 * inch
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, f"{ui('Additional work to be done')}:")
    y -= 0.15 * inch
    y = draw_wrapped_text(
        pdf,
        contract.additional_work or "-",
        margin,
        y,
        width - (margin * 2),
        11,
        "Helvetica",
        8,
    )

    y -= 0.05 * inch
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, f"{ui('Work NOT to be done')}:")
    y -= 0.15 * inch
    y = draw_wrapped_text(
        pdf,
        contract.work_not_to_be_done or "-",
        margin,
        y,
        width - (margin * 2),
        11,
        "Helvetica",
        8,
    )

    y -= 0.05 * inch
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, f"{ui('Special Instructions')}:")
    y -= 0.15 * inch
    y = draw_wrapped_text(
        pdf,
        contract.special_instructions or "-",
        margin,
        y,
        width - (margin * 2),
        11,
        "Helvetica",
        8,
    )

    if y < 2.8 * inch:
        pdf.showPage()
        y = height - margin

    y -= 0.1 * inch
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, f"{ui('Notice to Consumer')}:")
    y -= 0.15 * inch
    y = draw_wrapped_text(
        pdf,
        contract.consumer_notice or "-",
        margin,
        y,
        width - (margin * 2),
        10,
        "Helvetica",
        7,
    )

    y -= 0.1 * inch
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, f"{ui('Cancellation Notice')}:")
    y -= 0.15 * inch
    y = draw_wrapped_text(
        pdf,
        contract.cancellation_notice or "-",
        margin,
        y,
        width - (margin * 2),
        10,
        "Helvetica",
        7,
    )

    if y < 2.1 * inch:
        pdf.showPage()
        y = height - margin

    y -= 0.1 * inch
    
    if y < 2.8 * inch:
        pdf.showPage()
        y = height - margin

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin, y, ui("Signatures"))

    y -= 0.28 * inch

    signature_box_x = margin
    signature_box_y = y - 1.45 * inch
    signature_box_width = 3.65 * inch
    signature_box_height = 1.35 * inch

    info_box_x = margin + 3.95 * inch
    info_box_y = signature_box_y
    info_box_width = width - margin - info_box_x
    info_box_height = signature_box_height

    pdf.setStrokeColorRGB(0.80, 0.84, 0.90)
    pdf.setFillColorRGB(1, 1, 1)

    pdf.roundRect(
        signature_box_x,
        signature_box_y,
        signature_box_width,
        signature_box_height,
        8,
        fill=0,
        stroke=1,
    )

    pdf.roundRect(
        info_box_x,
        info_box_y,
        info_box_width,
        info_box_height,
        8,
        fill=0,
        stroke=1,
    )

    pdf.setFillColorRGB(0.38, 0.43, 0.51)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(signature_box_x + 0.12 * inch, signature_box_y + signature_box_height - 0.20 * inch, ui("Customer Signature").upper())

    signature_file = getattr(contract, "signature_image", None)

    if signature_file:
        try:
            from reportlab.lib.utils import ImageReader

            signature_path = signature_file.path
            signature_reader = ImageReader(signature_path)

            image_width, image_height = signature_reader.getSize()

            max_draw_width = signature_box_width - 0.35 * inch
            max_draw_height = signature_box_height - 0.45 * inch

            scale = min(
                max_draw_width / image_width,
                max_draw_height / image_height,
            )

            draw_width = image_width * scale
            draw_height = image_height * scale

            draw_x = signature_box_x + (signature_box_width - draw_width) / 2
            draw_y = signature_box_y + 0.14 * inch

            pdf.drawImage(
                signature_reader,
                draw_x,
                draw_y,
                width=draw_width,
                height=draw_height,
                mask="auto",
            )

        except Exception:
            pdf.setFillColorRGB(0, 0, 0)
            pdf.setFont("Helvetica", 8)
            pdf.drawString(signature_box_x + 0.12 * inch, signature_box_y + 0.55 * inch, ui("Signature image could not be loaded."))
    else:
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(signature_box_x + 0.12 * inch, signature_box_y + 0.55 * inch, ui("No signature available."))

    signed_date = getattr(contract, "sign_token_used_at", None) or getattr(contract, "signed_date", None)
    customer_signature_name = (
        getattr(contract, "customer_signature_name", "")
        or getattr(contract, "client_name", "")
        or "-"
    )

    pdf.setFillColorRGB(0.38, 0.43, 0.51)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(info_box_x + 0.12 * inch, info_box_y + info_box_height - 0.20 * inch, ui("Customer Signature Name").upper())

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(info_box_x + 0.12 * inch, info_box_y + info_box_height - 0.45 * inch, customer_signature_name)

    pdf.setFillColorRGB(0.38, 0.43, 0.51)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(info_box_x + 0.12 * inch, info_box_y + info_box_height - 0.78 * inch, ui("Signed Date").upper())

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 9)

    if signed_date:
        pdf.drawString(
            info_box_x + 0.12 * inch,
            info_box_y + info_box_height - 1.03 * inch,
            date_format(signed_date, format="DATETIME_FORMAT", use_l10n=True),
        )
    else:
        pdf.drawString(
            info_box_x + 0.12 * inch,
            info_box_y + info_box_height - 1.03 * inch,
            "-",
        )

    y = signature_box_y - 0.30 * inch
  

    draw_contract_terms_page(
        pdf=pdf,
        contract=contract,
        width=width,
        height=height,
        margin=margin,
        inch=inch,
    )


    evidence_photos = []

    if getattr(contract, "id_contract", None):
        try:
            evidence_photos = list(contract.evidence_photos.all())
        except Exception:
            evidence_photos = []


 
    if evidence_photos:
     
        evidence_page_size = landscape(letter)
        evidence_width, evidence_height = evidence_page_size
      

        photos_per_page = 4
        columns = 2
        rows = 2

        margin_x = 0.55 * inch
        margin_top = 0.55 * inch
        margin_bottom = 0.45 * inch
        gap_x = 0.30 * inch
        gap_y = 0.30 * inch

        for page_start in range(0, len(evidence_photos), photos_per_page):
            photos = evidence_photos[page_start:page_start + photos_per_page]

            pdf.showPage()
            pdf.setPageSize(evidence_page_size)

            title_y = evidence_height - margin_top
            content_top = title_y - 0.50 * inch

            pdf.setFillColorRGB(0.05, 0.08, 0.16)
            pdf.setFont("Helvetica-Bold", 18)
            pdf.drawString(margin_x, title_y, ui("Evidence Photos / Annexes"))

            pdf.setFillColorRGB(0.38, 0.43, 0.51)
            pdf.setFont("Helvetica", 9)
            pdf.drawString(
                margin_x,
                title_y - 0.20 * inch,
                ui("Evidence photos attached to this contract."),
            )

            usable_width = evidence_width - (margin_x * 2)
            usable_height = content_top - margin_bottom

            cell_width = (usable_width - gap_x) / columns
            cell_height = (usable_height - gap_y) / rows

            for index, evidence in enumerate(photos):
                image_path = _contract_safe_image_path(evidence.image)

                if not image_path:
                    continue

                row = index // columns
                col = index % columns

                x = margin_x + (col * (cell_width + gap_x))
                y_cell = content_top - ((row + 1) * cell_height) - (row * gap_y)

                pdf.setFillColorRGB(1, 1, 1)
                pdf.setStrokeColorRGB(0.80, 0.84, 0.90)
                pdf.roundRect(
                    x,
                    y_cell,
                    cell_width,
                    cell_height,
                    10,
                    fill=1,
                    stroke=1,
                )

                padding = 0.14 * inch
                caption_height = 0.34 * inch

                image_box_x = x + padding
                image_box_y = y_cell + caption_height + padding
                image_box_width = cell_width - (padding * 2)
                image_box_height = cell_height - caption_height - (padding * 2)

                try:
                    image = ImageReader(image_path)
                    image_width, image_height = image.getSize()
                    image_width, image_height = image.getSize()

                    scale = min(
                        image_box_width / image_width,
                        image_box_height / image_height,
                    )

                    draw_width = image_width * scale
                    draw_height = image_height * scale

                    draw_x = image_box_x + (image_box_width - draw_width) / 2
                    draw_y = image_box_y + (image_box_height - draw_height) / 2

                    pdf.drawImage(
                        image,
                        draw_x,
                        draw_y,
                        width=draw_width,
                        height=draw_height,
                        mask="auto",
                    )

                except Exception:
                    pdf.setFillColorRGB(0, 0, 0)
                    pdf.setFont("Helvetica", 8)
                    pdf.drawString(
                        x + 0.16 * inch,
                        y_cell + 0.50 * inch,
                        ui("Image could not be loaded."),
                    )

                pdf.setFillColorRGB(0.05, 0.08, 0.16)
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(
                    x + 0.16 * inch,
                    y_cell + 0.16 * inch,
                    f"{ui('Photo')} {page_start + index + 1}",
                )

   
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()

def contract_pdf_response(contract):
    pdf_bytes = build_contract_pdf_bytes(contract)
    filename = get_contract_pdf_filename(contract)

    response = HttpResponse(
        pdf_bytes,
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response


@use_company_language
@transaction.atomic
def send_contract_to_email(contract, recipient_email, subject="", message="", user=None, public_contract_url=""):
    if contract.status == CONTRACT_STATUS_DRAFT:
        contract_mark_generated(
            contract=contract,
            user=user,
        )

    if contract.status not in CONTRACT_SENDABLE_STATUSES:
        raise ValueError("Only generated, sent, viewed, or approved contracts can be emailed.")

    recipient_email = (recipient_email or contract.client_email or "").strip()

    if not recipient_email:
        raise ValueError("Recipient email is required.")

    subject = (subject or "").strip()

    if not subject:
        subject = f"{ui('Contract')} {contract.contract_number or contract.id_contract}"

    public_contract_url = (public_contract_url or "").strip()
    contract_number = contract.contract_number or contract.id_contract
    company_name = contract.company_name or getattr(contract.id_company, "name", "") or ui("Our Team")
    client_name = contract.client_name or getattr(contract.id_client, "name", "") or ui("Customer")
    project_name = contract.project_name or getattr(contract.id_project, "project_name", "") or ui("your project")

    custom_message = (message or "").strip()

    text_body = custom_message or (
        f"{ui('Hello')} {client_name},\n\n"
        f"{ui('Please review the contract')} {contract_number} {ui('for')} {project_name}.\n"
    )

    if public_contract_url:
        text_body += (
            f"\n{ui('You can review, approve, or reject the contract using this secure link:')}\n"
            f"{public_contract_url}\n\n"
            f"{ui('This link does not require a CRM login.')}\n"
        )

    # PDF note is added after the PDF size is known.

    try:
        from apps.smtp_settings.services import (
            build_smtp_connection,
            get_active_smtp_setting_for_company,
            get_from_email,
            validate_smtp_setting,
        )
    except Exception as error:
        raise ValueError(f"SMTP service is not available: {error}")

    smtp_setting = get_active_smtp_setting_for_company(contract.id_company)
    validate_smtp_setting(smtp_setting)

    connection = build_smtp_connection(smtp_setting)
    from_email = get_from_email(smtp_setting)

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

    max_attachment_bytes = 18 * 1024 * 1024
    pdf_size_mb = round(len(pdf_bytes) / 1024 / 1024, 2)
    attach_pdf = len(pdf_bytes) <= max_attachment_bytes

    if attach_pdf:
        text_body += (
            f"\n{ui('A PDF copy of the contract is attached for your records.')}\n\n"
            f"{ui('Thank you')},\n{company_name}"
        )
        pdf_html_note = ui("A PDF copy is attached for your records.")
    else:
        text_body += (
            f"\n{ui('The PDF copy is available through the secure contract link above.')} "
            f"{ui('It was not attached because the file is large')} ({pdf_size_mb} MB).\n\n"
            f"{ui('Thank you')},\n{company_name}"
        )
        pdf_html_note = (
            f"{ui('The PDF was not attached because the file is large')} ({pdf_size_mb} MB). "
            f"{ui('Please use the secure contract link to review the full contract.')}"
        )

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[recipient_email],
        connection=connection,
    )

    if public_contract_url:
        html_body = f"""
        <div style="margin:0;padding:0;background:#f3f6fb;font-family:Arial,sans-serif;color:#111827;">
          <div style="max-width:680px;margin:0 auto;padding:32px 18px;">
            <div style="background:#ffffff;border-radius:22px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:0 18px 50px rgba(15,23,42,.10);">
              <div style="background:#0f172a;color:#ffffff;padding:28px;">
                <h1 style="margin:0;font-size:28px;line-height:1.2;">{ui("Contract Ready For Review")}</h1>
                <p style="margin:10px 0 0;color:#dbeafe;font-size:15px;">{company_name}</p>
              </div>

              <div style="padding:28px;">
                <p style="margin:0 0 16px;font-size:16px;line-height:1.6;">
                  {ui("Hello")} <strong>{client_name}</strong>,
                </p>

                <p style="margin:0 0 16px;font-size:16px;line-height:1.6;">
                  {ui("Please review the contract for")} <strong>{project_name}</strong>.
                </p>

                <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:16px;padding:18px;margin:20px 0;">
                  <p style="margin:0 0 8px;font-size:14px;color:#6b7280;">{ui("Contract Number")}</p>
                  <p style="margin:0;font-size:20px;font-weight:800;color:#111827;">{contract_number}</p>
                </div>

                <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:16px;padding:18px;margin:20px 0;">
                  <p style="margin:0 0 8px;font-size:14px;color:#1e3a8a;">{ui("Total Amount Due")}</p>
                  <p style="margin:0;font-size:30px;font-weight:900;color:#0f172a;">${contract.total_amount_due}</p>
                </div>

                <p style="margin:0 0 22px;font-size:16px;line-height:1.6;">
                  {ui("Use the secure button below to review, approve, or reject the contract. No CRM login is required.")}
                </p>

                <p style="margin:26px 0;text-align:center;">
                  <a href="{public_contract_url}" target="_blank" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:14px 26px;border-radius:999px;font-weight:800;">
                    {ui("View Contract")}
                  </a>
                </p>

                <p style="margin:22px 0 0;font-size:14px;line-height:1.6;color:#6b7280;">
                  {pdf_html_note}
                </p>
              </div>
            </div>
          </div>
        </div>
        """

        email.attach_alternative(html_body, "text/html")

    if attach_pdf:
        email.attach(
            filename,
            pdf_bytes,
            "application/pdf",
        )

    sent_count = email.send()

    if sent_count <= 0:
        raise ValueError("The contract email could not be sent.")

    contract_mark_sent(
        contract=contract,
        user=user,
    )

    return sent_count
def create_contracts(**data):
    return contract_create(**data)


def update_contracts(instance, **data):
    return contract_update(instance, **data)