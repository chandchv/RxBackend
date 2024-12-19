import csv
import re
import json  # To parse JSON data
from users.models import Drug  # Adjust as per your Django model import

def import_drugs_from_csv(csv_file_path):
    with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                # Check if product_price is empty or invalid
                if not row['product_price'] or not re.search(r'\d', row['product_price']):
                    print(f"Warning: Skipping row with missing or invalid price: {row}")
                    continue  # Skip the row

                # Clean and convert product_price
                product_price = float(re.sub(r'[^\d.]', '', row['product_price']))

                # Parse drug_interactions (JSON data)
                drug_interactions = json.loads(row['drug_interactions'])
                
                # Create and save the Drug instance
                drug = Drug.objects.create(
                    sub_category=row['sub_category'],
                    product_name=row['product_name'],
                    salt_composition=row['salt_composition'],
                    product_price=product_price,
                    product_manufactured=row['product_manufactured'],
                    medicine_desc=row['medicine_desc'],
                    side_effects=row['side_effects'],
                    drug_interactions=drug_interactions
                )
                drug.save()

            except ValueError as e:
                print(f"ValueError: Could not convert or parse row: {row} -> {e}")
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: Invalid JSON in drug_interactions: {row['drug_interactions']} -> {e}")
