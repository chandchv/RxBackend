# Generated by Django 5.1.3 on 2024-11-25 12:29

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_alter_userprofile_address_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="address",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="license_number",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="medical_degree",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="phone_number",
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="pincode",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="state_council",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="title",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]