"""Runtime adapters that internationalize legacy company-CRM UI literals.

The adapters intentionally translate UI metadata only. Normal template variables
(client names, addresses, user notes, company names, etc.) remain untouched.
"""

from __future__ import annotations

from functools import wraps
import re

from django.contrib.messages.storage.base import BaseStorage
from django.core.exceptions import ValidationError
from django.db.models import Model
from django.forms.boundfield import BoundField
from django.forms.utils import ErrorList
from django.forms.widgets import ChoiceWidget, Widget
from django.template.base import TextNode, VariableNode
from django.utils.encoding import force_str
from django.utils.functional import Promise
from django.utils.safestring import SafeData, mark_safe

from .ui_translation import (
    EXACT_ES,
    translate_template_fragment,
    translate_ui_text,
)

_PATCHED = False

SKIPPED_PATH_PREFIXES = (
    "/admin/",
    "/api/",
    "/metrics",
    "/health/",
    "/static/",
    "/media/",
)

TRANSLATABLE_VARIABLE_ROOTS = {
    "page_subtitle",
    "page_description",
    "title",
    "subtitle",
    "heading",
    "label",
    "page_title",
    "form_title",
    "section_title",
    "section_description",
    "empty_state_title",
    "empty_state_text",
    "submit_label",
    "cancel_label",
    "button_label",
    "action_label",
    "empty_message",
    "error_title",
    "error_message",
    "success_message",
    "message",
    "status_label",
    "scope_label",
    "status",
    "stage",
    "source",
    "type",
    "method",
    "priority",
    "channel",
    "action",
    "section",
}

TRANSLATABLE_VARIABLE_LEAVES = {
    "label",
    "status",
    "status_label",
    "type",
    "type_label",
    "source",
    "source_label",
    "method",
    "method_label",
    "priority",
    "priority_label",
    "stage",
    "stage_label",
    "channel",
    "channel_label",
    "action",
    "action_label",
    "payment_status",
    "invoice_status",
    "estimate_status",
    "contract_status",
    "project_status",
    "inspection_status",
    "crm_status",
    "display",
    "event_type_label",
}


_HTML_FRAGMENT_RE = re.compile(r"</?[A-Za-z][^>]*>")
_ESCAPED_HTML_FRAGMENT_RE = re.compile(r"&lt;/?[A-Za-z][^&]*&gt;", re.I)


def _is_rendered_html(output):
    """Return True when a template variable already contains rendered markup.

    Bound fields such as ``{{ form.status }}`` render to a SafeString containing
    ``<select>`` and ``<option>`` elements. Passing that HTML through
    ``translate_ui_text`` translates tag/attribute names (for example
    ``select`` -> ``seleccionar``), destroys the control and exposes every option
    as plain text. Choice labels are translated separately by
    ``ChoiceWidget.create_option``, so rendered markup must remain untouched.
    """
    if not isinstance(output, str):
        return False
    if isinstance(output, SafeData) and ("<" in output or ">" in output):
        return True
    return bool(
        _HTML_FRAGMENT_RE.search(output)
        or _ESCAPED_HTML_FRAGMENT_RE.search(output)
    )


def _variable_should_translate(token, output):
    expression = token.split("|")[0].strip()
    parts = [part for part in expression.split(".") if part]
    root = parts[0] if parts else ""
    leaf = parts[-1] if parts else ""

    # Django's built-in widget templates expose machine attributes through
    # variables such as ``widget.type`` and ``widget.attrs.placeholder``.
    # Translating those values can turn type="password" into invalid HTML and
    # break form controls. Widget labels/placeholders are translated earlier by
    # the dedicated Widget/ChoiceWidget adapters, so the rendered widget
    # internals must remain untouched here.
    if root in {"widget", "attrs"}:
        return False
    if leaf in {
        "name",
        "value",
        "id",
        "class",
        "type",
        "required",
        "disabled",
        "selected",
        "checked",
        "multiple",
    } and root not in TRANSLATABLE_VARIABLE_ROOTS:
        return False

    if root in TRANSLATABLE_VARIABLE_ROOTS or leaf in TRANSLATABLE_VARIABLE_LEAVES:
        return True

    if "get_" in expression and expression.endswith("_display"):
        return True

    # Arbitrary template variables may contain company/customer-entered data.
    # Translate only explicitly recognized UI metadata roots/leaves above.
    return False


