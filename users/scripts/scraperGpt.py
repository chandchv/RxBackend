from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def verify_doctor(doctor_details):
    chrome_options = Options()

    # Browser configuration
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

        # Extract data from the first result row
        print("Extracting data from results...")
        cells = rows[1].find_elements(By.TAG_NAME, "td")
        if len(cells) >= 6:  # Ensure there are enough cells
            formatted_data = {
                'year_of_registration': cells[1].text.strip(),
                'registration_number': cells[2].text.strip(),
                'state_council': cells[3].text.strip(),
                'name': cells[4].text.strip(),
                'father_name': cells[5].text.strip(),
                'qualification': 'MBBS',  # Default qualification
                'date_of_birth': '',
                'registration_date': '',
                'university': '',
                'permanent_address': ''
            }

            print("Looking for 'View' link...")
            view_link = cells[-1].find_element(By.TAG_NAME, "a")  # Locate 'View' link

            if view_link:
                print("Clicking 'View' link to fetch additional details...")
            try:
                # Click the 'View' link
                driver.execute_script("arguments[0].click();", view_link)
                time.sleep(3)  # Wait for the detailed view or modal to load

                # Ensure the detailed view is fully loaded
                wait.until(EC.presence_of_element_located((By.ID, "doctorBiodata")))  # Example element
                print("Detailed view loaded successfully.")

                # Scrape additional details
                detail_dob = driver.find_element(By.ID, "doctorBiodata").text.strip()
                detail_address = driver.find_element(By.ID, "doctorAddress").text.strip()

                formatted_data.update({
                    'date_of_birth': detail_dob,
                    'permanent_address': detail_address
                })

                print("Additional details fetched successfully:", formatted_data)
                return True, formatted_data

            except Exception as e:
                print(f"Error fetching additional details: {str(e)}")
                print("Taking screenshot for debugging...")
                driver.save_screenshot("error_screenshot.png")  # Save a screenshot of the current state
                return False, f"Failed to fetch additional details: {str(e)}"
            else:
                print("'View' link not found in the result row.")
                return False, "No 'View' link available to fetch additional details"

        return False, "Could not extract required information from results"

    except Exception as e:
        print(f"Error during verification process: {str(e)}")
        return False, f"Verification process failed: {str(e)}"

    finally:
        if driver:
            time.sleep(5)
            try:
                driver.quit()
            except Exception as e:
                print(f"Error closing browser: {str(e)}")
def format_doctor_details(data):
    """
    Formats the scraped doctor details into a structured format.
    """
    # Parse the 'date_of_birth' field which contains jumbled text
    details_lines = data['date_of_birth'].split("\n")
    parsed_details = {}
    
    # Extract key details line by line
    for line in details_lines:
        parts = line.split(":")
        if len(parts) == 2:  # Handle lines that have a key-value pair
            key, value = parts[0].strip(), parts[1].strip()
            parsed_details[key] = value

    # Update structured fields with parsed details
    return {
        "Name": data.get('name', ''),
        "Father/Husband Name": data.get('father_name', ''),
        "Date of Birth": parsed_details.get('Date of Birth', ''),
        "Year of Registration": data.get('year_of_registration', ''),
        "Registration Number": data.get('registration_number', ''),
        "Date of Registration": parsed_details.get('Date of Reg.', ''),
        "State Medical Council": data.get('state_council', ''),
        "Qualification": data.get('qualification', ''),
        "Qualification Year": parsed_details.get('Qualification Year', ''),
        "University": parsed_details.get('University Name', ''),
        "Permanent Address": parsed_details.get('Permanent Address', '')
    }

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
            
            # Format the results for better readability
            formatted_result = format_doctor_details(result)
            for key, value in formatted_result.items():
                print(f"{key}: {value}")
        else:
            print("Verification failed:", result)

