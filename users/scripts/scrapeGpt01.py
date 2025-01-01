from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import re

def parse_additional_details(details_string):
    # Define a dictionary to hold the parsed data
    parsed_data = {}

    # Use regular expressions to extract the relevant fields
    name_match = re.search(r'Name\s*([^\n]+)', details_string)
    father_name_match = re.search(r'Father/Husband Name\s*([^\n]+)', details_string)
    dob_match = re.search(r'Date of Birth\s*([^\n]+)', details_string)
    registration_no_match = re.search(r'Registration No\s*([^\n]+)', details_string)
    registration_date_match = re.search(r'Date of Reg\.\s*([^\n]+)', details_string)
    state_council_match = re.search(r'State Medical Council\s*([^\n]+)', details_string)
    qualification_match = re.search(r'Qualification\s*([^\n]+)', details_string)
    qualification_year_match = re.search(r'Qualification Year\s*([^\n]+)', details_string)
    university_name_match = re.search(r'University Name\s*([^\n]+)', details_string)
    permanent_address_match = re.search(r'Permanent Address\s*([^\n]+)', details_string)

    # Populate the parsed_data dictionary with the extracted values
    if name_match:
        parsed_data['name'] = name_match.group(1).strip()
    if father_name_match:
        parsed_data['father_name'] = father_name_match.group(1).strip()
    if dob_match:
        parsed_data['date_of_birth'] = dob_match.group(1).strip()
    if registration_no_match:
        parsed_data['registration_number'] = registration_no_match.group(1).strip()
    if registration_date_match:
        parsed_data['registration_date'] = registration_date_match.group(1).strip()
    if state_council_match:
        parsed_data['state_council'] = state_council_match.group(1).strip()
    if qualification_match:
        parsed_data['qualification'] = qualification_match.group(1).strip()
    if qualification_year_match:
        parsed_data['qualification_year'] = qualification_year_match.group(1).strip()
    if university_name_match:
        parsed_data['university'] = university_name_match.group(1).strip()
    if permanent_address_match:
        parsed_data['permanent_address'] = permanent_address_match.group(1).strip()

    return parsed_data

def verify_doctor(doctor_details):
    chrome_options = Options()
    
    # Browser configuration
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
        time.sleep(3)

        print("Filling in doctor details...")
        name_input = wait.until(EC.presence_of_element_located((By.ID, "doctorName")))
        name_input.clear()
        time.sleep(1)
        name_input.send_keys(doctor_details['name'])
        time.sleep(1)

        reg_input = wait.until(EC.presence_of_element_located((By.ID, "doctorRegdNo")))
        reg_input.clear()
        time.sleep(1)
        reg_input.send_keys(doctor_details['registration_number'])
        time.sleep(1)

        council_dropdown = wait.until(EC.presence_of_element_located((By.ID, "advsmcId")))
        driver.execute_script("arguments[0].style.display = 'block';", council_dropdown)
        time.sleep(1)
        
        council_found = False
        for option in council_dropdown.find_elements(By.TAG_NAME, "option"):
            if doctor_details['state_council'] in option.text:
                driver.execute_script("arguments[0].selected = true; arguments[0].dispatchEvent(new Event('change'))", option)
                council_found = True
                break

        if not council_found:
            return False, "Medical council not found in dropdown"

        time.sleep(2)
        print("Submitting form...")
        submit_button = wait.until(EC.element_to_be_clickable((By.ID, "doctor_advance_Details")))
        driver.execute_script("arguments[0].click();", submit_button)
        
        time.sleep(3)

        print("Waiting for results table...")
        results_table = wait.until(EC.presence_of_element_located((By.ID, "doct_info5")))
        
        if not results_table.is_displayed():
            return False, "No results found"

        rows = results_table.find_elements(By.TAG_NAME, "tr")
        if len(rows) <= 1:  # Only header row
            return False, "No results found"

        # Click the first result row to show details
        cells = rows[1].find_elements(By.TAG_NAME, "td")
        print("Looking for 'View' link...")
        view_link = cells[-1].find_element(By.TAG_NAME, "a")  # Locate 'View' link

        if view_link:
            print("Clicking 'View' link to fetch additional details...")
            driver.execute_script("arguments[0].click();", view_link)
            time.sleep(3)  # Wait for the detailed view or modal to load

            # Wait for the modal to be present in the DOM
            modal = wait.until(EC.presence_of_element_located((By.ID, "doctorModalBody")))
            biodata_text = modal.find_element(By.ID, "doctorBiodata").text.strip()  # Get the text directly

            # Parse the additional details
            parsed_details = parse_additional_details(biodata_text)

            # Return the parsed data
            return True, parsed_details

        else:
            print("'View' link not found in the result row.")
            return False, "No 'View' link available to fetch additional details"

    except Exception as e:
        print(f"Error during verification process: {str(e)}")
        return False, f"Verification process failed: {str(e)}"

    finally:
        if driver:
            time.sleep(5)  # Give time to see the results
            try:
                driver.quit()
            except Exception as e:
                print(f"Error closing browser: {str(e)}")

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

