# Generated manually to fix appointment_id field type in ConsultationBilling

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_fix_appointment_uuid_field'),
        ('users', '0001_initial'),
    ]

    operations = [
        # First, remove the foreign key constraint for ConsultationBilling
        migrations.RunSQL(
            "ALTER TABLE billing_consultationbilling DROP CONSTRAINT IF EXISTS billing_consultationbilling_appointment_id_fkey;",
            reverse_sql="-- No reverse needed"
        ),
        
        # Drop the existing appointment_id column (bigint)
        migrations.RunSQL(
            "ALTER TABLE billing_consultationbilling DROP COLUMN IF EXISTS appointment_id;",
            reverse_sql="-- No reverse needed"
        ),
        
        # Add the new appointment_id column as UUID
        migrations.RunSQL(
            "ALTER TABLE billing_consultationbilling ADD COLUMN appointment_id uuid NULL;",
            reverse_sql="ALTER TABLE billing_consultationbilling DROP COLUMN appointment_id;"
        ),
        
        # Add the foreign key constraint with proper UUID reference
        migrations.RunSQL(
            """
            ALTER TABLE billing_consultationbilling 
            ADD CONSTRAINT billing_consultationbilling_appointment_id_fkey 
            FOREIGN KEY (appointment_id) REFERENCES users_appointment(id) 
            ON DELETE CASCADE;
            """,
            reverse_sql="ALTER TABLE billing_consultationbilling DROP CONSTRAINT billing_consultationbilling_appointment_id_fkey;"
        ),
        
        # Add unique constraint for OneToOneField
        migrations.RunSQL(
            "ALTER TABLE billing_consultationbilling ADD CONSTRAINT billing_consultationbilling_appointment_id_unique UNIQUE (appointment_id);",
            reverse_sql="ALTER TABLE billing_consultationbilling DROP CONSTRAINT billing_consultationbilling_appointment_id_unique;"
        ),
    ] 