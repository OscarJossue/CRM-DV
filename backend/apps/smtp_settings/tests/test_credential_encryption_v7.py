import base64

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.companies.models import Company
from apps.smtp_settings.forms import SmtpSettingForm
from apps.smtp_settings.models import SmtpSetting
from apps.smtp_settings.security import (
    ENCRYPTED_PREFIX,
    decrypt_smtp_password,
    is_encrypted_smtp_password,
)


TEST_KEY = base64.urlsafe_b64encode(b"v7-smtp-credential-key-material!!"[:32]).decode("ascii")


@override_settings(CREDENTIAL_ENCRYPTION_KEY=TEST_KEY)
class SmtpCredentialEncryptionV7Tests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Encrypted SMTP Company")
        self.setting = SmtpSetting.objects.create(
            id_company=self.company,
            smtp_host="smtp.example.com",
            smtp_port=587,
            use_tls=True,
            use_ssl=False,
            smtp_username="mailer@example.com",
            smtp_password="",
            default_from_email="mailer@example.com",
            from_name="Encrypted SMTP",
            is_active=True,
        )

    def form_data(self, password):
        return {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "use_tls": "on",
            "smtp_username": "mailer@example.com",
            "smtp_password": password,
            "default_from_email": "mailer@example.com",
            "from_name": "Encrypted SMTP",
            "is_active": "on",
        }

    def test_form_encrypts_new_smtp_password_at_rest(self):
        form = SmtpSettingForm(self.form_data("Company-Mail-Secret!"), instance=self.setting)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()

        self.assertTrue(saved.smtp_password.startswith(ENCRYPTED_PREFIX))
        self.assertNotIn("Company-Mail-Secret!", saved.smtp_password)
        self.assertEqual(decrypt_smtp_password(saved.smtp_password), "Company-Mail-Secret!")

    def test_blank_edit_preserves_encrypted_password(self):
        first_form = SmtpSettingForm(self.form_data("Company-Mail-Secret!"), instance=self.setting)
        self.assertTrue(first_form.is_valid(), first_form.errors)
        first = first_form.save()
        ciphertext = first.smtp_password

        second_form = SmtpSettingForm(self.form_data(""), instance=first)
        self.assertTrue(second_form.is_valid(), second_form.errors)
        second = second_form.save()

        self.assertEqual(second.smtp_password, ciphertext)
        self.assertEqual(decrypt_smtp_password(second.smtp_password), "Company-Mail-Secret!")

    def test_management_command_encrypts_legacy_plaintext(self):
        self.setting.smtp_password = "Legacy-Plaintext-Secret!"
        self.setting.save(update_fields=["smtp_password"])

        call_command("encrypt_smtp_credentials", verbosity=0)
        self.setting.refresh_from_db()

        self.assertTrue(is_encrypted_smtp_password(self.setting.smtp_password))
        self.assertNotIn("Legacy-Plaintext-Secret!", self.setting.smtp_password)
        self.assertEqual(
            decrypt_smtp_password(self.setting.smtp_password),
            "Legacy-Plaintext-Secret!",
        )
