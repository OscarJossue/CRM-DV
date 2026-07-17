from django import forms


class PlatformEmailComposeForm(forms.Form):
    recipient_email = forms.EmailField(
        label="Recipient Email",
        widget=forms.EmailInput(
            attrs={
                "class": "crm_input",
                "placeholder": "owner@company.com",
            }
        ),
    )
    subject = forms.CharField(
        label="Subject",
        max_length=255,
        initial="CEO Marketing CRM Notification",
        widget=forms.TextInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Subscription renewal notice",
            }
        ),
    )
    message = forms.CharField(
        label="Message",
        initial="Hello, this is a notification from CEO Marketing CRM regarding your SaaS account.",
        widget=forms.Textarea(
            attrs={
                "class": "crm_input",
                "rows": 7,
                "placeholder": "Write the platform email message here.",
            }
        ),
    )