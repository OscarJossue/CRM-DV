from django import forms
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.accounts.models import UserAccount
from apps.accounts.models.choices import STATUS_ACTIVE
from apps.platform_plans.models import PlatformPlan
from apps.platform_plans.models.choices import PLAN_STATUS_ACTIVE
from apps.platform_subscriptions.models import PlatformSubscription
from apps.platform_subscriptions.services import calculate_plan_renewal_date

from .models import Company


def get_current_company_subscription(company):
    if not company or not getattr(company, "pk", None):
        return None

    return (
        PlatformSubscription.objects.select_related("id_plan", "id_company")
        .filter(id_company=company)
        .order_by("-created_at")
        .first()
    )


def get_company_owner_user(company):
    if not company or not getattr(company, "pk", None):
        return None

    owner_user = (
        UserAccount.objects.select_related("id_company", "id_role")
        .filter(
            id_company=company,
            is_company_owner=True,
        )
        .order_by("id_user")
        .first()
    )

    if not owner_user:
        owner_user = (
            UserAccount.objects.select_related("id_company", "id_role")
            .filter(
                id_company=company,
                id_role__name__iexact="Owner",
            )
            .order_by("id_user")
            .first()
        )

    return owner_user


class CompanyForm(forms.ModelForm):
    id_plan = forms.ModelChoiceField(
        label="SaaS Plan",
        queryset=PlatformPlan.objects.none(),
        required=True,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    subscription_start_date = forms.DateField(
        label="Subscription Start Date",
        required=False,
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
    )

    subscription_renewal_date = forms.DateField(
        label="Renewal Date",
        required=False,
        widget=forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
    )

    subscription_notes = forms.CharField(
        label="Subscription Notes",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 3,
                "placeholder": "Internal notes about the company subscription, plan change or renewal.",
            }
        ),
    )

    owner_first_name = forms.CharField(
        label="Administrator First Name",
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "crm_input", "autocomplete": "given-name"}),
    )

    owner_last_name = forms.CharField(
        label="Administrator Last Name",
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"class": "crm_input", "autocomplete": "family-name"}),
    )

    owner_email = forms.EmailField(
        label="Administrator Login Email",
        required=False,
        widget=forms.EmailInput(attrs={"class": "crm_input", "autocomplete": "email", "spellcheck": "false"}),
    )

    owner_phone = forms.CharField(
        label="Administrator Phone",
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={"class": "crm_input", "autocomplete": "tel"}),
    )

    owner_password1 = forms.CharField(
        label="New Administrator Password",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Leave empty to keep current owner password",
                "autocomplete": "new-password",
            }
        ),
    )

    owner_password2 = forms.CharField(
        label="Confirm Administrator Password",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Confirm new owner password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = Company
        fields = [
            "name",
            "legal_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "country",
            "logo",
            "description",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Company name"}),
            "legal_name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Legal company name"}),
            "email": forms.EmailInput(attrs={"class": "crm_input", "placeholder": "company@email.com"}),
            "phone": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Company phone"}),
            "address": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Address"}),
            "city": forms.TextInput(attrs={"class": "crm_input", "placeholder": "City"}),
            "state": forms.TextInput(attrs={"class": "crm_input", "placeholder": "State"}),
            "country": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Country"}),
            "logo": forms.ClearableFileInput(attrs={"class": "crm_input", "accept": "image/*"}),
            "description": forms.Textarea(attrs={"class": "crm_input", "rows": 5, "placeholder": "Company description"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_subscription = get_current_company_subscription(self.instance)
        current_owner = get_company_owner_user(self.instance)

        plan_queryset = PlatformPlan.objects.filter(status=PLAN_STATUS_ACTIVE)

        if current_subscription and current_subscription.id_plan_id:
            plan_queryset = PlatformPlan.objects.filter(
                Q(status=PLAN_STATUS_ACTIVE) | Q(id_plan=current_subscription.id_plan_id)
            )

        self.fields["id_plan"].queryset = plan_queryset.distinct().order_by("price", "name")

        if current_subscription:
            self.fields["id_plan"].initial = current_subscription.id_plan_id
            self.fields["subscription_start_date"].initial = current_subscription.start_date
            self.fields["subscription_renewal_date"].initial = current_subscription.renewal_date
            self.fields["subscription_notes"].initial = current_subscription.notes
        else:
            today = timezone.localdate()
            self.fields["subscription_start_date"].initial = today

            first_plan = self.fields["id_plan"].queryset.first()
            if first_plan:
                self.fields["subscription_renewal_date"].initial = calculate_plan_renewal_date(
                    first_plan,
                    start_date=today,
                )

        if current_owner:
            self.fields["owner_first_name"].initial = current_owner.first_name
            self.fields["owner_last_name"].initial = current_owner.last_name
            self.fields["owner_email"].initial = current_owner.email
            self.fields["owner_phone"].initial = current_owner.phone

        if not self.instance or not self.instance.pk:
            self.fields.pop("owner_first_name", None)
            self.fields.pop("owner_last_name", None)
            self.fields.pop("owner_email", None)
            self.fields.pop("owner_phone", None)
            self.fields.pop("owner_password1", None)
            self.fields.pop("owner_password2", None)

            self.order_fields(
                [
                    "name",
                    "legal_name",
                    "email",
                    "phone",
                    "address",
                    "city",
                    "state",
                    "country",
                    "logo",
                    "description",
                    "id_plan",
                    "subscription_start_date",
                    "subscription_renewal_date",
                    "subscription_notes",
                    "status",
                ]
            )
        else:
            self.order_fields(
                [
                    "name",
                    "legal_name",
                    "email",
                    "phone",
                    "address",
                    "city",
                    "state",
                    "country",
                    "logo",
                    "description",
                    "id_plan",
                    "subscription_start_date",
                    "subscription_renewal_date",
                    "subscription_notes",
                    "status",
                    "owner_first_name",
                    "owner_last_name",
                    "owner_email",
                    "owner_phone",
                    "owner_password1",
                    "owner_password2",
                ]
            )

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()

        if not name:
            raise forms.ValidationError("Company name is required.")

        qs = Company.objects.filter(name__iexact=name)

        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("A company with this name already exists.")

        return name

    def clean_owner_email(self):
        email = (self.cleaned_data.get("owner_email") or "").strip().lower()
        if not self.instance or not self.instance.pk:
            return email or None

        owner_user = get_company_owner_user(self.instance)
        if not email:
            raise forms.ValidationError("Administrator email is required.")

        queryset = UserAccount.objects.filter(email__iexact=email)
        if owner_user:
            queryset = queryset.exclude(pk=owner_user.pk)
        if queryset.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")

        if not logo:
            return logo

        max_size_mb = 3
        max_size_bytes = max_size_mb * 1024 * 1024

        if logo.size > max_size_bytes:
            raise forms.ValidationError(f"Logo file must be less than {max_size_mb}MB.")

        return logo

    def clean(self):
        cleaned_data = super().clean()

        plan = cleaned_data.get("id_plan")
        owner_password1 = cleaned_data.get("owner_password1")
        owner_password2 = cleaned_data.get("owner_password2")

        start_date = cleaned_data.get("subscription_start_date")
        renewal_date = cleaned_data.get("subscription_renewal_date")

        if not plan:
            self.add_error("id_plan", "Select a SaaS plan.")

        if start_date and renewal_date and renewal_date < start_date:
            self.add_error("subscription_renewal_date", "Renewal date cannot be before the start date.")

        status = cleaned_data.get("status") or getattr(self.instance, "status", None)

        if status == "active" and renewal_date and renewal_date < timezone.localdate():
            self.add_error(
                "subscription_renewal_date",
                "This renewal date is already expired. Choose a future date before activating the company.",
            )

        if self.instance and self.instance.pk:
            owner_user = get_company_owner_user(self.instance)
            owner_first_name = (cleaned_data.get("owner_first_name") or "").strip()
            owner_email = cleaned_data.get("owner_email")

            if not owner_first_name:
                self.add_error("owner_first_name", "Administrator first name is required.")
            if not owner_email:
                self.add_error("owner_email", "Administrator email is required.")

            if not owner_user and not owner_password1:
                self.add_error("owner_password1", "Set a password to create the missing company administrator.")

            if owner_password1 or owner_password2:
                if owner_password1 != owner_password2:
                    self.add_error("owner_password2", "Administrator passwords do not match.")
                else:
                    candidate = owner_user or UserAccount(
                        email=owner_email or "",
                        first_name=owner_first_name,
                    )
                    try:
                        validate_password(owner_password1, user=candidate)
                    except forms.ValidationError as exc:
                        self.add_error("owner_password1", exc)

        return cleaned_data

    def save_company_administrator(self, company):
        if not company:
            return {"created": False, "password_changed": False, "user": None}

        from .services import create_owner_role_for_company, enable_default_company_modules

        role = create_owner_role_for_company(company)
        enable_default_company_modules(company)
        owner_user = get_company_owner_user(company)
        created = owner_user is None

        if created:
            owner_user = UserAccount(
                id_company=company,
                id_role=role,
                is_company_owner=True,
                is_staff=False,
                is_superuser=False,
            )

        owner_user.first_name = (self.cleaned_data.get("owner_first_name") or "").strip()
        owner_user.last_name = (self.cleaned_data.get("owner_last_name") or "").strip() or None
        owner_user.email = (self.cleaned_data.get("owner_email") or "").strip().lower()
        owner_user.phone = (self.cleaned_data.get("owner_phone") or "").strip() or None
        owner_user.id_company = company
        owner_user.id_role = role
        owner_user.is_company_owner = True
        owner_user.is_staff = False
        owner_user.is_superuser = False
        owner_user.is_active = True
        owner_user.status = STATUS_ACTIVE

        password = self.cleaned_data.get("owner_password1")
        password_changed = bool(password)
        if password_changed:
            owner_user.set_password(password)

        owner_user.save()
        return {"created": created, "password_changed": password_changed, "user": owner_user}


class CompanyProvisioningForm(forms.Form):
    """Atomic two-step company + administrator provisioning form.

    The browser presents this as two windows, but the server validates every
    field and writes everything inside one database transaction. No company is
    left without an administrator if the second step fails.
    """

    # Step 1: company and access plan.
    name = forms.CharField(
        label="Company Name",
        max_length=255,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Company name", "autocomplete": "organization"}),
    )
    legal_name = forms.CharField(
        label="Legal Name",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Legal company name"}),
    )
    email = forms.EmailField(
        label="Company Email",
        required=False,
        widget=forms.EmailInput(attrs={"class": "crm_input", "placeholder": "company@email.com", "autocomplete": "email"}),
    )
    phone = forms.CharField(
        label="Company Phone",
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Company phone", "autocomplete": "tel"}),
    )
    address = forms.CharField(
        label="Address",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Address", "autocomplete": "street-address"}),
    )
    city = forms.CharField(
        label="City",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "City", "autocomplete": "address-level2"}),
    )
    state = forms.CharField(
        label="State",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "State", "autocomplete": "address-level1"}),
    )
    country = forms.CharField(
        label="Country",
        max_length=120,
        required=False,
        initial="United States",
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Country", "autocomplete": "country-name"}),
    )
    logo = forms.ImageField(
        label="Logo",
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "crm_input", "accept": "image/png,image/jpeg,image/webp"}),
    )
    description = forms.CharField(
        label="Description",
        required=False,
        widget=forms.Textarea(attrs={"class": "crm_input", "rows": 4, "placeholder": "Company description"}),
    )
    id_plan = forms.ModelChoiceField(
        label="SaaS Plan",
        queryset=PlatformPlan.objects.none(),
        widget=forms.Select(attrs={"class": "crm_input"}),
    )
    start_date = forms.DateField(
        label="Subscription Start Date",
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "crm_input", "type": "date"}),
    )
    renewal_date = forms.DateField(
        label="Renewal Date",
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"class": "crm_input", "type": "date"}),
    )

    # Step 2: the one administrator that owns the tenant workspace.
    admin_first_name = forms.CharField(
        label="Administrator First Name",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "First name", "autocomplete": "given-name"}),
    )
    admin_last_name = forms.CharField(
        label="Administrator Last Name",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Last name", "autocomplete": "family-name"}),
    )
    admin_email = forms.EmailField(
        label="Administrator Login Email",
        widget=forms.EmailInput(attrs={"class": "crm_input", "placeholder": "admin@company.com", "autocomplete": "email", "spellcheck": "false"}),
    )
    admin_phone = forms.CharField(
        label="Administrator Phone",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Phone", "autocomplete": "tel"}),
    )
    password1 = forms.CharField(
        label="Administrator Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "crm_input", "placeholder": "Password", "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "crm_input", "placeholder": "Confirm password", "autocomplete": "new-password"}),
    )

    company_step_fields = {
        "name", "legal_name", "email", "phone", "address", "city", "state",
        "country", "logo", "description", "id_plan", "start_date", "renewal_date",
    }
    admin_step_fields = {
        "admin_first_name", "admin_last_name", "admin_email", "admin_phone",
        "password1", "password2",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["id_plan"].queryset = PlatformPlan.objects.filter(
            status=PLAN_STATUS_ACTIVE
        ).order_by("price", "name")

        start_date = self.initial.get("start_date") or timezone.localdate()
        first_plan = self.fields["id_plan"].queryset.first()
        if first_plan and not self.initial.get("renewal_date"):
            self.fields["renewal_date"].initial = calculate_plan_renewal_date(
                first_plan,
                start_date=start_date,
            )

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Company name is required.")
        if Company.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("A company with this name already exists.")
        return name

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower() or None

    def clean_admin_email(self):
        email = (self.cleaned_data.get("admin_email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Administrator email is required.")
        if UserAccount.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo:
            return logo
        if logo.size > 3 * 1024 * 1024:
            raise forms.ValidationError("Logo file must be less than 3MB.")
        try:
            image = Image.open(logo)
            image.verify()
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise forms.ValidationError("Logo must be a PNG, JPEG or WebP image.")
        except (UnidentifiedImageError, OSError, ValueError):
            raise forms.ValidationError("The uploaded logo is not a valid image.")
        finally:
            try:
                logo.seek(0)
            except (AttributeError, OSError):
                pass
        return logo

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        start_date = cleaned_data.get("start_date")
        renewal_date = cleaned_data.get("renewal_date")
        plan = cleaned_data.get("id_plan")

        if not plan:
            self.add_error("id_plan", "Select a SaaS plan.")

        if start_date and not renewal_date and plan:
            cleaned_data["renewal_date"] = calculate_plan_renewal_date(plan, start_date=start_date)
            renewal_date = cleaned_data["renewal_date"]

        if start_date and renewal_date and renewal_date < start_date:
            self.add_error("renewal_date", "Renewal date cannot be before the start date.")

        if renewal_date and renewal_date < timezone.localdate():
            self.add_error("renewal_date", "Renewal date must be today or later.")

        if password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        elif password1:
            candidate = UserAccount(
                email=cleaned_data.get("admin_email") or "",
                first_name=cleaned_data.get("admin_first_name") or "",
                last_name=cleaned_data.get("admin_last_name") or "",
            )
            try:
                validate_password(password1, user=candidate)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)

        return cleaned_data

    def first_error_step(self):
        if any(name in self.errors for name in self.admin_step_fields):
            return 2
        return 1

