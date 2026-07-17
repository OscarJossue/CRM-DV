from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError


ALLOWED_SUPPLIER_DOCUMENT_TYPES = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}
MAX_SUPPLIER_DOCUMENT_SIZE = 5 * 1024 * 1024


def validate_supplier_document_file(uploaded_file):
    if not uploaded_file:
        return uploaded_file
    if uploaded_file.size > MAX_SUPPLIER_DOCUMENT_SIZE:
        raise ValidationError("The document must not exceed 5 MB.")
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    signatures = ALLOWED_SUPPLIER_DOCUMENT_TYPES.get(content_type)
    if not signatures:
        raise ValidationError("Only PDF, JPEG and PNG documents are allowed.")
    position = uploaded_file.tell()
    header = uploaded_file.read(16)
    uploaded_file.seek(position)
    if not any(header.startswith(signature) for signature in signatures):
        raise ValidationError("The uploaded file content does not match its declared type.")
    return uploaded_file
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Supplier, SupplierDocument, SupplierOffer, SupplierPurchase, SupplierPurchaseItem
from .models.choices import OFFER_TYPE_PRODUCT, SUPPLIER_STATUS_ACTIVE


def clean_decimal_value(value, default="0.00"):
    if value in [None, ""]:
        return Decimal(default)

    if isinstance(value, Decimal):
        return value

    value = str(value).strip().replace(",", ".")

    try:
        return Decimal(value)
    except InvalidOperation:
        raise forms.ValidationError("Enter a valid number.")


def company_for_user(user):
    if not user or not user.is_authenticated or user.is_superuser:
        return None
    return user.id_company


