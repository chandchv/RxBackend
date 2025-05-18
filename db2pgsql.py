from sqlalchemy import create_engine, inspect
import pandas as pd

# Define DB connections
sqlite_engine = create_engine('sqlite:///db.sqlite3')
postgres_engine = create_engine('postgresql://postgres:admin@localhost:5432/rxdoctor')

# Use SQLAlchemy's Inspector to list table names
inspector = inspect(sqlite_engine)
tables = inspector.get_table_names()

for table in tables:
    print(f"Migrating table: {table}")
    df = pd.read_sql_table(table, sqlite_engine)
    df.to_sql(table, postgres_engine, if_exists='append', index=False)

print("✅ Migration complete.")
