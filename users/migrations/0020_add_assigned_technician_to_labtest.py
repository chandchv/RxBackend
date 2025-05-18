from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0019_appointment_fee_appointment_payment_intent_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='labtest',
            name='assigned_technician',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ] 