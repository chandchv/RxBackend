# Generated by Django 5.1.3 on 2024-11-30 11:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0009_patient"),
    ]

    operations = [
        migrations.CreateModel(
            name="Appointment",
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
                ("doctor", models.CharField(max_length=100)),
                ("appointment_date", models.DateTimeField()),
                ("symptoms", models.TextField()),
                ("diagnosis", models.TextField()),
                ("medications", models.TextField()),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="users.patient"
                    ),
                ),
            ],
        ),
    ]
