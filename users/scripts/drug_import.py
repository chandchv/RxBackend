import csv
import re
from users.models import Drug  # Adjust as per your Django model import

def clean_price(price_str):
    """Clean and convert price string to float, return 0.00 if invalid"""
    if not price_str or not re.search(r'\d', price_str):
        return 0.00
    try:
        return float(re.sub(r'[^\d.]', '', price_str))
    except ValueError:
        return 0.00

def clean_string(value):
    """Clean string value, return empty string if None"""
    return str(value).strip() if value is not None else ""

def import_drugs_from_csv(csv_file_path):
    successful_imports = 0
    skipped_rows = 0
    error_rows = 0
    
    print("\nStarting drug import process...")
    print("-" * 50)
    
    with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        total_rows = sum(1 for row in csvfile)
        csvfile.seek(0)  # Reset file pointer
        next(reader)  # Skip header row
        
        for row_num, row in enumerate(reader, 1):
            try:
                # Clean and validate required fields
                product_name = clean_string(row.get('product_name', ''))
                if not product_name:
                    print(f"\nRow {row_num}: Skipping - Missing product name")
                    print("-" * 30)
                    skipped_rows += 1
                    continue

                # Clean all fields with default values
                sub_category = clean_string(row.get('sub_category', ''))
                salt_composition = clean_string(row.get('salt_composition', ''))
                product_price = clean_price(row.get('product_price', ''))
                product_manufactured = clean_string(row.get('product_manufactured', ''))
                
                # Create and save the Drug instance
                drug = Drug.objects.create(
                    sub_category=sub_category,
                    product_name=product_name,
                    salt_composition=salt_composition,
                    product_price=product_price,
                    product_manufactured=product_manufactured
                )
                drug.save()
                successful_imports += 1
                
                if row_num % 100 == 0:  # Progress update every 100 rows
                    print(f"Processed {row_num}/{total_rows} rows...")

            except ValueError as e:
                print(f"\nRow {row_num}: Error - Value conversion failed")
                print(f"Product: {product_name}")
                print(f"Error: {str(e)}")
                print("-" * 30)
                error_rows += 1
            except Exception as e:
                print(f"\nRow {row_num}: Unexpected error")
                print(f"Product: {product_name}")
                print(f"Error: {str(e)}")
                print("-" * 30)
                error_rows += 1

    print("\nImport Summary:")
    print("-" * 50)
    print(f"Total rows processed: {total_rows}")
    print(f"Successfully imported: {successful_imports}")
    print(f"Skipped rows: {skipped_rows}")
    print(f"Error rows: {error_rows}")
    print("-" * 50)
