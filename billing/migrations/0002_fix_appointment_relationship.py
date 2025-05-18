from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consultationbilling',
            name='appointment',
            field=models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='consultation_billing', to='users.appointment', to_field='id'),
        ),
    ] 