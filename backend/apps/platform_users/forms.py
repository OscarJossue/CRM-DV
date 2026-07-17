from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.accounts.models import UserAccount


class PlatformUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Temporary password",
                "autocomplete": "new-password",
            }
        ),
    )

    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Confirm temporary password",
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
            "status",
            "is_active",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "First name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Last name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "developer@ceomarketingusa.com",
                    "autocomplete": "email",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Phone number",
                }
            ),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "crm_checkbox"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if not email:
            raise forms.ValidationError("Email is required.")

        if UserAccount.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")

        return email

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 != password2:
            raise forms.ValidationError("Passwords do not match.")

        if password1:
            candidate = UserAccount(
                email=cleaned_data.get("email") or "",
                first_name=cleaned_data.get("first_name") or "",
                last_name=cleaned_data.get("last_name") or "",
            )
            try:
                validate_password(password1, user=candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        user.id_company = None
        user.id_role = None
        user.email = user.email.lower()
        user.is_staff = True
        user.is_superuser = False
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()

        return user


class PlatformUserUpdateForm(forms.ModelForm):
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
            "status",
            "is_active",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "crm_input"}),
            "last_name": forms.TextInput(attrs={"class": "crm_input"}),
            "email": forms.EmailInput(attrs={"class": "crm_input"}),
            "phone": forms.TextInput(attrs={"class": "crm_input"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "crm_checkbox"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if not email:
            raise forms.ValidationError("Email is required.")

        queryset = UserAccount.objects.filter(email=email)

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError("This email is already registered.")

        return email

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError("Passwords do not match.")
            try:
                validate_password(password1, user=self.instance)
            except ValidationError as exc:
                self.add_error("password1", exc)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        user.id_company = None
        user.id_role = None
        user.email = user.email.lower()
        user.is_staff = True
        user.is_superuser = False

        password1 = self.cleaned_data.get("password1")

        if password1:
            user.set_password(password1)

        if commit:
            user.save()

        return user