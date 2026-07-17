from django.db import migrations, models
from django.utils.text import slugify


def populate_company_slugs(apps, schema_editor):
    Company = apps.get_model("companies", "Company")

    used_slugs = set()

    for company in Company.objects.all().order_by("id_company"):
        base_slug = slugify(company.name) or f"company-{company.id_company}"
        slug = base_slug
        counter = 1

        while slug in used_slugs:
            counter += 1
            slug = f"{base_slug}-{counter}"

        company.slug = slug
        company.save(update_fields=["slug"])
        used_slugs.add(slug)


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0003_alter_company_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="slug",
            field=models.SlugField(
                blank=True,
                max_length=180,
                null=True,
            ),
        ),
        migrations.RunPython(
            populate_company_slugs,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="company",
            name="slug",
            field=models.SlugField(
                blank=True,
                max_length=180,
            ),
        ),
        migrations.AddConstraint(
            model_name="company",
            constraint=models.UniqueConstraint(
                fields=["slug"],
                name="company_slug_unique",
            ),
        ),
    ]