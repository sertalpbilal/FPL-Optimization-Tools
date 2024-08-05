from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep
import winsound  # For making a sound on Windows

# Configure Chrome options
options = Options()
options.add_experimental_option(
    "excludeSwitches", ["enable-automation"]
)  # Remove the 'being controlled by software' message

# Initialize the Chrome driver
driver = webdriver.Chrome(options=options)

# URL to monitor
url = "https://fantasy.premierleague.com/"
driver.get(url)

# Xpath of the element to monitor
xpath = "/html/body/article/h1"

# Main loop
while True:
    try:
        # Wait for the element to be visible
        WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.XPATH, xpath))
        )
    except:
        # Sound an alarm if the element is not found
        for i in range(3):
            winsound.Beep(1000, 5000)  # 1000 Hz frequency, 5s duration
        break  # Exit the loop when the element is not found

    sleep(1)  # Wait for 1 seconds before refreshing
    driver.refresh()  # Refresh the webpage

# Close the driver
driver.quit()
