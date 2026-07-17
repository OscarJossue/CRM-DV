from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import UserAccount

from .services import sync_employee_profile


@receiver(post_save, sender=UserAccount, dispatch_uid="employees.sync_user_profile")
def keep_employee_profile_in_sync(sender, instance, raw=False, **kwargs):
    if raw:
        return
    sync_employee_profile(instance)
