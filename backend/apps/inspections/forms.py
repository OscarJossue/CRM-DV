from django import forms

from apps.accounts.models import UserAccount
from apps.clients.models import Client

from .models import InspectionAssignment

class InspectionAssignmentForm(forms.ModelForm):
    """Administrative inspection form with automatic workflow status."""

    temp_first_name = forms.CharField(
        required=False,
        label="First Name",
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "First name"}),
    )
    temp_middle_name = forms.CharField(
        required=False,
        label="Middle Name",
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Middle name"}),
    )
    temp_last_name = forms.CharField(
        required=False,
        label="Last Name",
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Last name"}),
    )
    temp_second_last_name = forms.CharField(
        required=False,
        label="Second Last Name",
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Second last name"}),
    )
    temp_phone = forms.CharField(
        required=False,
        label="Phone",
        widget=forms.TextInput(attrs={"class": "crm_input", "placeholder": "Phone"}),
    )
    temp_email = forms.EmailField(
        required=False,
        label="Email",
        widget=forms.EmailInput(attrs={"class": "crm_input", "placeholder": "Email"}),
    )
    temp_address = forms.CharField(
        required=False,
        label="Address",
        widget=forms.Textarea(
            attrs={"class": "crm_input", "rows": 3, "placeholder": "Inspection address"}
        ),
    )

    class Meta:
        model = InspectionAssignment
        fields = ["client", "inspector", "inspection_date", "google_maps_url", "notes"]
        widgets = {
            "client": forms.Select(attrs={"class": "crm_input"}),
            "inspector": forms.Select(attrs={"class": "crm_input"}),
            "inspection_date": forms.DateTimeInput(
                attrs={"class": "crm_input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "google_maps_url": forms.URLInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Optional Google Maps link",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 4,
                    "placeholder": "Administrative assignment notes",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        self.fields["inspection_date"].input_formats = ["%Y-%m-%dT%H:%M"]

        def client_label(obj):
            code = obj.client_code or f"CL_{obj.id_client:06d}"
            name = obj.name or "No name"
            phone = obj.phone or "No phone"
            return f"{code} - {name} - {phone}"

        def user_label(obj):
            full_name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
            role_name = obj.id_role.name if obj.id_role else "No role"
            return f"{full_name or obj.email} - {obj.email} - {role_name}"

        self.fields["client"].label_from_instance = client_label
        self.fields["inspector"].label_from_instance = user_label
        self.fields["client"].required = False
        self.fields["client"].empty_label = "Search existing client or enter a new client"
        self.fields["inspector"].required = False
        self.fields["inspector"].empty_label = "Search inspector"
        self.fields["inspection_date"].required = True
        self.fields["google_maps_url"].required = False
        self.fields["notes"].required = False

        if user and user.is_authenticated and user.id_company_id:
            clients_queryset = Client.objects.filter(
                id_company_id=user.id_company_id
            ).order_by("first_name", "last_name", "name", "email")
            self.fields["client"].queryset = clients_queryset
            self.client_autofill_data = {
                str(client.id_client): {
                    "first_name": client.first_name or "",
                    "middle_name": client.middle_name or "",
                    "last_name": client.last_name or "",
                    "second_last_name": client.second_last_name or "",
                    "phone": client.phone or "",
                    "email": client.email or "",
                    "address": client.address or "",
                }
                for client in clients_queryset
            }
            self.fields["inspector"].queryset = (
                UserAccount.objects.select_related("id_company", "id_role")
                .filter(id_company_id=user.id_company_id, is_active=True)
                .order_by("first_name", "last_name", "email")
            )
        else:
            self.fields["client"].queryset = Client.objects.none()
            self.fields["inspector"].queryset = UserAccount.objects.none()
            self.client_autofill_data = {}

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get("client")
        inspector = cleaned_data.get("inspector")
        temp_first_name = (cleaned_data.get("temp_first_name") or "").strip()
        temp_last_name = (cleaned_data.get("temp_last_name") or "").strip()
        temp_phone = (cleaned_data.get("temp_phone") or "").strip()
        temp_email = (cleaned_data.get("temp_email") or "").strip()
        temp_address = (cleaned_data.get("temp_address") or "").strip()

        if not self.request_user or not self.request_user.is_authenticated:
            raise forms.ValidationError("You must be logged in to assign inspections.")
        if not self.request_user.id_company_id:
            raise forms.ValidationError("Your user does not have a company assigned.")
        if client and client.id_company_id != self.request_user.id_company_id:
            raise forms.ValidationError("You can only use clients from your company.")
        if not client:
            if not temp_first_name:
                self.add_error("temp_first_name", "First name is required.")
            if not temp_last_name:
                self.add_error("temp_last_name", "Last name is required.")
            if not temp_address:
                self.add_error("temp_address", "Address is required.")
            if not temp_phone and not temp_email:
                self.add_error("temp_phone", "Phone or email is required.")
                self.add_error("temp_email", "Phone or email is required.")
        if inspector and inspector.id_company_id != self.request_user.id_company_id:
            raise forms.ValidationError("Inspector must belong to your company.")
        return cleaned_data

    def save(self, commit=True):
        assignment = super().save(commit=False)
        if not assignment.client_id:
            client = Client.objects.create(
                id_company=self.request_user.id_company,
                first_name=(self.cleaned_data.get("temp_first_name") or "").strip(),
                middle_name=(self.cleaned_data.get("temp_middle_name") or "").strip() or None,
                last_name=(self.cleaned_data.get("temp_last_name") or "").strip(),
                second_last_name=(self.cleaned_data.get("temp_second_last_name") or "").strip() or None,
                phone=(self.cleaned_data.get("temp_phone") or "").strip() or None,
                email=(self.cleaned_data.get("temp_email") or "").strip() or None,
                address=(self.cleaned_data.get("temp_address") or "").strip(),
                notes="[TEMPORARY CLIENT]",
            )
            assignment.client = client
        if commit:
            assignment.save()
        return assignment
