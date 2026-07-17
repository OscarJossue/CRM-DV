from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.core.access_policy import (
    ACCESS_COMPANY_INACTIVE,
    ACCESS_COMPANY_MISSING,
    ACCESS_USER_INACTIVE,
    ACCESS_USER_STATUS_INACTIVE,
    get_user_runtime_access_code,
)

from .models import Role, UserAccount
from .security import (
    clear_login_failures,
    login_is_throttled,
    register_login_failure,
)
from .models.choices import STATUS_ACTIVE, STATUS_INACTIVE


def get_company_user_limit(company):
    if not company:
        return 0

    try:
        limit = int(getattr(company, "user_limit", 0) or 0)
    except (TypeError, ValueError):
        limit = 0

    return max(limit, 0)


def get_company_active_user_count(company):
    if not company:
        return 0

    return UserAccount.objects.filter(
        id_company=company,
        is_active=True,
    ).count()


def company_active_user_limit_reached(company):
    limit = get_company_user_limit(company)

    if limit <= 0:
        return False

    active_users = get_company_active_user_count(company)

    return active_users >= limit


def get_company_user_limit_message(company):
    limit = get_company_user_limit(company)
    active_users = get_company_active_user_count(company)

    return (
        f"This company has reached its user limit. "
        f"Active users: {active_users}/{limit}. "
        "Upgrade the SaaS plan or deactivate another user before creating a new active user."
    )


class CRMLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(
            attrs={
                "class": "crm_input",
                "placeholder": _("email@company.com"),
                "autocomplete": "email",
            }
        ),
    )

    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": _("Password"),
                "autocomplete": "current-password",
            }
        ),
    )

    error_messages = {
        "invalid_login": _("Please enter a correct email and password."),
        "inactive": _("This user account is suspended or inactive. Contact your administrator."),
        "missing_company": _("This user is not assigned to a company. Contact the platform administrator."),
        "inactive_company": _("This company account is inactive or suspended. Please contact CEO Marketing support."),
    }

    def raise_runtime_access_error(self, user):
        access_code = get_user_runtime_access_code(user)

        if access_code in {ACCESS_USER_INACTIVE, ACCESS_USER_STATUS_INACTIVE}:
            raise ValidationError(
                self.error_messages["inactive"],
                code="inactive",
            )

        if access_code == ACCESS_COMPANY_MISSING:
            raise ValidationError(
                self.error_messages["missing_company"],
                code="missing_company",
            )

        if access_code == ACCESS_COMPANY_INACTIVE:
            raise ValidationError(
                self.error_messages["inactive_company"],
                code="inactive_company",
            )

    def clean(self):
        email = (self.cleaned_data.get("username") or "").strip().lower()
        password = self.cleaned_data.get("password")

        if email and password:
            if login_is_throttled(self.request, email):
                raise ValidationError(
                    _("Too many unsuccessful sign-in attempts. Wait a few minutes and try again."),
                    code="login_throttled",
                )

            existing_user = (
                UserAccount.objects.select_related("id_company")
                .filter(email__iexact=email)
                .first()
            )

            # Show a precise status error only after the supplied password is
            # confirmed. This avoids leaking account state for arbitrary emails.
            if existing_user and existing_user.check_password(password):
                clear_login_failures(self.request, email)
                self.raise_runtime_access_error(existing_user)

            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password,
            )

            if self.user_cache is None:
                register_login_failure(self.request, email)
                raise self.get_invalid_login_error()

            clear_login_failures(self.request, email)
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        self.raise_runtime_access_error(user)


class CRMPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].widget.attrs.update(
            {
                "class": "crm_input",
                "placeholder": "email@company.com",
                "autocomplete": "email",
            }
        )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if not email:
            raise forms.ValidationError("Email is required.")

        user = (
            UserAccount.objects.select_related("id_company")
            .filter(email__iexact=email)
            .first()
        )

        if not user:
            raise forms.ValidationError(
                "No CRM account was found with this email. Check the email or contact support."
            )

        access_code = get_user_runtime_access_code(user)

        if access_code in {ACCESS_USER_INACTIVE, ACCESS_USER_STATUS_INACTIVE}:
            raise forms.ValidationError(
                "This user account is inactive or suspended. Contact support before resetting the password."
            )

        if access_code == ACCESS_COMPANY_MISSING:
            raise forms.ValidationError(
                "This user is not assigned to a company. Contact the platform administrator."
            )

        if access_code == ACCESS_COMPANY_INACTIVE:
            raise forms.ValidationError(
                "This company account is inactive or suspended. Contact support before resetting the password."
            )

        if not user.has_usable_password():
            raise forms.ValidationError(
                "This account does not have a usable password. Contact support."
            )

        return email

    def get_users(self, email):
        users = UserAccount.objects.filter(
            email__iexact=email,
            is_active=True,
            status=STATUS_ACTIVE,
        ).select_related("id_company")

        for user in users:
            if get_user_runtime_access_code(user) != "allowed":
                continue

            if user.has_usable_password():
                yield user


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = [
            "name",
            "description",
            "is_contractor_only",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Supervisor, Accounting, Estimator...",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Describe what this role can do.",
                }
            ),
            "is_contractor_only": forms.CheckboxInput(
                attrs={
                    "class": "crm_checkbox",
                    "data-contractor-role": "1",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user

        self.fields["name"].required = True
        self.fields["description"].required = False
        self.fields["is_contractor_only"].required = False
        if user and user.is_authenticated and not getattr(user, "is_company_owner", False):
            self.fields["is_contractor_only"].disabled = True
            self.fields["is_contractor_only"].help_text = (
                "Only the company owner can enable or disable contractor-only access."
            )

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()

        if not name:
            raise forms.ValidationError("Role name is required.")

        return name

    def clean(self):
        cleaned_data = super().clean()

        request_user = self.request_user
        company = getattr(request_user, "id_company", None)
        name = cleaned_data.get("name")

        if not request_user or not request_user.is_authenticated:
            raise forms.ValidationError("You must be logged in to manage roles.")

        if not company:
            raise forms.ValidationError("Your account does not have a company assigned.")

        original_contractor_value = (
            bool(self.instance.is_contractor_only) if self.instance and self.instance.pk else False
        )
        requested_contractor_value = bool(cleaned_data.get("is_contractor_only"))
        if (
            requested_contractor_value != original_contractor_value
            and not getattr(request_user, "is_company_owner", False)
        ):
            raise forms.ValidationError(
                "Only the company owner can enable or disable a contractor-only role."
            )

        if name:
            existing = Role.objects.filter(
                id_company=company,
                name__iexact=name,
            )

            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise forms.ValidationError("A role with this name already exists for this company.")

        return cleaned_data

    def save(self, commit=True):
        role = super().save(commit=False)

        request_user = self.request_user
        role.id_company = request_user.id_company

        if hasattr(role, "status") and not role.status:
            role.status = STATUS_ACTIVE

        if commit:
            role.save()

        return role


def _identification_form_field():
    return forms.CharField(
        label="DNI / Identification",
        required=False,
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Optional DNI or identification",
                "autocomplete": "off",
            }
        ),
    )


def _position_form_field():
    return forms.CharField(
        label="Position / Category",
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Position or job category",
                "autocomplete": "organization-title",
            }
        ),
    )


