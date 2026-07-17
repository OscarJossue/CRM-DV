from django.urls import path

from .views import (
    FinancialSummaryCSVView,
    FinancialSummaryPDFView,
    PaymentsSummaryCSVView,
    ProjectsSummaryCSVView,
    ReportsDetailView,
    ReportsHomeView,
)

app_name = "reports"

urlpatterns = [
    path("", ReportsHomeView.as_view(), name="reports_home"),
    path("financial-summary/", ReportsDetailView.as_view(), name="financial_summary"),
    path(
        "financial-summary.csv",
        FinancialSummaryCSVView.as_view(),
        name="financial_summary_csv",
    ),
    path(
        "financial-summary.pdf",
        FinancialSummaryPDFView.as_view(),
        name="financial_summary_pdf",
    ),
    path(
        "projects-summary.csv",
        ProjectsSummaryCSVView.as_view(),
        name="projects_summary_csv",
    ),
    path(
        "payments-summary.csv",
        PaymentsSummaryCSVView.as_view(),
        name="payments_summary_csv",
    ),
]