def _ui_translation_context(context) -> bool:
    try:
        request = context.get("request")
    except Exception:
        request = None

    if not request:
        # Email/PDF templates rendered inside translation.override() are allowed.
        return True

    path = getattr(request, "path", "") or ""
    return not any(path.startswith(prefix) for prefix in SKIPPED_PATH_PREFIXES)


def _translate_error_data(data):
    if isinstance(data, (str, Promise)):
        return translate_ui_text(force_str(data))
    if isinstance(data, ValidationError):
        if hasattr(data, "message") and isinstance(data.message, str):
            data.message = translate_ui_text(data.message)
        return data
    if isinstance(data, (list, tuple)):
        return type(data)(_translate_error_data(item) for item in data)
    return data


def install_runtime_translation_adapters():
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    original_text_render = TextNode.render
    original_text_render_annotated = TextNode.render_annotated

    @wraps(original_text_render)
    def text_render(self, context):
        output = original_text_render(self, context)
        if not _ui_translation_context(context):
            return output
        return mark_safe(translate_template_fragment(output))

    @wraps(original_text_render_annotated)
    def text_render_annotated(self, context):
        output = original_text_render_annotated(self, context)
        if not _ui_translation_context(context):
            return output
        return mark_safe(translate_template_fragment(output))

    TextNode.render = text_render
    TextNode.render_annotated = text_render_annotated

    original_variable_render = VariableNode.render

    @wraps(original_variable_render)
    def variable_render(self, context):
        output = original_variable_render(self, context)
        if not _ui_translation_context(context):
            return output
        token = str(getattr(self.filter_expression, "token", "") or "")
        if (
            isinstance(output, str)
            and not _is_rendered_html(output)
            and _variable_should_translate(token, output)
        ):
            return translate_ui_text(output)
        return output

    VariableNode.render = variable_render

    original_boundfield_init = BoundField.__init__

    @wraps(original_boundfield_init)
    def boundfield_init(self, form, field, name):
        original_boundfield_init(self, form, field, name)
        if isinstance(self.label, (str, Promise)):
            self.label = translate_ui_text(force_str(self.label))
        if isinstance(self.help_text, (str, Promise)):
            self.help_text = translate_ui_text(force_str(self.help_text))

    BoundField.__init__ = boundfield_init

    original_widget_get_context = Widget.get_context

    @wraps(original_widget_get_context)
    def widget_get_context(self, name, value, attrs):
        context = original_widget_get_context(self, name, value, attrs)
        final_attrs = context.get("widget", {}).get("attrs", {})
        for key in ("placeholder", "title", "aria-label", "alt"):
            current = final_attrs.get(key)
            if isinstance(current, (str, Promise)):
                final_attrs[key] = translate_ui_text(force_str(current))
        return context

    Widget.get_context = widget_get_context

    original_create_option = ChoiceWidget.create_option

    @wraps(original_create_option)
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        if isinstance(label, (str, Promise)):
            label = translate_ui_text(force_str(label))
        return original_create_option(self, name, value, label, selected, index, subindex, attrs)

    ChoiceWidget.create_option = create_option

    original_get_field_display = Model._get_FIELD_display

    @wraps(original_get_field_display)
    def get_field_display(self, field):
        value = original_get_field_display(self, field)
        return translate_ui_text(value) if isinstance(value, str) else value

    Model._get_FIELD_display = get_field_display

    original_add = BaseStorage.add

    @wraps(original_add)
    def storage_add(self, level, message, extra_tags=""):
        if isinstance(message, (str, Promise)):
            message = translate_ui_text(force_str(message))
        return original_add(self, level, message, extra_tags)

    BaseStorage.add = storage_add

    original_errorlist_init = ErrorList.__init__

    @wraps(original_errorlist_init)
    def errorlist_init(self, initlist=None, error_class=None, renderer=None, field_id=None):
        if initlist is not None:
            initlist = _translate_error_data(initlist)
        return original_errorlist_init(
            self,
            initlist=initlist,
            error_class=error_class,
            renderer=renderer,
            field_id=field_id,
        )

    ErrorList.__init__ = errorlist_init
