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

def parse_additional_details(html_content):
    """Parse HTML table to extract doctor details."""
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_data = {}

    try:
        table = soup.find('table', id='doctorBiodata')
        if not table:
            print("Table not found")
            return {}

        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                
                # Special handling for rows with 4 cells
                if len(cells) == 4:
                    # First pair
                    key1 = cells[0].get_text(strip=True)
                    value1 = cells[1].get_text(strip=True)
                    # Second pair
                    key2 = cells[2].get_text(strip=True)
                    value2 = cells[3].get_text(strip=True)
                    
                    # Process first pair
                    if key1 == 'Registration No':
                        parsed_data['registration_number'] = value1
                    elif key1 == 'Date of Birth':
                        parsed_data['date_of_birth'] = value1
                    elif key1 == 'Qualification':
                        parsed_data['qualification'] = value1
                        
                    # Process second pair
                    if key2 == 'Date of Reg.':
                        parsed_data['registration_date'] = value2
                    elif key2 == 'State Medical Council':
                        parsed_data['medical_council'] = value2
                    elif key2 == 'Qualification Year':
                        parsed_data['qualification_year'] = value2
                else:
                    # Handle rows with colspan
                    value = cells[1].get_text(strip=True)
                    if key == 'Name':
                        parsed_data['full_name'] = value
                    elif key == 'Father/Husband Name':
                        parsed_data['father_name'] = value
                    elif key == 'University Name':
                        parsed_data['university'] = value
                    elif key == 'Permanent Address':
                        parsed_data['permanent_address'] = value

        # Clean the data
        for key in parsed_data:
            if parsed_data[key] == 'N/A':
                parsed_data[key] = ''
            else:
                parsed_data[key] = parsed_data[key].strip()

        # Add verification timestamp
        parsed_data['verification_timestamp'] = datetime.now().isoformat()
        
        print("Raw Parsed Data:", parsed_data)
        return parsed_data

    except Exception as e:
        print(f"Error parsing details: {str(e)}")
        print("HTML Content:", html_content)
        return {}


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
        time.sleep(15)  # Increased wait time

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

            print("Clicking view button...")
            view_link = cells[-1].find_element(By.TAG_NAME, "a")
            driver.execute_script("arguments[0].click();", view_link)
            time.sleep(5)  # Increased wait time

            print("Waiting for modal...")
            modal = wait.until(EC.presence_of_element_located((By.ID, "doctorModalBody")))
            time.sleep(3)  # Wait for modal content

            print("Getting modal content...")
            modal_html = modal.get_attribute('innerHTML')
            if not modal_html:
                print("Error: Empty modal content")
                driver.save_screenshot("empty_modal.png")
                return False, "Modal content empty"

            print("Parsing doctor details...")
            detailed_info = parse_additional_details(modal_html)
            
            if not detailed_info:
                print("Error: Failed to parse details")
                driver.save_screenshot("parse_error.png")
                return False, "Failed to parse doctor details"

            print("Successfully extracted details:", detailed_info)

            # After getting detailed_info, format the response
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

            # Debug prints
            print("Raw Details:", detailed_info)
            print("Formatted Response:", verification_response)
            
            # Validate required fields
            if not verification_response['registration'] or not verification_response['qualification']:
                print("Warning: Missing required fields in response")
            
            return True, verification_response

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
