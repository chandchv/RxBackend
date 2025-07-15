# Aster Labs Test Scraper

This Python scraper extracts test information from the Aster Labs website and formats it according to your CSV template structure.

## Features

- 🔍 **Comprehensive Scraping**: Extracts test names, prices, categories, and detailed information
- 📊 **Smart Categorization**: Automatically categorizes tests based on keywords
- 💰 **Price Extraction**: Extracts and formats prices from the website
- 🏠 **Home Collection Detection**: Identifies tests that offer home collection
- ⏱️ **Turnaround Time**: Extracts or estimates test turnaround times
- 📄 **Multiple Output Formats**: Saves data in both CSV and JSON formats
- 🔄 **Pagination Support**: Can scrape multiple pages automatically
- 🛡️ **Error Handling**: Robust error handling with retries and logging
- ⚡ **Rate Limiting**: Respectful scraping with delays between requests

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements_scraper.txt
   ```

2. **Verify Installation**:
   ```bash
   python -c "import requests, bs4; print('Dependencies installed successfully!')"
   ```

## Usage

### Basic Usage

```bash
# Run the scraper with default settings
python run_scraper.py

# Run with custom options
python run_scraper.py --max-pages 10 --output my_tests.csv
```

### Advanced Usage

```bash
# Scrape specific URL
python run_scraper.py --url "https://www.asterlabs.in/mumbai/tests"

# Limit pages and save to specific file
python run_scraper.py --max-pages 3 --output aster_tests.csv

# Also save JSON for debugging
python run_scraper.py --json

# Full example
python run_scraper.py --url "https://www.asterlabs.in/bengaluru/tests" --max-pages 5 --output bengaluru_tests.csv --json
```

### Direct Python Usage

```python
from aster_labs_advanced_scraper import AsterLabsAdvancedScraper

# Create scraper instance
scraper = AsterLabsAdvancedScraper()

# Run scraper
result = scraper.run_scraper(
    tests_url="https://www.asterlabs.in/bengaluru/tests",
    max_pages=5
)

if result:
    print(f"Scraped {result['total_count']} tests")
    print(f"CSV file: {result['csv_file']}")
    print(f"JSON file: {result['json_file']}")
```

## Output Format

The scraper generates a CSV file with the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `name` | Test name | "CORTISOL, SALIVA" |
| `short_code` | Generated short code | "CS" |
| `description` | Test description | "Measures cortisol levels in saliva" |
| `category` | Test category | "Hormones" |
| `preparation_instructions` | Patient preparation | "Fasting not required" |
| `price` | Test price in INR | "2200" |
| `turnaround_time_hours` | Time to results | "24" |
| `offers_home_collection` | Home collection available | "true" |
| `specific_instructions` | Additional instructions | "Sample collection method: Lab Visit & Home Collection" |

## Test Categories

The scraper automatically categorizes tests into the following categories:

- **Hematology**: Blood tests, CBC, hemoglobin, etc.
- **Diabetes**: Glucose, HbA1c, insulin tests
- **Thyroid**: TSH, T3, T4, thyroid function tests
- **Liver**: Liver function tests, ALT, AST, bilirubin
- **Kidney**: Kidney function tests, creatinine, urea
- **Lipid**: Cholesterol, triglyceride tests
- **Vitamins**: Vitamin D, B12, folate tests
- **Hormones**: Cortisol, testosterone, hormone tests
- **Urine**: Urinalysis, urine tests
- **Cardiac**: Cardiac markers, troponin, BNP
- **Inflammation**: CRP, ESR, inflammatory markers
- **Electrolytes**: Sodium, potassium, electrolyte tests
- **Tumor Markers**: PSA, AFP, CEA, cancer markers
- **Allergy**: Allergy tests, IgE
- **Microbiology**: Culture, sensitivity tests
- **Immunology**: Antibody, antigen tests
- **Molecular**: PCR, genetic, molecular tests

## Configuration

### Customizing Categories

You can modify the category mapping in the `AsterLabsAdvancedScraper` class:

```python
self.category_mapping = {
    'your_category': ['keyword1', 'keyword2', 'keyword3'],
    # Add more categories as needed
}
```

### Adjusting Delays

To be more respectful to the server, you can adjust delays:

```python
# In the scrape_tests_page method
time.sleep(1)  # Delay between tests
time.sleep(2)  # Delay between pages
```

## Error Handling

The scraper includes comprehensive error handling:

- **Network Errors**: Automatic retries with exponential backoff
- **Parsing Errors**: Graceful handling of malformed HTML
- **Rate Limiting**: Respectful delays between requests
- **Logging**: Detailed logs saved to `aster_labs_scraper.log`

## Troubleshooting

### Common Issues

1. **No tests found**:
   - Check if the website structure has changed
   - Verify the URL is correct
   - Check network connection

2. **Permission denied**:
   - Ensure you have write permissions in the directory
   - Check if the output file is open in another program

3. **Network timeouts**:
   - Increase timeout values in the scraper
   - Check your internet connection
   - Try again later if the server is busy

### Debug Mode

For debugging, the scraper saves detailed logs and JSON output:

```bash
python run_scraper.py --json
```

Check the generated JSON file for raw scraped data and the log file for detailed execution information.

## Legal and Ethical Considerations

- **Respect robots.txt**: Check the website's robots.txt file
- **Rate limiting**: The scraper includes delays to be respectful
- **Terms of service**: Ensure scraping complies with the website's terms
- **Data usage**: Use scraped data responsibly and in accordance with applicable laws

## Sample Output

```
🔬 Aster Labs Test Scraper
========================================
URL: https://www.asterlabs.in/bengaluru/tests
Max pages: 5
Output file: auto-generated
========================================

✅ Successfully scraped 150 tests!
📁 CSV file: aster_labs_tests_20241201_143022.csv

💰 Price Statistics:
   Min: ₹200
   Max: ₹5000
   Average: ₹1200

📂 Top Categories:
   General: 45 tests
   Hematology: 25 tests
   Diabetes: 20 tests
   Thyroid: 15 tests
   Liver: 12 tests

🎉 Scraping completed successfully!
```

## Support

If you encounter issues:

1. Check the log file: `aster_labs_scraper.log`
2. Verify the website structure hasn't changed
3. Ensure all dependencies are installed
4. Check your network connection

## Contributing

To improve the scraper:

1. Test with different URLs and page structures
2. Add new category mappings
3. Improve error handling
4. Add new output formats
5. Optimize performance

## License

This scraper is provided for educational and research purposes. Please use responsibly and in accordance with applicable laws and website terms of service. 