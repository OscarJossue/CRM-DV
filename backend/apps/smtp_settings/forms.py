from django import forms

from apps.companies.models.choices import COMPANY_LANGUAGE_CHOICES

from .models import SmtpSetting
from .security import encrypt_smtp_password


class CompanyLanguageSettingsForm(forms.Form):
    default_language = forms.ChoiceField(
        choices=COMPANY_LANGUAGE_CHOICES,
        label="Company interface language",
        widget=forms.Select(attrs={"class": "crm_input"}),
    )


class SmtpSettingForm(forms.ModelForm):
    smtp_password = forms.CharField(
        required=False,
        label="SMTP Password / App Password",
        widget=forms.PasswordInput(
            render_value=False,
            attrs={
                "class": "crm_input",
                "placeholder": "Paste SMTP password or Gmail App Password",
                "autocomplete": "new-password",
            },
        ),
    )

    class Meta:
        model = SmtpSetting
        fields = [
            "smtp_host",
            "smtp_port",
            "use_tls",
            "use_ssl",
            "smtp_username",
            "smtp_password",
            "default_from_email",
            "from_name",
            "is_active",
        ]

        labels = {
            "smtp_host": "SMTP Host",
            "smtp_port": "SMTP Port",
            "use_tls": "Use TLS",
            "use_ssl": "Use SSL",
            "smtp_username": "SMTP Username",
            "smtp_password": "SMTP Password / App Password",
            "default_from_email": "Default From Email",
            "from_name": "From Name",
            "is_active": "Active",
        }

        widgets = {
            "smtp_host": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "mail.yourdomain.com",
                }
            ),
            "smtp_port": forms.NumberInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "465",
                    "min": "1",
                }
            ),
            "use_tls": forms.CheckboxInput(),
            "use_ssl": forms.CheckboxInput(),
            "smtp_username": forms.EmailInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "info@yourdomain.com",
                }
            ),
            "default_from_email": forms.EmailInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "info@yourdomain.com",
                }
            ),
            "from_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Company Name",
                }
            ),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_password = ""

        if self.instance and self.instance.pk:
            self.current_password = self.instance.smtp_password or ""
            self.fields["smtp_password"].required = False
            self.fields["smtp_password"].help_text = (
                "Leave blank to keep the current SMTP password."
            )
        else:
            self.fields["smtp_password"].required = True

    def clean_smtp_host(self):
        smtp_host = (self.cleaned_data.get("smtp_host") or "").strip()

        if not smtp_host:
            raise forms.ValidationError("SMTP host is required.")

        if smtp_host.startswith(("http://", "https://")):
            raise forms.ValidationError(
                "Enter only the SMTP server host, for example mail.yourdomain.com. Do not use http:// or https://."
            )

        return smtp_host

    def clean_smtp_port(self):
        smtp_port = self.cleaned_data.get("smtp_port")

        if not smtp_port:
            raise forms.ValidationError("SMTP port is required.")

        if smtp_port in [80, 443]:
            raise forms.ValidationError(
                "Port 443/80 is for websites, not SMTP. Use 465 with SSL or 587 with TLS."
            )

        return smtp_port

    def clean_smtp_username(self):
        return (self.cleaned_data.get("smtp_username") or "").strip()

    def clean_default_from_email(self):
        return (self.cleaned_data.get("default_from_email") or "").strip()

    def clean_from_name(self):
        return (self.cleaned_data.get("from_name") or "").strip()

    def clean(self):
        cleaned_data = super().clean()

        use_tls = cleaned_data.get("use_tls")
        use_ssl = cleaned_data.get("use_ssl")
        smtp_password = cleaned_data.get("smtp_password")
        smtp_port = cleaned_data.get("smtp_port")

        if use_tls and use_ssl:
            raise forms.ValidationError("Use TLS and Use SSL cannot both be enabled.")

        if smtp_port == 465 and not use_ssl:
            raise forms.ValidationError("Port 465 must use SSL enabled and TLS disabled.")

        if smtp_port == 465 and use_tls:
            raise forms.ValidationError("Port 465 must use SSL, not TLS.")

        if smtp_port == 587 and not use_tls:
            raise forms.ValidationError("Port 587 must use TLS enabled and SSL disabled.")

        if smtp_port == 587 and use_ssl:
            raise forms.ValidationError("Port 587 must use TLS, not SSL.")

        if not smtp_password and not self.current_password:
            raise forms.ValidationError("SMTP password is required.")

        return cleaned_data

    def save(self, commit=True):
        smtp_setting = super().save(commit=False)

        smtp_password = self.cleaned_data.get("smtp_password")

        if smtp_password:
            smtp_setting.smtp_password = encrypt_smtp_password(smtp_password)
        else:
            smtp_setting.smtp_password = encrypt_smtp_password(self.current_password)

        if commit:
            smtp_setting.save()

        return smtp_setting
