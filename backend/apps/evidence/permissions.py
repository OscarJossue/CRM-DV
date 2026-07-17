from apps.core.permissions import HasModulePermission


class EvidenceFilePermission(HasModulePermission):
    pass


def user_can_access_evidence_file(user, evidence_file):
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return evidence_file.id_project.id_company_id == user.id_company_id
