from django.core.mail import EmailMultiAlternatives


def _safe_email(value):
    value = (value or "").strip().lower()
    return value if "@" in value else ""


def _get_object_email(obj):
    if not obj:
        return ""

    email = _safe_email(getattr(obj, "email", ""))

    if email:
        return email

    user = getattr(obj, "id_user", None) or getattr(obj, "user", None)

    if user:
        return _safe_email(getattr(user, "email", ""))

    return ""


def get_project_related_emails(project, exclude_email=""):
    exclude_email = _safe_email(exclude_email)
    emails = set()

    inspector = getattr(project, "id_inspector", None)

    inspector_email = _get_object_email(inspector)

    if inspector_email:
        emails.add(inspector_email)

    possible_assignment_managers = [
        "assignments",
        "project_assignments",
        "projectassignment_set",
    ]

    for related_name in possible_assignment_managers:
        manager = getattr(project, related_name, None)

        if not manager:
            continue

        try:
            assignments = manager.all()
        except Exception:
            continue

        for assignment in assignments:
            possible_people = [
                getattr(assignment, "id_user", None),
                getattr(assignment, "user", None),
                getattr(assignment, "id_employee", None),
                getattr(assignment, "employee", None),
                getattr(assignment, "assigned_user", None),
            ]

            for person in possible_people:
                email = _get_object_email(person)

                if email:
                    emails.add(email)

    if exclude_email and exclude_email in emails:
        emails.remove(exclude_email)

    return sorted(emails)


def send_project_status_changed_email(project, old_status, new_status, changed_by=None, request=None):
    recipients = get_project_related_emails(
    project=project,
    )

    if not recipients:
        return 0

    company = getattr(project, "id_company", None)
    company_name = getattr(company, "name", "") or "CRM Team"

    project_code = getattr(project, "project_code", "") or getattr(project, "id_project", "")
    project_name = getattr(project, "name", "") or getattr(project, "project_name", "") or "Project"

    changed_by_email = getattr(changed_by, "email", "") or "A CRM user"

    project_url = ""

    if request:
        company_slug = getattr(company, "slug", "") or ""

        if company_slug:
            project_path = f"/{str(company_slug).strip('/')}/projects/{project.id_project}/"
        else:
            project_path = f"/projects/{project.id_project}/"

        project_url = request.build_absolute_uri(project_path)

    subject = f"Project Status Updated - {project_code}"

    text_body = (
        f"Project status updated.\n\n"
        f"Project: {project_name}\n"
        f"Project Code: {project_code}\n"
        f"Previous Status: {old_status}\n"
        f"New Status: {new_status}\n"
        f"Changed By: {changed_by_email}\n"
    )

    if project_url:
        text_body += f"\nView project:\n{project_url}\n"

    html_body = f"""
    <div style="margin:0;padding:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#111827;">
      <div style="max-width:680px;margin:0 auto;padding:28px 18px;">
        <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:18px;overflow:hidden;">
          <div style="background:#1f3a8a;color:#ffffff;padding:24px;">
            <h1 style="margin:0;font-size:24px;line-height:1.25;">Project Status Updated</h1>
            <p style="margin:8px 0 0;color:#dbeafe;">{company_name}</p>
          </div>

          <div style="padding:24px;">
            <p style="margin:0 0 14px;font-size:16px;line-height:1.6;">
              The status of the project <strong>{project_code}</strong> has been updated.
            </p>

            <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:14px;padding:16px;margin:18px 0;">
              <p style="margin:0 0 8px;"><strong>Project:</strong> {project_name}</p>
              <p style="margin:0 0 8px;"><strong>Previous Status:</strong> {old_status}</p>
              <p style="margin:0 0 8px;"><strong>New Status:</strong> {new_status}</p>
              <p style="margin:0;"><strong>Changed By:</strong> {changed_by_email}</p>
            </div>
    """

    if project_url:
        html_body += f"""
            <p style="margin:24px 0;text-align:center;">
              <a href="{project_url}" target="_blank" style="display:inline-block;background:#1f3a8a;color:#ffffff;text-decoration:none;padding:13px 22px;border-radius:999px;font-weight:800;">
                View Project
              </a>
            </p>
        """

    html_body += """
          </div>
        </div>
      </div>
    </div>
    """

    try:
        from apps.smtp_settings.services import (
            build_smtp_connection,
            get_active_smtp_setting_for_company,
            get_from_email,
            validate_smtp_setting,
        )

        smtp_setting = get_active_smtp_setting_for_company(company)
        validate_smtp_setting(smtp_setting)

        connection = build_smtp_connection(smtp_setting)
        from_email = get_from_email(smtp_setting)

    except Exception as error:
        raise ValueError(f"SMTP service is not available or not configured: {error}")

    sent_total = 0

    for recipient in recipients:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[recipient],
            connection=connection,
        )

        email.attach_alternative(html_body, "text/html")

        sent_total += email.send()

    return sent_total