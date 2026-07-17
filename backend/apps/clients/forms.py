from django import forms

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "second_last_name",
            "dni",
            "phone",
            "email",
            "address",
        ]

        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "First name",
                }
            ),
            "middle_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Middle name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Last name",
                }
            ),
            "second_last_name": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Second last name",
                }
            ),
            "dni": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "DNI / Tax ID (optional)",
                    "autocomplete": "off",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Phone",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Email",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 3,
                    "placeholder": "Address",
                }
            ),
                    }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user

        self.fields["first_name"].required = True
        self.fields["middle_name"].required = False
        self.fields["last_name"].required = True
        self.fields["second_last_name"].required = False
        self.fields["dni"].required = False
        self.fields["phone"].required = False
        self.fields["email"].required = False
        self.fields["address"].required = False

    def clean_dni(self):
        return (self.cleaned_data.get("dni") or "").strip()

    def clean(self):
        cleaned_data = super().clean()

        first_name = (cleaned_data.get("first_name") or "").strip()
        last_name = (cleaned_data.get("last_name") or "").strip()

        if not first_name or not last_name:
            raise forms.ValidationError("First name and last name are required.")

        if not self.request_user or not self.request_user.is_authenticated:
            raise forms.ValidationError("You must be logged in to manage clients.")

        if not self.request_user.id_company_id:
            raise forms.ValidationError("Your user does not have a company assigned.")

        return cleaned_data

    def save(self, commit=True):
        client = super().save(commit=False)

        client.id_company = self.request_user.id_company

        full_name = client.full_name

        if full_name:
            client.name = full_name

        if commit:
            client.save()

        return client