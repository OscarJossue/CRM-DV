from celery import shared_task

from .services import purge_expired_system_logs


@shared_task(name="audit.purge_expired_system_logs")
def purge_expired_system_logs_task():
    return purge_expired_system_logs()