class _UserEmploymentFormMixin:
    def _configure_common_fields(self, user):
        self.request_user = user
        company = getattr(user, "id_company", None)

        self.fields["id_role"].queryset = Role.objects.filter(
            id_company=company,
            status=STATUS_ACTIVE,
        ).order_by("name")

        for field_name in ("first_name", "last_name", "email", "id_role", "status"):
            self.fields[field_name].required = True

        self.fields["phone"].required = False
        self.fields["identification"].required = False
        self.fields["position"].required = False
        self.fields["status"].initial = getattr(self.instance, "status", None) or STATUS_ACTIVE

        profile = getattr(self.instance, "employment_profile", None)
        if profile:
            self.fields["identification"].initial = profile.identification
            self.fields["position"].initial = profile.position or profile.category

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")

        duplicate = UserAccount.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def _clean_common(self, cleaned_data):
        request_user = self.request_user
        company = getattr(request_user, "id_company", None)
        role = cleaned_data.get("id_role")
        status = cleaned_data.get("status") or STATUS_ACTIVE

        if not request_user or not request_user.is_authenticated:
            raise forms.ValidationError("You must be logged in to manage employees and users.")
        if not company:
            raise forms.ValidationError("Your account does not have a company assigned.")
        if role and role.id_company_id != company.id_company:
            raise forms.ValidationError("You can only assign roles from your company.")
        if role and role.status != STATUS_ACTIVE:
            raise forms.ValidationError("The selected role is inactive.")

        if self.instance and self.instance.pk:
            activating = not self.instance.is_active and status == STATUS_ACTIVE
            if activating and company_active_user_limit_reached(company):
                raise forms.ValidationError(get_company_user_limit_message(company))
            if request_user.pk == self.instance.pk and status == STATUS_INACTIVE:
                raise forms.ValidationError("You cannot deactivate your own account.")
        elif status == STATUS_ACTIVE and company_active_user_limit_reached(company):
            raise forms.ValidationError(get_company_user_limit_message(company))

        return cleaned_data

    def _save_user_and_profile(self, user_account, password=None, commit=True):
        from apps.employees.services import sync_employee_profile

        user_account.id_company = self.request_user.id_company
        user_account.is_active = user_account.status == STATUS_ACTIVE

        if password:
            user_account.set_password(password)

        if not commit:
            return user_account

        with transaction.atomic():
            user_account.save()
            sync_employee_profile(
                user_account,
                identification=(self.cleaned_data.get("identification") or "").strip() or None,
                position=(self.cleaned_data.get("position") or "").strip() or None,
            )

        return user_account


class UserAccountCreateForm(_UserEmploymentFormMixin, forms.ModelForm):
    identification = _identification_form_field()
    position = _position_form_field()
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Password",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Confirm password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = UserAccount
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "id_role",
            "status",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"class": "crm_input", "placeholder": "email@company.com", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Optional phone", "autocomplete": "tel"}),
            "id_role": forms.Select(attrs={"class": "crm_input"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_common_fields(user)

    def clean(self):
        cleaned_data = super().clean()
        self._clean_common(cleaned_data)
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if not password1:
            self.add_error("password1", "Password is required.")
        elif password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        else:
            candidate = UserAccount(
                email=cleaned_data.get("email") or "",
                first_name=cleaned_data.get("first_name") or "",
                last_name=cleaned_data.get("last_name") or "",
                id_company=getattr(self.request_user, "id_company", None),
            )
            try:
                validate_password(password1, user=candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned_data

    def save(self, commit=True):
        user_account = super().save(commit=False)
        return self._save_user_and_profile(
            user_account,
            password=self.cleaned_data.get("password1"),
            commit=commit,
        )


class UserAccountUpdateForm(_UserEmploymentFormMixin, forms.ModelForm):
    identification = _identification_form_field()
    position = _position_form_field()
    password1 = forms.CharField(
        label="New Password",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Leave empty to keep current password",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm New Password",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = UserAccount
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "id_role",
            "status",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"class": "crm_input", "placeholder": "email@company.com", "autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Optional phone", "autocomplete": "tel"}),
            "id_role": forms.Select(attrs={"class": "crm_input"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_common_fields(user)

    def clean(self):
        cleaned_data = super().clean()
        self._clean_common(cleaned_data)
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 or password2:
            if password1 != password2:
                self.add_error("password2", "Passwords do not match.")
            else:
                try:
                    validate_password(password1, user=self.instance)
                except ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned_data

    def save(self, commit=True):
        user_account = super().save(commit=False)
        return self._save_user_and_profile(
            user_account,
            password=self.cleaned_data.get("password1"),
            commit=commit,
        )
