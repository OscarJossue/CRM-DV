from django import forms

from apps.accounts.models import UserAccount

from .models import Notification
from .models.choices import NOTIFICATION_STATUS_CHOICES, NOTIFICATION_TYPE_CHOICES


class NotificationForm(forms.ModelForm):
    type = forms.ChoiceField(
        choices=NOTIFICATION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    status = forms.ChoiceField(
        choices=NOTIFICATION_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "crm_input"}),
    )

    class Meta:
        model = Notification
        fields = [
            "id_user",
            "type",
            "title",
            "message",
            "status",
        ]
        widgets = {
            "id_user": forms.Select(attrs={"class": "crm_input"}),
            "title": forms.TextInput(
                attrs={
                    "class": "crm_input",
                    "placeholder": "Notification title",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 5,
                    "placeholder": "Notification message",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.request_user = user

        if user and not user.is_superuser:
            self.fields["id_user"].queryset = UserAccount.objects.filter(
                id_company=user.id_company_id,
                is_active=True,
            ).order_by("first_name", "last_name", "email")
        else:
            self.fields["id_user"].queryset = UserAccount.objects.select_related(
                "id_company"
            ).filter(is_active=True).order_by("id_company__name", "first_name", "email")

    def clean(self):
        cleaned_data = super().clean()

        target_user = cleaned_data.get("id_user")

        if (
            self.request_user
            and not self.request_user.is_superuser
            and target_user
            and target_user.id_company_id != self.request_user.id_company_id
        ):
            raise forms.ValidationError("You can only create notifications for users in your company.")

        return cleaned_data
