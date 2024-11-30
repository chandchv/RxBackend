from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import platform

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

        try:
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
            
            if len(cells) >= 6:  # Make sure we have enough cells
                formatted_data = {
                    'year_of_registration': cells[1].text.strip(),  # Year column
                    'registration_number': cells[2].text.strip(),   # Registration number
                    'state_council': cells[3].text.strip(),        # Medical Council
                    'name': cells[4].text.strip(),                 # Doctor's name
                    'father_name': cells[5].text.strip(),          # Father's name
                    'qualification': '',                        # Default qualification
                    'date_of_birth': '',                           # Not available in table
                    'registration_date': '',                       # Not available in table
                    'university': '',                              # Not available in table
                    'permanent_address': ''                        # Not available in table
                }

                # Verify the data matches what was searched
                if (formatted_data['registration_number'] == doctor_details['registration_number'] and
                    formatted_data['state_council'] == doctor_details['state_council']):
                    print("Successfully extracted verification data:", formatted_data)
                    return True, formatted_data
                else:
                    return False, "Verification failed: Details do not match"

            return False, "Could not extract required information from results"

        except Exception as e:
            print(f"Error during verification process: {str(e)}")
            return False, f"Verification process failed: {str(e)}"

    except Exception as e:
        print(f"Error initializing Chrome: {str(e)}")
        return False, f"Failed to initialize verification: {str(e)}"

    finally:
        if driver:
            time.sleep(5)
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