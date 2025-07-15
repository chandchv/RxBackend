import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import json
from urllib.parse import urljoin, urlparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AsterLabsScraper:
    def __init__(self):
        self.base_url = "https://www.asterlabs.in"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def get_page(self, url):
        """Fetch a web page with error handling and retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch {url} after {max_retries} attempts")
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
        return test_name
    
    def extract_test_method(self, method_element):
        """Extract test method from method element"""
        if not method_element:
            return "Lab Visit"
        
        method_text = method_element.get_text(strip=True)
        # Extract method from text like "Test method - Lab Visit & Home Collection"
        if "Home Collection" in method_text:
            return "true"
        return "false"
    
    def extract_turnaround_time(self, time_element):
        """Extract turnaround time from time element"""
        if not time_element:
            return "24"  # Default 24 hours
        
        time_text = time_element.get_text(strip=True)
        # Look for patterns like "Thursday", "Same Day", "24 hours", etc.
        if "Same Day" in time_text or "Today" in time_text:
            return "4"  # 4 hours for same day
        elif "Next Day" in time_text or "Tomorrow" in time_text:
            return "24"  # 24 hours
        elif "2-3" in time_text or "3-4" in time_text:
            return "72"  # 3 days
        elif "Week" in time_text:
            return "168"  # 1 week
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
        param_elements = parameters_container.find_all(class_=re.compile(r'popular-tests-parameters'))
        
        for param in param_elements:
            param_text = param.get_text(strip=True)
            if param_text and param_text != "...":
                parameters.append(param_text)
        
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
        
        for word in words:
            if len(word) > 2 and word not in ['THE', 'AND', 'FOR', 'WITH', 'TEST', 'BLOOD', 'SERUM', 'URINE']:
                short_code += word[0]
        
        if len(short_code) < 2:
            # Fallback: take first 3-4 letters
            short_code = test_name[:4].upper().replace(' ', '')
        
        return short_code[:5]  # Limit to 5 characters
    
    def generate_category(self, test_name):
        """Generate category based on test name"""
        test_name_lower = test_name.lower()
        
        if any(word in test_name_lower for word in ['blood', 'cbc', 'hemoglobin', 'platelet', 'wbc', 'rbc']):
            return "Hematology"
        elif any(word in test_name_lower for word in ['diabetes', 'glucose', 'sugar', 'hba1c']):
            return "Diabetes"
        elif any(word in test_name_lower for word in ['thyroid', 'tsh', 't3', 't4']):
            return "Endocrinology"
        elif any(word in test_name_lower for word in ['liver', 'alt', 'ast', 'bilirubin']):
            return "Liver Function"
        elif any(word in test_name_lower for word in ['kidney', 'creatinine', 'urea', 'bun']):
            return "Kidney Function"
        elif any(word in test_name_lower for word in ['lipid', 'cholesterol', 'triglyceride']):
            return "Lipid Profile"
        elif any(word in test_name_lower for word in ['vitamin', 'vit d', 'vitamin d', 'b12']):
            return "Vitamins"
        elif any(word in test_name_lower for word in ['hormone', 'cortisol', 'testosterone', 'estrogen']):
            return "Hormones"
        elif any(word in test_name_lower for word in ['urine', 'urinalysis']):
            return "Urine Analysis"
        elif any(word in test_name_lower for word in ['cardiac', 'troponin', 'ck-mb']):
            return "Cardiac Markers"
        else:
            return "General"
    
    def generate_description(self, test_name, parameters):
        """Generate description based on test name and parameters"""
        test_name_lower = test_name.lower()
        
        if 'cbc' in test_name_lower or 'complete blood count' in test_name_lower:
            return "Measures various components of blood including red blood cells, white blood cells, and platelets"
        elif 'diabetes' in test_name_lower or 'glucose' in test_name_lower:
            return "Measures blood glucose levels to assess diabetes control and management"
        elif 'thyroid' in test_name_lower:
            return "Evaluates thyroid function by measuring thyroid hormone levels"
        elif 'liver' in test_name_lower:
            return "Assesses liver function by measuring liver enzymes and proteins"
        elif 'kidney' in test_name_lower or 'renal' in test_name_lower:
            return "Evaluates kidney function by measuring waste products in blood"
        elif 'lipid' in test_name_lower or 'cholesterol' in test_name_lower:
            return "Measures cholesterol and triglyceride levels to assess cardiovascular risk"
        elif 'vitamin' in test_name_lower:
            return f"Measures {test_name} levels to assess nutritional status"
        elif 'hormone' in test_name_lower:
            return f"Measures {test_name} hormone levels to assess endocrine function"
        else:
            return f"Comprehensive {test_name} test to assess health parameters"
    
    def generate_preparation_instructions(self, test_name):
        """Generate preparation instructions based on test type"""
        test_name_lower = test_name.lower()
        
        if any(word in test_name_lower for word in ['glucose', 'sugar', 'diabetes', 'lipid', 'cholesterol']):
            return "Fasting required for 8-12 hours before the test"
        elif any(word in test_name_lower for word in ['thyroid', 'hormone', 'cortisol']):
            return "Fasting not required. Avoid strenuous exercise 24 hours before"
        elif any(word in test_name_lower for word in ['urine', 'urinalysis']):
            return "First morning urine sample preferred. Avoid excessive fluid intake"
        elif any(word in test_name_lower for word in ['vitamin', 'b12', 'd3']):
            return "Fasting not required. Avoid supplements 24 hours before"
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
    
    def scrape_tests_page(self, url):
        """Scrape tests from the main tests page"""
        logger.info(f"Scraping tests from: {url}")
        
        response = self.get_page(url)
        if not response:
            logger.error("Failed to fetch the tests page")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        tests = []
        
        # Find all test links
        test_links = soup.find_all('a', class_='highpertext')
        
        logger.info(f"Found {len(test_links)} test links")
        
        for i, link in enumerate(test_links):
            try:
                logger.info(f"Processing test {i+1}/{len(test_links)}")
                
                # Extract test information
                test_data = self.extract_test_data(link)
                if test_data:
                    tests.append(test_data)
                
                # Add delay to be respectful to the server
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing test {i+1}: {e}")
                continue
        
        return tests
    
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
    
    def save_to_csv(self, tests, filename='aster_labs_tests.csv'):
        """Save scraped tests to CSV file"""
        if not tests:
            logger.warning("No tests to save")
            return
        
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
            
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
    
    def run_scraper(self, tests_url="https://www.asterlabs.in/bengaluru/tests"):
        """Main method to run the scraper"""
        logger.info("Starting Aster Labs scraper...")
        
        # Scrape tests from the main page
        tests = self.scrape_tests_page(tests_url)
        
        if tests:
            # Save to CSV
            self.save_to_csv(tests)
            
            # Print summary
            logger.info(f"Scraping completed! Found {len(tests)} tests")
            logger.info("Sample tests:")
            for i, test in enumerate(tests[:3]):
                logger.info(f"  {i+1}. {test['name']} - ₹{test['price']}")
        else:
            logger.warning("No tests found")
        
        return tests

def main():
    """Main function to run the scraper"""
    scraper = AsterLabsScraper()
    tests = scraper.run_scraper()
    
    if tests:
        print(f"\n✅ Successfully scraped {len(tests)} tests from Aster Labs")
        print(f"📁 Results saved to: aster_labs_tests.csv")
        print(f"💰 Price range: ₹{min(int(t['price']) for t in tests if t['price'] != '0')} - ₹{max(int(t['price']) for t in tests if t['price'] != '0')}")
    else:
        print("❌ No tests were scraped. Please check the website structure or network connection.")

if __name__ == "__main__":
    main() 