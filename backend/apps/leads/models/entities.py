from django.db import models


class Lead(models.Model):
    id_lead = models.BigAutoField(primary_key=True)
    id_company = models.ForeignKey("companies.Company", db_column="id_company", on_delete=models.CASCADE, related_name="leads")
    id_assigned_user = models.ForeignKey("accounts.UserAccount", db_column="id_assigned_user", on_delete=models.SET_NULL, related_name="assigned_leads", blank=True, null=True)
    id_converted_client = models.ForeignKey("clients.Client", db_column="id_converted_client", on_delete=models.SET_NULL, related_name="converted_leads", blank=True, null=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(max_length=150, blank=True, null=True)
    source = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default="new")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lead"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
