from django.db import migrations


def normalize_client_codes(apps, schema_editor):
    Client = apps.get_model("clients", "Client")
    for client in Client.objects.all().only("id_client", "client_code").iterator():
        expected = f"CLI-{client.id_client:06d}"
        if client.client_code != expected:
            Client.objects.filter(id_client=client.id_client).update(client_code=expected)


def reverse_client_codes(apps, schema_editor):
    Client = apps.get_model("clients", "Client")
    for client in Client.objects.all().only("id_client", "client_code").iterator():
        previous = f"CL_{client.id_client:06d}"
        if client.client_code != previous:
            Client.objects.filter(id_client=client.id_client).update(client_code=previous)


class Migration(migrations.Migration):
    dependencies = [("clients", "0004_client_dni")]

    operations = [
        migrations.RunPython(normalize_client_codes, reverse_client_codes),
    ]
