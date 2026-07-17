from django import forms
from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation
from django.utils.html import conditional_escape

from apps.core.ui_translation import translate_ui_text


class WorkspaceUiTranslationTests(SimpleTestCase):
    def test_raw_status_is_humanized_in_both_languages(self):
        with translation.override("en"):
            self.assertEqual(translate_ui_text("pending_send"), "Pending Send")
        with translation.override("es"):
            self.assertEqual(translate_ui_text("pending_send"), "Pendiente de envío")

    def test_action_tooltips_and_visible_labels_are_translated(self):
        template = Template(
            '<a data-tooltip="Download PDF" aria-label="View Details">'
            '<span>View</span>{{ status }}</a>'
        )
        with translation.override("es"):
            output = template.render(Context({"status": "pending_send"}))
        self.assertIn('data-tooltip="Descargar PDF"', output)
        self.assertIn('aria-label="Ver detalles"', output)
        self.assertIn('<span>Ver</span>', output)
        self.assertIn('Pendiente de envío', output)


    def test_choice_widgets_keep_valid_html_in_spanish(self):
        class StatusForm(forms.Form):
            status = forms.ChoiceField(
                choices=(("new", "New"), ("qualified", "Qualified"), ("won", "Won")),
                widget=forms.Select(attrs={"class": "crm_input opportunity_status_select"}),
            )
            source = forms.ChoiceField(
                choices=(("website", "Website"), ("phone", "Phone")),
                widget=forms.Select(attrs={"class": "crm_input opportunity_source_select"}),
            )

        template = Template("{{ form.status }}{{ form.source }}")
        with translation.override("es"):
            output = template.render(Context({"form": StatusForm()}))

        self.assertEqual(output.count("<select"), 2)
        self.assertEqual(output.count("</select>"), 2)
        self.assertIn('name="status"', output)
        self.assertIn('name="source"', output)
        self.assertIn('value="new"', output)
        self.assertIn('value="website"', output)
        self.assertIn(">Nuevo</option>", output)
        self.assertIn(">Calificado</option>", output)
        self.assertNotIn("<seleccionar", output)
        self.assertNotIn("<opción", output)
        self.assertNotIn('nombre="estado"', output)

    def test_safe_html_status_value_is_not_translated_as_markup(self):
        template = Template("{{ status }}")
        rendered_widget = '<select name="status"><option value="active">Active</option></select>'

        with translation.override("es"):
            output = template.render(Context({"status": rendered_widget}))

        self.assertEqual(output, conditional_escape(rendered_widget))

    def test_multiline_platform_copy_uses_exact_translation(self):
        source = (
            "Smart SaaS calendar for CEO Marketing. It pulls subscriptions, renewals, "
            "platform payments,\nSaaS documents, notification logs, inactive companies "
            "and manual internal follow-ups."
        )
        with translation.override("es"):
            self.assertEqual(
                translate_ui_text(source),
                "Calendario SaaS inteligente para CEO Marketing. Reúne suscripciones, "
                "renovaciones, pagos de plataforma, documentos SaaS, registros de "
                "notificaciones, empresas inactivas y seguimientos internos manuales.",
            )

    def test_english_interface_remains_natural(self):
        template = Template('{{ status }}')
        with translation.override("en"):
            output = template.render(Context({"status": "in_progress"}))
        self.assertEqual(output, "In Progress")

    def test_user_entered_names_are_not_changed(self):
        with translation.override("es"):
            self.assertEqual(translate_ui_text("John Smith"), "John Smith")
    def test_platform_copy_uses_curated_natural_spanish(self):
        with translation.override("es"):
            self.assertEqual(
                translate_ui_text("Language & Region"),
                "Idioma y región",
            )
            self.assertEqual(
                translate_ui_text("Subscriptions that need renewal review."),
                "Suscripciones que requieren revisión de renovación.",
            )
            self.assertEqual(
                translate_ui_text("Register a SaaS payment and update billing status."),
                "Registre un pago SaaS y actualice el estado de facturación.",
            )

