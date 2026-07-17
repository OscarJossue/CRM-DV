from django import forms

from apps.accounts.models.choices import LANGUAGE_CHOICES
from apps.companies.models.choices import COMPANY_LANGUAGE_CHOICES


class CompanyLanguageForm(forms.Form):
    language = forms.ChoiceField(
        choices=COMPANY_LANGUAGE_CHOICES,
        widget=forms.RadioSelect,
    )


class PlatformLanguageForm(forms.Form):
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=forms.RadioSelect,
    )
