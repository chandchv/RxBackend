from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0020_add_assigned_technician_to_labtest'),
    ]

    operations = [
        migrations.AddField(
            model_name='labtest',
            name='expected_collection_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='labtest',
            name='collection_notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='labtest',
            name='collection_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='labtest',
            name='processing_notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='labtest',
            name='expected_completion_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='labtest',
            name='test_results',
            field=models.TextField(blank=True, null=True),
        ),
    ] 