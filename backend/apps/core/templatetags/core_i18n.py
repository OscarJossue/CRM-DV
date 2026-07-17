from django import template

from apps.core.ui_translation import translate_ui_text

register = template.Library()


@register.filter(name="ui_trans")
def ui_trans(value):
    return translate_ui_text(value)
