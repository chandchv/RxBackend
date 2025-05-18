from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from datetime import datetime
from selenium.webdriver.common.action_chains import ActionChains

def parse_additional_details(html_content):
    """Parse HTML table to extract doctor details."""
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_data = {}

    try:
        # First try to find the table
        table = soup.find('table', id='doctorBiodata')
        if not table:
            print("Table not found, trying alternative selectors...")
            # Try alternative table selectors
            table = soup.find('table', class_='table')
            if not table:
                print("No table found with alternative selectors")
                return {}

        print("Found table, extracting rows...")
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all(['td', 'th'])  # Include both td and th elements
            if len(cells) >= 2:
                # Handle both regular and colspan rows
                if len(cells) == 4:  # Two pairs of key-value
                    key1 = cells[0].get_text(strip=True).replace(':', '')
                    value1 = cells[1].get_text(strip=True)
                    key2 = cells[2].get_text(strip=True).replace(':', '')
                    value2 = cells[3].get_text(strip=True)
                    
                    # Map keys to our data structure
                    key_mapping = {
                        'Registration No': 'registration_number',
                        'Date of Birth': 'date_of_birth',
                        'Qualification': 'qualification',
                        'Date of Reg.': 'registration_date',
                        'State Medical Council': 'medical_council',
                        'Qualification Year': 'qualification_year'
                    }
                    
                    # Process first pair
                    if key1 in key_mapping:
                        parsed_data[key_mapping[key1]] = value1
                    
                    # Process second pair
                    if key2 in key_mapping:
                        parsed_data[key_mapping[key2]] = value2
                else:
                    # Handle single key-value pair
                    key = cells[0].get_text(strip=True).replace(':', '')
                    value = cells[1].get_text(strip=True)
                    
                    # Map keys to our data structure
                    key_mapping = {
                        'Name': 'full_name',
                        'Father/Husband Name': 'father_name',
                        'University Name': 'university',
                        'Permanent Address': 'permanent_address'
                    }
                    
                    if key in key_mapping:
                        parsed_data[key_mapping[key]] = value

        # Clean the data
        for key in parsed_data:
            if parsed_data[key] == 'N/A' or parsed_data[key] == '-':
                parsed_data[key] = ''
            else:
                parsed_data[key] = parsed_data[key].strip()

        # Add verification timestamp
        parsed_data['verification_timestamp'] = datetime.now().isoformat()
        
        print("Raw Parsed Data:", parsed_data)
        
        # Validate required fields
        required_fields = ['full_name', 'registration_number', 'qualification']
        missing_fields = [field for field in required_fields if not parsed_data.get(field)]
        if missing_fields:
            print(f"Warning: Missing required fields: {missing_fields}")
        
        return parsed_data

    except Exception as e:
        print(f"Error parsing details: {str(e)}")
        print("HTML Content:", html_content)
        return {}

def extract_from_table_row(cells, doctor_details):
    """Extract doctor details from the result table row as fallback."""
    try:
        # Based on the visible structure: ['1', '2015', '89604', 'Andhra Pradesh Medical Council', 'BUDDE SRINIVAS', 'BUDDE VEERASWAMY', 'View']
        year = cells[1].text.strip()
        registration_number = cells[2].text.strip()
        council = cells[3].text.strip()
        full_name = cells[4].text.strip()
        father_name = cells[5].text.strip() if len(cells) > 5 else ''

        verification_response = {
            'name': full_name,
            'registration': registration_number,
            'council': council,
            'qualification': '',  # Not available in list
            'registration_date': '',  # Not available in list
            'father_name': father_name,
            'date_of_birth': '',  # Not available in list
            'university': '',  # Not available in list
            'permanent_address': '',  # Not available in list
            'qualification_year': year,
            'verification_status': 'VERIFIED',
            'verification_timestamp': datetime.now().isoformat()
        }

        print("Successfully extracted details from results table (fallback method)")
        print("Verification Response:", verification_response)
        
        # Validate that we found the correct doctor
        if (registration_number.lower() == doctor_details['registration_number'].lower() and 
            council.lower() == doctor_details['state_council'].lower() and
            full_name.lower() == doctor_details['name'].lower()):
            return True, verification_response
        else:
            print("Warning: Verification data doesn't match input data")
            return False, "Verification data doesn't match input data"

    except Exception as e:
        print(f"Error extracting data from result row: {str(e)}")
        return False, f"Error extracting data from result row: {str(e)}"

