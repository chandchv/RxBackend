from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),  # Replace with your last successful migration
    ]

    operations = [
        migrations.RunSQL(
            # Drop the duplicate column if it exists
            "SELECT 1;",  # This is a no-op as a safety measure
            reverse_sql="SELECT 1;"
        ),
    ] 