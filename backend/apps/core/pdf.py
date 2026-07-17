from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def simple_pdf_response(title, lines, filename="document.pdf"):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 60
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, title)
    y -= 35
    pdf.setFont("Helvetica", 10)
    for line in lines:
        if y < 60:
            pdf.showPage()
            y = height - 60
            pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y, str(line))
        y -= 18
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
