import csv

from django.http import HttpResponse

from apps.core.pdf import simple_pdf_response

from .selectors import (
    get_financial_summary,
    get_payment_summary,
    get_project_summary,
)


def build_financial_summary_rows(user):
    summary = get_financial_summary(user)

    return [
        ["Metric", "Value"],
        ["Company", summary["company"].name if summary["company"] else "All Companies"],
        ["Total Clients", summary["total_clients"]],
        ["Total Leads", summary["total_leads"]],
        ["Total Projects", summary["total_projects"]],
        ["Active Projects", summary["active_projects"]],
        ["Total Estimates", summary["total_estimates"]],
        ["Total Estimated", summary["total_estimated"]],
        ["Total Invoices", summary["total_invoices"]],
        ["Total Billed", summary["total_billed"]],
        ["Total Balance", summary["total_balance"]],
        ["Total Payments", summary["total_payments"]],
        ["Total Paid", summary["total_paid"]],
        ["Pending Payments", summary["pending_payments"]],
        ["Verified Payments", summary["verified_payments"]],
    ]


def build_projects_summary_rows(user):
    summary = get_project_summary(user)

    return [
        ["Metric", "Value"],
        ["Total Projects", summary["total_projects"]],
        ["Pending Projects", summary["pending_projects"]],
        ["Active Projects", summary["active_projects"]],
        ["Completed Projects", summary["completed_projects"]],
        ["Cancelled Projects", summary["cancelled_projects"]],
    ]


def build_payments_summary_rows(user):
    summary = get_payment_summary(user)

    return [
        ["Metric", "Value"],
        ["Total Payments", summary["total_payments"]],
        ["Pending Payments", summary["pending_payments"]],
        ["Paid Payments", summary["paid_payments"]],
        ["Verified Payments", summary["verified_payments"]],
        ["Rejected Payments", summary["rejected_payments"]],
        ["Cancelled Payments", summary["cancelled_payments"]],
        ["Total Paid", summary["total_paid"]],
    ]


def csv_response(filename, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    safe_filename = filename.replace('"', "").replace("\r", "").replace("\n", "")
    response["Content-Disposition"] = f'attachment; filename="{safe_filename}"'
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response.write("\ufeff")

    writer = csv.writer(response)

    for row in rows:
        writer.writerow(row)

    return response


def financial_summary_csv_response(user):
    return csv_response(
        "financial-summary.csv",
        build_financial_summary_rows(user),
    )


def projects_summary_csv_response(user):
    return csv_response(
        "projects-summary.csv",
        build_projects_summary_rows(user),
    )


def payments_summary_csv_response(user):
    return csv_response(
        "payments-summary.csv",
        build_payments_summary_rows(user),
    )


def financial_summary_pdf_response(user):
    rows = build_financial_summary_rows(user)
    lines = [f"{row[0]}: {row[1]}" for row in rows[1:]]

    return simple_pdf_response(
        "Financial Summary",
        lines,
        filename="financial-summary.pdf",
    )
