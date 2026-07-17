from django import forms

from .models import SystemLog


class SystemLogFilterForm(forms.Form):
    """Compatibility form: history records themselves are never editable."""

    q = forms.CharField(required=False)
    module = forms.CharField(required=False)
    action_type = forms.CharField(required=False)
    severity = forms.CharField(required=False)
    user = forms.IntegerField(required=False)
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)


class SystemLogForm(forms.ModelForm):
    class Meta:
        model = SystemLog
        fields = []
