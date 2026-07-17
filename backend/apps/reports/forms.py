from django import forms


class ReportFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "crm_input",
                "type": "date",
            }
        ),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={
                "class": "crm_input",
                "type": "date",
            }
        ),
    )
