from celery import shared_task


@shared_task
def generate_report_placeholder(company_id):
    return {"company_id": company_id, "status": "ready"}
