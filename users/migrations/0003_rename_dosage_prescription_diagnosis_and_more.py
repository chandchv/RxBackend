# Generated by Django 5.1.3 on 2024-12-16 10:28

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_patient_clinic_patient_created_at_patient_updated_at_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="prescription",
            old_name="dosage",
            new_name="diagnosis",
        ),
        migrations.RemoveField(
            model_name="prescription",
            name="instructions",
        ),
        migrations.RemoveField(
            model_name="prescription",
            name="medication",
        ),
        migrations.AddField(
            model_name="prescription",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="prescription",
            name="notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="prescription",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="patient",
            name="clinic",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="users.clinic"
            ),
        ),
        migrations.AlterField(
            model_name="prescription",
            name="date",
            field=models.DateField(default=django.utils.timezone.now),
        ),
        migrations.CreateModel(
            name="PrescriptionItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("medicine", models.CharField(max_length=200)),
                ("dosage", models.CharField(max_length=100)),
                ("frequency", models.CharField(max_length=100)),
                ("duration", models.CharField(max_length=100)),
                ("instructions", models.TextField(blank=True)),
                (
                    "prescription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="users.prescription",
                    ),
                ),
            ],
        ),
    ]