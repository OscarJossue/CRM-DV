from django import forms

from .models import Employee


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["identification", "position", "status"]
        widgets = {
            "identification": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Optional DNI or identification"}),
            "position": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Position or job category"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