def verify_doctor(doctor_details):
    """Verify doctor details using the NMC website."""
    print(f"\n=== Starting Verification ===")
    print(f"Doctor details: {doctor_details}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        print("Initializing Chrome WebDriver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 20)

        print("Navigating to website...")
        driver.get("https://www.nmc.org.in/information-desk/indian-medical-register")
        time.sleep(5)  # Increased wait time

        print("Filling form fields...")
        # Fill in doctor details
        name_input = wait.until(EC.presence_of_element_located((By.ID, "doctorName")))
        name_input.clear()
        name_input.send_keys(doctor_details['name'])
        print(f"Entered name: {doctor_details['name']}")

        reg_input = wait.until(EC.presence_of_element_located((By.ID, "doctorRegdNo")))
        reg_input.clear()
        reg_input.send_keys(doctor_details['registration_number'])
        print(f"Entered registration: {doctor_details['registration_number']}")

        council_dropdown = wait.until(EC.presence_of_element_located((By.ID, "advsmcId")))
        driver.execute_script("arguments[0].style.display = 'block';", council_dropdown)
        time.sleep(3)

        print("Selecting medical council...")
        council_found = False
        for option in council_dropdown.find_elements(By.TAG_NAME, "option"):
            if doctor_details['state_council'].lower() in option.text.lower():
                driver.execute_script("arguments[0].selected = true; arguments[0].dispatchEvent(new Event('change'))", option)
                council_found = True
                print(f"Selected council: {option.text}")
                break

        if not council_found:
            print("Error: Medical council not found")
            return False, "Medical council not found in dropdown"

        print("Submitting form...")
        submit_button = wait.until(EC.element_to_be_clickable((By.ID, "doctor_advance_Details")))
        driver.execute_script("arguments[0].click();", submit_button)

        print("Waiting for results...")
        time.sleep(5)  # Increased wait time

        try:
            # Wait for results table
            results_table = wait.until(
                EC.presence_of_element_located((By.ID, "doct_info5"))
            )
            
            print("Checking results table...")
            if not results_table.is_displayed():
                print("Error: Results table not visible")
                driver.save_screenshot("table_not_visible.png")
                return False, "Results table not visible"

            rows = results_table.find_elements(By.TAG_NAME, "tr")
            if len(rows) <= 1:
                print("Error: No results found")
                driver.save_screenshot("no_results.png")
                return False, "No results found"

            print(f"Found {len(rows)-1} results")
            
            # Get first result row
            result_row = rows[1]
            cells = result_row.find_elements(By.TAG_NAME, "td")
            print(f"Result row cells: {[cell.text for cell in cells]}")

            # Try to get detailed info from modal first
            modal_success = False
            try:
                print("Attempting to get detailed info from modal...")
                view_button = cells[-1].find_element(By.TAG_NAME, "a")
                driver.execute_script("arguments[0].click();", view_button)
                
                # Wait for modal and its content
                modal = wait.until(EC.presence_of_element_located((By.ID, "doctorModalBody")))
                time.sleep(3)
                
                # Wait for table data
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_element(By.ID, "doctorBiodata").find_elements(By.TAG_NAME, "tr")) > 0
                )
                
                modal_html = modal.get_attribute('innerHTML')
                if modal_html and "<td" in modal_html:
                    detailed_info = parse_additional_details(modal_html)
                    if detailed_info and any(detailed_info.values()):
                        print("Successfully got data from modal")
                        verification_response = {
                            'name': detailed_info.get('full_name', ''),
                            'registration': detailed_info.get('registration_number', ''),
                            'council': detailed_info.get('medical_council', doctor_details.get('state_council', '')),
                            'qualification': detailed_info.get('qualification', ''),
                            'registration_date': detailed_info.get('registration_date', ''),
                            'father_name': detailed_info.get('father_name', ''),
                            'date_of_birth': detailed_info.get('date_of_birth', ''),
                            'university': detailed_info.get('university', ''),
                            'permanent_address': detailed_info.get('permanent_address', ''),
                            'qualification_year': detailed_info.get('qualification_year', ''),
                            'verification_status': 'VERIFIED',
                            'verification_timestamp': detailed_info.get('verification_timestamp', datetime.now().isoformat())
                        }
                        modal_success = True
                        return True, verification_response
            except Exception as e:
                print(f"Modal data extraction failed: {str(e)}")
                print("Falling back to table row data...")
            
            if not modal_success:
                print("Using fallback method: extracting from table row")
                return extract_from_table_row(cells, doctor_details)

        except Exception as e:
            print(f"Error processing results: {str(e)}")
            driver.save_screenshot("error_screenshot.png")
            return False, f"Error processing results: {str(e)}"

    except Exception as e:
        print(f"Verification process failed: {str(e)}")
        if driver:
            driver.save_screenshot("error_screenshot.png")
        return False, f"Verification process failed: {str(e)}"

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    test_doctors = [
        {
            "name": "CHANDRASEKHAR.J",
            "registration_number": "51806",
            "state_council": "Andhra Pradesh Medical Council"
        }
    ]
    
    for doctor in test_doctors:
        print(f"\nVerifying doctor: {doctor['name']}")
        success, result = verify_doctor(doctor)
        if success:
            print("Verification successful!")
            print("Verified details:", result)
        else:
            print("Verification failed:", result)
