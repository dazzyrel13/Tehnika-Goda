# Generated manually for security hardening

import django.core.validators
from django.db import migrations, models

import catalog.models
import utils.pdf_validate


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0015_vehicle_filter_indexes_and_color_backfill"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="vehicle",
            name="catalog_vehicle_desc_txt_idx",
        ),
        migrations.AlterField(
            model_name="inspectionreport",
            name="pdf_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=catalog.models.inspection_report_path,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=["pdf"]
                    ),
                    utils.pdf_validate.validate_pdf_upload,
                ],
                verbose_name="PDF отчет (полный)",
            ),
        ),
    ]
