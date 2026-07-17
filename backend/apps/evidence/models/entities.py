from django.db import models


class EvidenceFile(models.Model):
    id_file = models.BigAutoField(primary_key=True)
    id_project = models.ForeignKey("projects.Project", db_column="id_project", on_delete=models.CASCADE, related_name="evidence_files")
    id_user = models.ForeignKey("accounts.UserAccount", db_column="id_user", on_delete=models.CASCADE, related_name="evidence_files")
    file_type = models.CharField(max_length=100, blank=True, null=True)
    file_url = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evidence_file"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Evidence {self.id_file}"
