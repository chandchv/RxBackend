from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0024_remove_labtest_collection_date_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            # Enable uuid-ossp extension for uuid_generate_v4()
            sql="CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";",
            reverse_sql="DROP EXTENSION IF EXISTS \"uuid-ossp\";"
        ),
        # First, add a temporary UUID column
        migrations.RunSQL(
            sql="""
            ALTER TABLE users_bill 
            ADD COLUMN appointment_id_new uuid;
            """,
            reverse_sql="""
            ALTER TABLE users_bill 
            DROP COLUMN IF EXISTS appointment_id_new;
            """
        ),
        # Then update the new column with UUIDs from appointments table
        migrations.RunSQL(
            sql="""
            UPDATE users_bill b
            SET appointment_id_new = a.id
            FROM users_appointment a
            WHERE b.appointment_id::text = a.id::text;
            """,
            reverse_sql=""
        ),
        # Drop the old column and rename the new one
        migrations.RunSQL(
            sql="""
            ALTER TABLE users_bill 
            DROP COLUMN appointment_id;
            
            ALTER TABLE users_bill 
            RENAME COLUMN appointment_id_new TO appointment_id;
            """,
            reverse_sql=""
        ),
        # Add foreign key constraint
        migrations.RunSQL(
            sql="""
            ALTER TABLE users_bill
            ADD CONSTRAINT users_bill_appointment_id_fk
            FOREIGN KEY (appointment_id)
            REFERENCES users_appointment(id)
            ON DELETE CASCADE;
            """,
            reverse_sql="""
            ALTER TABLE users_bill
            DROP CONSTRAINT IF EXISTS users_bill_appointment_id_fk;
            """
        ),
    ] 