class SupplierProductSelect(forms.Select):
    """Adds product metadata to each option for the purchase item JS."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance:
            option["attrs"]["data-supplier"] = str(instance.id_supplier_id)
            option["attrs"]["data-name"] = instance.name or ""
            option["attrs"]["data-description"] = instance.description or ""
            option["attrs"]["data-unit"] = instance.unit or ""
            option["attrs"]["data-price"] = str(instance.estimated_price or Decimal("0.00"))
        return option


class SupplierProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        code = f"{obj.product_code} · " if getattr(obj, "product_code", None) else ""
        price = f" · ${obj.estimated_price}" if obj.estimated_price else ""
        return f"{obj.id_supplier.company_name} — {code}{obj.name}{price}"


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "company_name",
            "tax_id",
            "contact_name",
            "phone",
            "email",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
            "status",
            "notes",
        ]
        labels = {
            "company_name": "Supplier Name",
            "tax_id": "DNI / Tax ID",
            "city": "Locality / City",
        }
        widgets = {
            "company_name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Supplier name"}),
            "tax_id": forms.TextInput(attrs={"class": "crm_input", "placeholder": "DNI, EIN, RUC or tax ID"}),
            "contact_name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Contact name"}),
            "phone": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Phone"}),
            "email": forms.EmailInput(attrs={"class": "crm_input", "placeholder": "supplier@example.com"}),
            "address": forms.Textarea(attrs={"class": "crm_input", "rows": 3, "placeholder": "Address"}),
            "city": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Locality / city"}),
            "state": forms.TextInput(attrs={"class": "crm_input", "placeholder": "State"}),
            "zip_code": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Zip code"}),
            "country": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Country"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "notes": forms.Textarea(attrs={"class": "crm_input", "rows": 3, "placeholder": "Internal notes"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        self.fields["company_name"].required = True
        for name, field in self.fields.items():
            if name != "company_name":
                field.required = False

    def clean_company_name(self):
        company_name = (self.cleaned_data.get("company_name") or "").strip()
        if not company_name:
            raise forms.ValidationError("Supplier name is required.")

        user_company = company_for_user(self.request_user)
        if user_company:
            exists = Supplier.objects.filter(
                id_company=user_company,
                company_name__iexact=company_name,
            )
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise forms.ValidationError("A supplier with this name already exists.")

        return company_name

    def clean(self):
        cleaned_data = super().clean()
        if not self.request_user or not self.request_user.is_authenticated:
            raise forms.ValidationError("You must be logged in to manage suppliers.")
        if not self.request_user.is_superuser and not self.request_user.id_company_id:
            raise forms.ValidationError("Your user does not have a company assigned.")
        return cleaned_data


class SupplierOfferForm(forms.ModelForm):
    class Meta:
        model = SupplierOffer
        fields = [
            "id_supplier",
            "name",
            "product_code",
            "description",
            "category",
            "unit",
            "estimated_price",
            "status",
            "notes",
        ]
        labels = {
            "id_supplier": "Supplier",
            "name": "Product / Service Name",
            "product_code": "Product Code",
            "estimated_price": "Reference Cost",
        }
        widgets = {
            "id_supplier": forms.Select(attrs={"class": "crm_input"}),
            "name": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Product or service name"}),
            "product_code": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Example: PD-001"}),
            "description": forms.Textarea(attrs={"class": "crm_input", "rows": 3, "placeholder": "Product description"}),
            "category": forms.Select(attrs={"class": "crm_input"}),
            "unit": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Unit, box, hour, roll..."}),
            "estimated_price": forms.NumberInput(attrs={"class": "crm_input", "step": "0.01", "min": "0"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "notes": forms.Textarea(attrs={"class": "crm_input", "rows": 3, "placeholder": "Internal notes"}),
        }

    def __init__(self, *args, user=None, supplier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        self.initial_supplier = supplier
        supplier_queryset = Supplier.objects.filter(status=SUPPLIER_STATUS_ACTIVE)
        if user and user.is_authenticated and not user.is_superuser:
            supplier_queryset = supplier_queryset.filter(id_company=user.id_company_id)
        self.fields["id_supplier"].queryset = supplier_queryset.order_by("company_name")
        if supplier:
            self.fields["id_supplier"].initial = supplier
            self.fields["id_supplier"].widget = forms.HiddenInput()
        self.fields["id_supplier"].required = True
        self.fields["name"].required = True
        self.fields["product_code"].required = False
        self.fields["description"].required = False
        self.fields["unit"].required = False
        self.fields["estimated_price"].required = False
        self.fields["notes"].required = False

    def clean_product_code(self):
        code = (self.cleaned_data.get("product_code") or "").strip()
        if not code:
            return code

        user_company = company_for_user(self.request_user)
        if user_company:
            exists = SupplierOffer.objects.filter(id_company=user_company, product_code__iexact=code)
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise forms.ValidationError("This product code is already used in your company.")
        return code

    def clean_estimated_price(self):
        value = clean_decimal_value(self.cleaned_data.get("estimated_price"), "0.00")
        if value < Decimal("0.00"):
            raise forms.ValidationError("Reference cost cannot be negative.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        supplier = cleaned_data.get("id_supplier") or self.initial_supplier
        if not supplier:
            raise forms.ValidationError("Select a supplier.")
        if not self.request_user.is_superuser and supplier.id_company_id != self.request_user.id_company_id:
            raise forms.ValidationError("Selected supplier does not belong to your company.")
        cleaned_data["offer_type"] = OFFER_TYPE_PRODUCT
        return cleaned_data


class SupplierPurchaseForm(forms.ModelForm):
    class Meta:
        model = SupplierPurchase
        fields = [
            "id_supplier",
            "purchase_date",
            "external_document_number",
            "category",
            "status",
            "discount_amount",
            "paid_amount",
            "description",
            "notes",
        ]
        labels = {
            "id_supplier": "Supplier",
            "external_document_number": "Receipt / Reference",
            "paid_amount": "Paid Amount",
        }
        widgets = {
            "id_supplier": forms.Select(attrs={"class": "crm_input", "id": "id_supplier_select"}),
            "purchase_date": forms.DateInput(attrs={"class": "crm_input", "type": "date"}),
            "external_document_number": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Receipt, invoice or reference"}),
            "category": forms.Select(attrs={"class": "crm_input"}),
            "status": forms.Select(attrs={"class": "crm_input"}),
            "discount_amount": forms.NumberInput(attrs={"class": "crm_input supplier_discount_input", "step": "0.01", "min": "0"}),
            "paid_amount": forms.NumberInput(attrs={"class": "crm_input supplier_paid_input", "step": "0.01", "min": "0"}),
            "description": forms.Textarea(attrs={"class": "crm_input", "rows": 3, "placeholder": "Purchase description"}),
            "notes": forms.Textarea(attrs={"class": "crm_input", "rows": 3, "placeholder": "Internal notes"}),
        }

    def __init__(self, *args, user=None, supplier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        self.initial_supplier = supplier
        supplier_queryset = Supplier.objects.filter(status=SUPPLIER_STATUS_ACTIVE)
        if user and user.is_authenticated and not user.is_superuser:
            supplier_queryset = supplier_queryset.filter(id_company=user.id_company_id)
        self.fields["id_supplier"].queryset = supplier_queryset.order_by("company_name")
        if supplier:
            self.fields["id_supplier"].initial = supplier
            self.fields["id_supplier"].widget = forms.HiddenInput()
        self.fields["id_supplier"].required = True
        self.fields["external_document_number"].required = False
        self.fields["discount_amount"].required = False
        self.fields["paid_amount"].required = False
        self.fields["description"].required = False
        self.fields["notes"].required = False

    def clean_discount_amount(self):
        value = clean_decimal_value(self.cleaned_data.get("discount_amount"), "0.00")
        if value < Decimal("0.00"):
            raise forms.ValidationError("Discount cannot be negative.")
        return value

    def clean_paid_amount(self):
        value = clean_decimal_value(self.cleaned_data.get("paid_amount"), "0.00")
        if value < Decimal("0.00"):
            raise forms.ValidationError("Paid amount cannot be negative.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        supplier = cleaned_data.get("id_supplier") or self.initial_supplier
        if not supplier:
            raise forms.ValidationError("Select a supplier.")
        if not self.request_user.is_superuser and supplier.id_company_id != self.request_user.id_company_id:
            raise forms.ValidationError("Selected supplier does not belong to your company.")
        return cleaned_data


class SupplierPurchaseItemForm(forms.ModelForm):
    id_offer = SupplierProductChoiceField(
        queryset=SupplierOffer.objects.none(),
        widget=SupplierProductSelect(attrs={"class": "crm_input supplier_product_select"}),
        required=True,
        label="Product",
        empty_label="Select product",
    )

    class Meta:
        model = SupplierPurchaseItem
        fields = [
            "id_offer",
            "item_name",
            "description",
            "quantity",
            "unit",
            "unit_price",
            "tax_amount",
        ]
        widgets = {
            "item_name": forms.HiddenInput(attrs={"class": "supplier_item_name"}),
            "description": forms.HiddenInput(attrs={"class": "supplier_item_description"}),
            "quantity": forms.NumberInput(attrs={"class": "crm_input supplier_item_quantity", "step": "0.01", "min": "0.01"}),
            "unit": forms.HiddenInput(attrs={"class": "supplier_item_unit"}),
            "unit_price": forms.NumberInput(attrs={"class": "crm_input supplier_item_price", "step": "0.01", "min": "0"}),
            "tax_amount": forms.NumberInput(attrs={"class": "crm_input supplier_item_tax", "step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, user=None, supplier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        self.initial_supplier = supplier
        offers = SupplierOffer.objects.filter(status=SUPPLIER_STATUS_ACTIVE)
        if supplier:
            offers = offers.filter(id_supplier=supplier)
        if user and user.is_authenticated and not user.is_superuser:
            offers = offers.filter(id_company=user.id_company_id)
        self.fields["id_offer"].queryset = offers.select_related("id_supplier").order_by("id_supplier__company_name", "name")
        self.fields["item_name"].required = False
        self.fields["description"].required = False
        self.fields["unit"].required = False
        self.fields["tax_amount"].required = False

    def clean_quantity(self):
        value = clean_decimal_value(self.cleaned_data.get("quantity"), "1.00")
        if value <= Decimal("0.00"):
            raise forms.ValidationError("Quantity must be greater than zero.")
        return value

    def clean_unit_price(self):
        value = clean_decimal_value(self.cleaned_data.get("unit_price"), "0.00")
        if value < Decimal("0.00"):
            raise forms.ValidationError("Unit cost cannot be negative.")
        return value

    def clean_tax_amount(self):
        value = clean_decimal_value(self.cleaned_data.get("tax_amount"), "0.00")
        if value < Decimal("0.00"):
            raise forms.ValidationError("Tax cannot be negative.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("id_offer")
        if product:
            cleaned_data["item_name"] = product.name
            if not cleaned_data.get("description"):
                cleaned_data["description"] = product.description or ""
            if not cleaned_data.get("unit"):
                cleaned_data["unit"] = product.unit or ""
        return cleaned_data


class RequiredPurchaseItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        valid_rows = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            if form.cleaned_data.get("id_offer"):
                valid_rows += 1
        if valid_rows < 1:
            raise forms.ValidationError("Add at least one purchase product.")


SupplierPurchaseItemFormSet = inlineformset_factory(
    SupplierPurchase,
    SupplierPurchaseItem,
    form=SupplierPurchaseItemForm,
    formset=RequiredPurchaseItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class SupplierDocumentForm(forms.ModelForm):
    class Meta:
        model = SupplierDocument
        fields = [
            "id_supplier",
            "id_purchase",
            "title",
            "document_type",
            "file",
            "notes",
        ]
        widgets = {
            "id_supplier": forms.Select(attrs={"class": "crm_input"}),
            "id_purchase": forms.Select(attrs={"class": "crm_input"}),
            "title": forms.TextInput(attrs={"class": "crm_input", "placeholder": "Document title"}),
            "document_type": forms.Select(attrs={"class": "crm_input"}),
            "file": forms.ClearableFileInput(attrs={"class": "crm_input"}),
            "notes": forms.Textarea(attrs={"class": "crm_input", "rows": 3, "placeholder": "Document notes"}),
        }

    def __init__(self, *args, user=None, supplier=None, purchase=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_user = user
        self.initial_supplier = supplier
        self.initial_purchase = purchase

        suppliers = Supplier.objects.all()
        purchases = SupplierPurchase.objects.select_related("id_supplier")
        if user and user.is_authenticated and not user.is_superuser:
            suppliers = suppliers.filter(id_company=user.id_company_id)
            purchases = purchases.filter(id_company=user.id_company_id)

        self.fields["id_supplier"].queryset = suppliers.order_by("company_name")
        self.fields["id_purchase"].queryset = purchases.order_by("-purchase_date", "-id_supplier_purchase")
        self.fields["id_supplier"].required = False
        self.fields["id_purchase"].required = False
        self.fields["notes"].required = False

        if supplier:
            self.fields["id_supplier"].initial = supplier
            self.fields["id_supplier"].widget = forms.HiddenInput()
        if purchase:
            self.fields["id_purchase"].initial = purchase
            self.fields["id_purchase"].widget = forms.HiddenInput()
            self.fields["id_supplier"].initial = purchase.id_supplier
            self.fields["id_supplier"].widget = forms.HiddenInput()

    def clean_file(self):
        return validate_supplier_document_file(self.cleaned_data.get("file"))

    def clean(self):
        cleaned_data = super().clean()
        supplier = cleaned_data.get("id_supplier") or self.initial_supplier
        purchase = cleaned_data.get("id_purchase") or self.initial_purchase

        if not supplier and not purchase:
            raise forms.ValidationError("Select a supplier or a purchase.")

        if purchase and supplier and purchase.id_supplier_id != supplier.id_supplier:
            raise forms.ValidationError("The selected purchase does not belong to the selected supplier.")

        if not self.request_user.is_superuser:
            if supplier and supplier.id_company_id != self.request_user.id_company_id:
                raise forms.ValidationError("Selected supplier does not belong to your company.")
            if purchase and purchase.id_company_id != self.request_user.id_company_id:
                raise forms.ValidationError("Selected purchase does not belong to your company.")

        return cleaned_data
