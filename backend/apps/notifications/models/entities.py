from django.db import models


class Notification(models.Model):
    id_notification = models.BigAutoField(primary_key=True)
    id_user = models.ForeignKey("accounts.UserAccount", db_column="id_user", on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=150, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default="unread")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or f"Notification {self.id_notification}"
