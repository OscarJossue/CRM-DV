import json
from datetime import datetime, time

from django import forms
from django.utils import timezone

from apps.clients.models import Client

from .models import Lead
from .models.choices import (
    LEAD_SOURCE_CHOICES,
    OPPORTUNITY_STATUS_FORM_CHOICES,
    OPPORTUNITY_STATUS_NEW,
)


class ClientSearchSelect(forms.Select):
    """Native select enhanced by Tom Select while keeping a working fallback."""

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )
        instance = getattr(value, "instance", None)
        if instance is not None:
            data = {
                "value": str(instance.pk),
                "text": str(label),
                "name": instance.name or "",
                "client_code": instance.client_code or "",
                "dni": instance.dni or "",
                "email": instance.email or "",
                "phone": instance.phone or "",
                "address": instance.address or "",
            }
            option["attrs"]["data-data"] = json.dumps(
                data,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return option


class ClientChoiceField(forms.ModelChoiceField):
    widget = ClientSearchSelect

    def label_from_instance(self, client):
        code = client.client_code or "Pending"
        dni = f" · DNI {client.dni}" if client.dni else ""
        return f"{code} · {client.name}{dni}"


class LeadForm(forms.ModelForm):
    id_client = ClientChoiceField(
        queryset=Client.objects.none(),
        required=True,
        empty_label="Search or select a client",
        widget=ClientSearchSelect(
            attrs={
                "class": "crm_input opportunity_client_select",
                "autocomplete": "off",
                "data-client-search": "true",
            }
        ),
    )

    status = forms.ChoiceField(
        choices=OPPORTUNITY_STATUS_FORM_CHOICES,
        initial=OPPORTUNITY_STATUS_NEW,
        widget=forms.Select(
            attrs={
                "class": "crm_input opportunity_select opportunity_status_select",
                "autocomplete": "off",
            }
        ),
    )

    source = forms.ChoiceField(
        choices=[("", "Select source"), *LEAD_SOURCE_CHOICES],
        required=False,
        widget=forms.Select(
            attrs={
                "class": "crm_input opportunity_select opportunity_source_select",
                "autocomplete": "off",
            }
        ),
    )

    next_follow_up_date = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "class": "crm_input opportunity_date_input",
                "type": "date",
                "autocomplete": "off",
            },
        ),
    )

    approximate_value = forms.DecimalField(
        min_value=0,
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "crm_input",
                "placeholder": "Approximate value",
                "step": "0.01",
            }
        ),
    )

    class Meta:
        model = Lead
        fields = [
            "id_client",
            "source",
            "status",
            "next_follow_up_date",
            "approximate_value",
            "project_description",
        ]
        widgets = {
            "project_description": forms.Textarea(
                attrs={
                    "class": "crm_input",
                    "rows": 5,
                    "placeholder": "Opportunity description",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user

        self.fields["source"].required = False
        self.fields["status"].required = True
        self.fields["next_follow_up_date"].required = False
        self.fields["project_description"].required = False

        if user and user.is_authenticated and user.id_company_id:
            self.fields["id_client"].queryset = Client.objects.filter(
                id_company_id=user.id_company_id,
            ).order_by("client_code", "name")
        else:
            self.fields["id_client"].queryset = Client.objects.none()

        follow_up_value = self.initial.get("next_follow_up_date")
        if isinstance(follow_up_value, datetime):
            if timezone.is_aware(follow_up_value):
                follow_up_value = timezone.localtime(follow_up_value)
            self.initial["next_follow_up_date"] = follow_up_value.date()

        if self.instance and self.instance.pk:
            self.fields["id_client"].disabled = True

    def clean_id_client(self):
        client = self.cleaned_data.get("id_client")
        if self.instance and self.instance.pk:
            return self.instance.id_client
        return client

    def clean_next_follow_up_date(self):
        follow_up_date = self.cleaned_data.get("next_follow_up_date")
        if not follow_up_date:
            return None

        follow_up_datetime = datetime.combine(follow_up_date, time.min)
        if timezone.is_naive(follow_up_datetime):
            follow_up_datetime = timezone.make_aware(
                follow_up_datetime,
                timezone.get_current_timezone(),
            )
        return follow_up_datetime

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get("id_client")

        if not self.request_user or not self.request_user.is_authenticated:
            raise forms.ValidationError("You must be logged in to manage opportunities.")

        if not self.request_user.id_company_id:
            raise forms.ValidationError("Your user does not have a company assigned.")

        if not client:
            raise forms.ValidationError(
                "Client is required. Please select an existing client."
            )

        if client.id_company_id != self.request_user.id_company_id:
            raise forms.ValidationError(
                "You can only manage opportunities for your company."
            )

        return cleaned_data

    def save(self, commit=True):
        lead = super().save(commit=False)
        lead.id_company = self.request_user.id_company
        lead.id_assigned_user = self.request_user

        if lead.id_client:
            lead.id_company = lead.id_client.id_company

        if commit:
            lead.save()

        return lead
