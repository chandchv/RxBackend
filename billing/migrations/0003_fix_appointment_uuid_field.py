# Generated manually to fix appointment_id field type

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        # First, remove the foreign key constraint
        migrations.RunSQL(
            "ALTER TABLE billing_bill DROP CONSTRAINT IF EXISTS billing_bill_appointment_id_fkey;",
            reverse_sql="-- No reverse needed"
        ),
        
        # Drop the existing appointment_id column (bigint)
        migrations.RunSQL(
            "ALTER TABLE billing_bill DROP COLUMN IF EXISTS appointment_id;",
            reverse_sql="-- No reverse needed"
        ),
        
        # Add the new appointment_id column as UUID
        migrations.RunSQL(
            "ALTER TABLE billing_bill ADD COLUMN appointment_id uuid NULL;",
            reverse_sql="ALTER TABLE billing_bill DROP COLUMN appointment_id;"
        ),
        
        # Add the foreign key constraint with proper UUID reference
        migrations.RunSQL(
            """
            ALTER TABLE billing_bill 
            ADD CONSTRAINT billing_bill_appointment_id_fkey 
            FOREIGN KEY (appointment_id) REFERENCES users_appointment(id) 
            ON DELETE SET NULL;
            """,
            reverse_sql="ALTER TABLE billing_bill DROP CONSTRAINT billing_bill_appointment_id_fkey;"
        ),
        
        # Add unique constraint for OneToOneField
        migrations.RunSQL(
            "ALTER TABLE billing_bill ADD CONSTRAINT billing_bill_appointment_id_unique UNIQUE (appointment_id);",
            reverse_sql="ALTER TABLE billing_bill DROP CONSTRAINT billing_bill_appointment_id_unique;"
        ),
    ] 