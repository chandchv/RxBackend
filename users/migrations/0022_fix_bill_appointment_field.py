from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0021_add_missing_fields_to_labtest'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bill',
            name='appointment',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bill',
                to='users.appointment',
                to_field='id',
            ),
        ),
        migrations.RunSQL(
            # Convert existing bigint to uuid
            sql="""
            ALTER TABLE users_bill 
            ALTER COLUMN appointment_id TYPE uuid 
            USING CAST(CASE WHEN appointment_id IS NOT NULL 
                          THEN uuid_generate_v4() 
                          ELSE NULL 
                     END AS uuid)
            """,
            # Convert back to bigint if needed
            reverse_sql="""
            ALTER TABLE users_bill 
            ALTER COLUMN appointment_id TYPE bigint 
            USING CAST(appointment_id AS bigint)
            """
        ),
        migrations.AlterField(
            model_name='labtest',
            name='prescription',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='users.labtestprescription',
                null=True,
                blank=True,
            ),
        ),
    ] 