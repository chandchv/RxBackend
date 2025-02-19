from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        # Add new fields first
        migrations.AddField(
            model_name='doctor',
            name='experience',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='doctor',
            name='qualification',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        # Create new indexes
        migrations.AddIndex(
            model_name='doctor',
            index=models.Index(fields=['license_number'], name='doctor_license_idx'),
        ),
        migrations.AddIndex(
            model_name='doctor',
            index=models.Index(fields=['clinic'], name='doctor_clinic_idx'),
        ),
    ] 