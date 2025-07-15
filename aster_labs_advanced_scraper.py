import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import json
from urllib.parse import urljoin, urlparse, parse_qs
import logging
from datetime import datetime
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aster_labs_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AsterLabsAdvancedScraper:
    def __init__(self):
        self.base_url = "https://www.asterlabs.in"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
        
        # Test categories mapping
        self.category_mapping = {
            'hematology': ['blood', 'cbc', 'hemoglobin', 'platelet', 'wbc', 'rbc', 'esr', 'pcv'],
            'diabetes': ['diabetes', 'glucose', 'sugar', 'hba1c', 'insulin', 'diabetic'],
            'thyroid': ['thyroid', 'tsh', 't3', 't4', 'ft3', 'ft4', 'thyroglobulin'],
            'liver': ['liver', 'alt', 'ast', 'bilirubin', 'alp', 'ggt', 'albumin', 'protein'],
            'kidney': ['kidney', 'creatinine', 'urea', 'bun', 'uric acid', 'renal', 'egfr'],
            'lipid': ['lipid', 'cholesterol', 'triglyceride', 'hdl', 'ldl', 'vldl'],
            'vitamins': ['vitamin', 'vit d', 'vitamin d', 'b12', 'folate', 'vitamin b'],
            'hormones': ['hormone', 'cortisol', 'testosterone', 'estrogen', 'progesterone', 'fsh', 'lh'],
            'urine': ['urine', 'urinalysis', 'microalbumin'],
            'cardiac': ['cardiac', 'troponin', 'ck-mb', 'bnp', 'nt-probnp'],
            'inflammation': ['crp', 'esr', 'ferritin', 'inflammatory'],
            'electrolytes': ['sodium', 'potassium', 'chloride', 'bicarbonate', 'electrolyte'],
            'tumor_markers': ['psa', 'afp', 'cea', 'ca125', 'ca199', 'tumor'],
            'allergy': ['allergy', 'ige', 'allergen'],
            'microbiology': ['culture', 'sensitivity', 'bacterial', 'fungal', 'viral'],
            'immunology': ['immunology', 'antibody', 'antigen', 'autoimmune'],
            'molecular': ['pcr', 'dna', 'rna', 'genetic', 'molecular'],
        }
        
    def get_page(self, url, retries=3):
        """Fetch a web page with error handling and retries"""
        for attempt in range(retries):
            try:
                logger.info(f"Fetching: {url} (attempt {attempt + 1})")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch {url} after {retries} attempts")
                    return None
    
    def extract_price(self, price_element):
        """Extract price from price element"""
        if not price_element:
            return "0"
        
        price_text = price_element.get_text(strip=True)
        # Extract numbers from price text (e.g., "₹2,200" -> "2200")
        price_match = re.search(r'₹?([\d,]+)', price_text)
        if price_match:
            return price_match.group(1).replace(',', '')
        return "0"
    
    def extract_test_name(self, title_element):
        """Extract test name from title element"""
        if not title_element:
            return "Unknown Test"
        
        test_name = title_element.get_text(strip=True)
        # Clean up the test name
        test_name = re.sub(r'\s+', ' ', test_name)  # Remove extra whitespace
        test_name = test_name.replace('&amp;', '&')  # Fix HTML entities
        return test_name
    
    def extract_test_method(self, method_element):
        """Extract test method from method element"""
        if not method_element:
            return "false"
        
        method_text = method_element.get_text(strip=True).lower()
        # Extract method from text like "Test method - Lab Visit & Home Collection"
        if "home collection" in method_text or "home" in method_text:
            return "true"
        return "false"
    
    def extract_turnaround_time(self, time_element):
        """Extract turnaround time from time element"""
        if not time_element:
            return "24"  # Default 24 hours
        
        time_text = time_element.get_text(strip=True).lower()
        
        # Look for specific time patterns
        if "same day" in time_text or "today" in time_text:
            return "4"  # 4 hours for same day
        elif "next day" in time_text or "tomorrow" in time_text:
            return "24"  # 24 hours
        elif "2-3" in time_text or "3-4" in time_text:
            return "72"  # 3 days
        elif "week" in time_text:
            return "168"  # 1 week
        elif "24 hours" in time_text or "24hr" in time_text:
            return "24"
        elif "48 hours" in time_text or "48hr" in time_text:
            return "48"
        elif "72 hours" in time_text or "72hr" in time_text:
            return "72"
        else:
            # Try to extract hours from text
            hours_match = re.search(r'(\d+)\s*hours?', time_text, re.IGNORECASE)
            if hours_match:
                return hours_match.group(1)
            return "24"  # Default
    
    def extract_parameters(self, parameters_container):
        """Extract test parameters"""
        if not parameters_container:
            return "Standard parameters"
        
        parameters = []
        
        # Look for parameter elements
        param_elements = parameters_container.find_all(class_=re.compile(r'popular-tests-parameters'))
        
        for param in param_elements:
            param_text = param.get_text(strip=True)
            if param_text and param_text != "..." and len(param_text) > 1:
                parameters.append(param_text)
        
        # If no parameters found, try alternative selectors
        if not parameters:
            # Look for any text that might be parameters
            all_text = parameters_container.get_text()
            # Extract potential parameter names (usually 2-4 letter codes)
            param_matches = re.findall(r'\b[A-Z]{2,4}\b', all_text)
            parameters.extend(param_matches[:5])  # Limit to 5 parameters
        
        if parameters:
            return ", ".join(parameters[:3])  # Limit to first 3 parameters
        return "Standard parameters"
    
    def generate_short_code(self, test_name):
        """Generate short code from test name"""
        if not test_name:
            return "TEST"
        
        # Remove common words and take first letters
        words = test_name.upper().split()
        short_code = ""
        
        # Common words to skip
        skip_words = {'THE', 'AND', 'FOR', 'WITH', 'TEST', 'BLOOD', 'SERUM', 'URINE', 'PLASMA', 'WHOLE'}
        
        for word in words:
            if len(word) > 2 and word not in skip_words:
                short_code += word[0]
        
        if len(short_code) < 2:
            # Fallback: take first 3-4 letters
            short_code = test_name[:4].upper().replace(' ', '')
        
        return short_code[:5]  # Limit to 5 characters
    
    def generate_category(self, test_name):
        """Generate category based on test name"""
        test_name_lower = test_name.lower()
        
        for category, keywords in self.category_mapping.items():
            if any(keyword in test_name_lower for keyword in keywords):
                return category.replace('_', ' ').title()
        
        return "General"
    
    def generate_description(self, test_name, parameters):
        """Generate description based on test name and parameters"""
        test_name_lower = test_name.lower()
        
        # Common test descriptions
        descriptions = {
            'cbc': "Measures various components of blood including red blood cells, white blood cells, and platelets",
            'diabetes': "Measures blood glucose levels to assess diabetes control and management",
            'thyroid': "Evaluates thyroid function by measuring thyroid hormone levels",
            'liver': "Assesses liver function by measuring liver enzymes and proteins",
            'kidney': "Evaluates kidney function by measuring waste products in blood",
            'lipid': "Measures cholesterol and triglyceride levels to assess cardiovascular risk",
            'vitamin': "Measures vitamin levels to assess nutritional status",
            'hormone': "Measures hormone levels to assess endocrine function",
            'urine': "Analyzes urine composition to assess kidney and metabolic function",
            'cardiac': "Measures cardiac markers to assess heart function and damage",
            'inflammation': "Measures inflammatory markers to assess inflammation levels",
            'electrolytes': "Measures electrolyte balance in the body",
            'tumor': "Measures tumor markers to assess cancer risk and monitoring",
            'allergy': "Measures allergy markers to assess allergic responses",
            'microbiology': "Identifies and analyzes microorganisms in samples",
            'immunology': "Measures immune system markers and antibodies",
            'molecular': "Analyzes genetic material for molecular diagnostics"
        }
        
        for keyword, description in descriptions.items():
            if keyword in test_name_lower:
                return description
        
        return f"Comprehensive {test_name} test to assess health parameters"
    
    def generate_preparation_instructions(self, test_name):
        """Generate preparation instructions based on test type"""
        test_name_lower = test_name.lower()
        
        if any(word in test_name_lower for word in ['glucose', 'sugar', 'diabetes', 'lipid', 'cholesterol', 'triglyceride']):
            return "Fasting required for 8-12 hours before the test"
        elif any(word in test_name_lower for word in ['thyroid', 'hormone', 'cortisol', 'insulin']):
            return "Fasting not required. Avoid strenuous exercise 24 hours before"
        elif any(word in test_name_lower for word in ['urine', 'urinalysis', 'microalbumin']):
            return "First morning urine sample preferred. Avoid excessive fluid intake"
        elif any(word in test_name_lower for word in ['vitamin', 'b12', 'd3', 'folate']):
            return "Fasting not required. Avoid supplements 24 hours before"
        elif any(word in test_name_lower for word in ['psa', 'prostate']):
            return "Fasting not required. Avoid ejaculation 48 hours before"
        elif any(word in test_name_lower for word in ['culture', 'bacterial']):
            return "Follow specific collection instructions provided by the lab"
        else:
            return "Fasting not required"
    
    def scrape_test_details(self, test_url):
        """Scrape detailed information from individual test page"""
        full_url = urljoin(self.base_url, test_url)
        response = self.get_page(full_url)
        
        if not response:
            return {}
        
        soup = BeautifulSoup(response.content, 'html.parser')
        details = {}
        
        # Extract additional details if available
        # This would need to be customized based on the actual test page structure
        
        return details
    
    def scrape_tests_page(self, url, max_pages=None):
        """Scrape tests from the main tests page with pagination support"""
        logger.info(f"Scraping tests from: {url}")
        
        all_tests = []
        # ----- Pagination Setup -----
        # Many pages after the first do not expose a visible "next" link. However the
        # tests listing endpoint supports simple page based pagination via the
        # query-string (e.g. ?page=7).  To avoid relying on brittle DOM elements we
        # derive a base URL (without the page param) and then iterate by manually
        # incrementing the page number until no more tests are found or the optional
        # max_pages limit is reached.

        parsed_initial = urlparse(url)
        base_url = parsed_initial._replace(query="", params="", fragment="").geturl()

        # Determine the starting page from the supplied URL (defaults to 1 if absent)
        query_params = parse_qs(parsed_initial.query)
        try:
            page = int(query_params.get("page", ["1"])[0])
        except ValueError:
            page = 1

        current_url = f"{base_url}?page={page}"
        
        while True:
            logger.info(f"Scraping page {page}")
            
            response = self.get_page(current_url)
            if not response:
                logger.error(f"Failed to fetch page {page}")
                break
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all test links
            test_links = soup.find_all('a', class_='highpertext')
            
            if not test_links:
                logger.info(f"No more test links found on page {page}")
                break
            
            logger.info(f"Found {len(test_links)} test links on page {page}")
            
            page_tests = []
            for i, link in enumerate(test_links):
                try:
                    logger.info(f"Processing test {i+1}/{len(test_links)} on page {page}")
                    
                    # Extract test information
                    test_data = self.extract_test_data(link)
                    if test_data:
                        page_tests.append(test_data)
                    
                    # Add delay to be respectful to the server
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error processing test {i+1} on page {page}: {e}")
                    continue
            
            all_tests.extend(page_tests)
            logger.info(f"Completed page {page}. Total tests so far: {len(all_tests)}")
            
            # ----- Determine Next Page -----
            if max_pages and page >= max_pages:
                logger.info(f"Reached maximum pages limit ({max_pages})")
                break

            page += 1
            current_url = f"{base_url}?page={page}"

            # Add a polite delay between page requests
            time.sleep(2)
        
        return all_tests
    
    def extract_test_data(self, link_element):
        """Extract test data from a link element"""
        try:
            # Extract price
            price_element = link_element.find(class_=re.compile(r'selected-swiper-card-rupees'))
            price = self.extract_price(price_element)
            
            # Extract test name
            title_element = link_element.find(class_=re.compile(r'popular-title-meth'))
            if title_element:
                test_name_element = title_element.find(class_=re.compile(r'lab-v-title'))
                test_name = self.extract_test_name(test_name_element)
            else:
                test_name = "Unknown Test"
            
            # Extract test method
            method_element = link_element.find(class_=re.compile(r'block-color'))
            home_collection = self.extract_test_method(method_element)
            
            # Extract turnaround time
            time_element = link_element.find(class_=re.compile(r'lab-time-title'))
            turnaround_time = self.extract_turnaround_time(time_element)
            
            # Extract parameters
            parameters_container = link_element.find(class_=re.compile(r'popular-complete-tests'))
            parameters = self.extract_parameters(parameters_container)
            
            # Generate additional fields
            short_code = self.generate_short_code(test_name)
            category = self.generate_category(test_name)
            description = self.generate_description(test_name, parameters)
            preparation_instructions = self.generate_preparation_instructions(test_name)
            
            # Get test URL for potential detailed scraping
            test_url = link_element.get('href', '')
            
            return {
                'name': test_name,
                'short_code': short_code,
                'description': description,
                'category': category,
                'preparation_instructions': preparation_instructions,
                'price': price,
                'turnaround_time_hours': turnaround_time,
                'offers_home_collection': home_collection,
                'specific_instructions': f"Sample collection method: {method_element.get_text(strip=True) if method_element else 'Lab Visit'}. Parameters: {parameters}",
                'test_url': test_url
            }
            
        except Exception as e:
            logger.error(f"Error extracting test data: {e}")
            return None
    
    def save_to_csv(self, tests, filename=None):
        """Save scraped tests to CSV file"""
        if not tests:
            logger.warning("No tests to save")
            return
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'aster_labs_tests_{timestamp}.csv'
        
        fieldnames = [
            'name', 'short_code', 'description', 'category', 'preparation_instructions',
            'price', 'turnaround_time_hours', 'offers_home_collection', 'specific_instructions'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for test in tests:
                    # Remove test_url from the data to be written
                    test_data = {k: v for k, v in test.items() if k in fieldnames}
                    writer.writerow(test_data)
            
            logger.info(f"Successfully saved {len(tests)} tests to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
            return None
    
    def save_to_json(self, tests, filename=None):
        """Save scraped tests to JSON file for debugging"""
        if not tests:
            logger.warning("No tests to save")
            return
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'aster_labs_tests_{timestamp}.json'
        
        try:
            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(tests, jsonfile, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully saved {len(tests)} tests to {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving to JSON: {e}")
            return None
    
    def run_scraper(self, tests_url="https://www.asterlabs.in/bengaluru/tests", max_pages=5):
        """Main method to run the scraper"""
        logger.info("Starting Aster Labs Advanced Scraper...")
        
        # Scrape tests from the main page
        tests = self.scrape_tests_page(tests_url, max_pages=max_pages)
        
        if tests:
            # Save to CSV
            csv_filename = self.save_to_csv(tests)
            
            # Save to JSON for debugging
            json_filename = self.save_to_json(tests)
            
            # Print summary
            logger.info(f"Scraping completed! Found {len(tests)} tests")
            
            # Calculate statistics
            prices = [int(t['price']) for t in tests if t['price'] != '0']
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                avg_price = sum(prices) / len(prices)
                
                logger.info(f"Price statistics:")
                logger.info(f"  Min: Rs.{min_price}")
                logger.info(f"  Max: Rs.{max_price}")
                logger.info(f"  Average: Rs.{avg_price:.0f}")
            
            # Show sample tests
            logger.info("Sample tests:")
            for i, test in enumerate(tests[:5]):
                logger.info(f"  {i+1}. {test['name']} - Rs.{test['price']} - {test['category']}")
            
            return {
                'tests': tests,
                'csv_file': csv_filename,
                'json_file': json_filename,
                'total_count': len(tests)
            }
        else:
            logger.warning("No tests found")
            return None

def main():
    """Main function to run the scraper"""
    scraper = AsterLabsAdvancedScraper()
    result = scraper.run_scraper(max_pages=3)  # Limit to 3 pages for testing
    
    if result:
        print(f"\n✅ Successfully scraped {result['total_count']} tests from Aster Labs")
        print(f"📁 CSV file: {result['csv_file']}")
        print(f"📄 JSON file: {result['json_file']}")
        
        # Show some statistics
        tests = result['tests']
        prices = [int(t['price']) for t in tests if t['price'] != '0']
        if prices:
            print(f"💰 Price range: ₹{min(prices)} - ₹{max(prices)}")
            print(f"📊 Average price: ₹{sum(prices) / len(prices):.0f}")
        
        # Show categories
        categories = {}
        for test in tests:
            cat = test['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"📂 Categories found: {len(categories)}")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   {cat}: {count} tests")
    else:
        print("❌ No tests were scraped. Please check the website structure or network connection.")

if __name__ == "__main__":
    main() 