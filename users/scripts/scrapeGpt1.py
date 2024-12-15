from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

def parse_additional_details(html_content):
    """Parse HTML table to extract doctor details."""
    soup = BeautifulSoup(html_content, "html.parser")
    parsed_data = {}

    # Extract rows from the table
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) == 2:  # Rows with one key-value pair
            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            parsed_data[key] = value
        elif len(cells) == 4:  # Rows with two key-value pairs
            key1 = cells[0].get_text(strip=True)
            value1 = cells[1].get_text(strip=True)
            key2 = cells[2].get_text(strip=True)
            value2 = cells[3].get_text(strip=True)
            parsed_data[key1] = value1
            parsed_data[key2] = value2

    # Map parsed data to the desired format
    mapped_data = {
        "name": parsed_data.get("Name", ""),
        "father_name": parsed_data.get("Father/Husband Name", ""),
        "date_of_birth": parsed_data.get("Date of Birth", ""),
        "year_of_info": parsed_data.get("Year of Info", ""),
        "registration_number": parsed_data.get("Registration No", ""),
        "registration_date": parsed_data.get("Date of Reg.", ""),
        "state_council": parsed_data.get("State Medical Council", ""),
        "qualification": parsed_data.get("Qualification", ""),
        "qualification_year": parsed_data.get("Qualification Year", ""),
        "university": parsed_data.get("University Name", ""),
        "permanent_address": parsed_data.get("Permanent Address", ""),
    }

    return mapped_data


def verify_doctor(doctor_details):
    """Verify doctor details using the NMC website."""
    chrome_options = Options()
    #chrome_options.add_argument("--headless")
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
            modal_content = modal.get_attribute("innerHTML")  # Get the modal's HTML content

            # Parse the additional details
            parsed_details = parse_additional_details(modal_content)

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
