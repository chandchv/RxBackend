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
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    try:
        print("Initializing browser...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 20)

        print("Navigating to website...")
        driver.get("https://www.nmc.org.in/information-desk/indian-medical-register")
        time.sleep(5)

        # Switch to the advance search tab if needed
        try:
            advance_search = wait.until(EC.element_to_be_clickable((By.ID, "advanceSearch")))
            if not "active" in advance_search.get_attribute("class"):
                advance_search.click()
        except:
            print("Already on advance search tab or tab not found")

        print("Filling doctor details...")
        # Fill doctor name
        name_input = wait.until(EC.presence_of_element_located((By.ID, "doctorName")))
        name_input.clear()
        name_input.send_keys(doctor_details['name'])

        # Fill registration number
        reg_input = wait.until(EC.presence_of_element_located((By.ID, "doctorRegdNo")))
        reg_input.clear()
        reg_input.send_keys(doctor_details['registration_number'])

        # Select state medical council if provided
        if doctor_details.get('state_council'):
            try:
                council_dropdown = wait.until(EC.presence_of_element_located((By.ID, "advsmcId")))
                driver.execute_script("arguments[0].style.display = 'block';", council_dropdown)
                for option in council_dropdown.find_elements(By.TAG_NAME, "option"):
                    if doctor_details['state_council'] in option.text:
                        option.click()
                        break
            except Exception as e:
                print(f"Error selecting medical council: {str(e)}")

        print("Submitting search...")
        # Click the submit button
        submit_button = wait.until(EC.element_to_be_clickable((By.ID, "doctor_advance_Details")))
        driver.execute_script("arguments[0].click();", submit_button)

        print("Waiting for results...")
        time.sleep(5)

        # Look for results
        try:
            # Wait for the total records element to confirm results are loaded
            total_records = wait.until(EC.presence_of_element_located((By.ID, "totalRecords5")))
            print(f"\n{total_records.text}")

            # Wait for and get the results table
            results_table = wait.until(EC.presence_of_element_located((By.ID, "doct_info5")))
            rows = results_table.find_elements(By.TAG_NAME, "tr")
            
            if len(rows) > 1:  # If we have results (excluding header row)
                print("\nFound matching records:")
                for row in rows[1:]:  # Skip header row
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if cols:
                        print("\nDoctor Details:")
                        print(f"Year: {cols[1].text if len(cols) > 1 else 'N/A'}")
                        print(f"Registration No: {cols[2].text if len(cols) > 2 else 'N/A'}")
                        print(f"State Medical Council: {cols[3].text if len(cols) > 3 else 'N/A'}")
                        print(f"Name: {cols[4].text if len(cols) > 4 else 'N/A'}")
                        print(f"Father Name: {cols[5].text if len(cols) > 5 else 'N/A'}")
                        
                        # Optionally, get detailed view
                        try:
                            view_link = cols[6].find_element(By.TAG_NAME, "a")
                            print("Detailed View Available: Yes")
                        except:
                            print("Detailed View Available: No")
                return True
            else:
                print("No matching records found.")
                return False

        except Exception as e:
            print(f"Error finding results: {str(e)}")
            # Take screenshot on error
            try:
                driver.save_screenshot("error_screenshot.png")
                print("Screenshot saved as error_screenshot.png")
            except:
                pass
            return False

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        if driver:
            try:
                driver.save_screenshot("error_screenshot.png")
                print("Screenshot saved as error_screenshot.png")
            except:
                pass
        return False

    finally:
        if driver:
            driver.quit()
            print("Browser closed.")

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
        verify_doctor(doctor)