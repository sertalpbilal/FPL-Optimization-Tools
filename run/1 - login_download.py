import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time

load_dotenv()

driver = webdriver.Chrome()
driver.set_window_size(800, 800)


def login(driver: webdriver):
    driver.get("https://fplreview.com/")

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                f'//*[@id="ast-mobile-header"]/div[1]/div/div/div[2]/div/div/button',
            )
        )
    )

    driver.add_cookie(
        {
            "name": os.getenv("NAME"),
            "value": os.getenv("KEY"),
        }
    )

    print(f'Patreon Cookie: {driver.get_cookies()[0]["value"]}')


login(driver)

# Click on Menu button
WebDriverWait(driver, 5).until(
    EC.element_to_be_clickable(
        (By.XPATH, f'//*[@id="ast-mobile-header"]/div[1]/div/div/div[2]/div/div/button')
    )
).click()

# Click on Massive Data Planner
WebDriverWait(driver, 5).until(
    EC.element_to_be_clickable((By.XPATH, f'//*[@id="ast-hf-mobile-menu"]/li[1]/a'))
).click()

# Click on download csv button
WebDriverWait(driver, 60).until(
    EC.element_to_be_clickable((By.ID, "exportbutton"))
).click()


try:
    time.sleep(1)
    alert = driver.switch_to.alert
    alert.accept()
except Exception as e:
    print(e)
    print("Cannot find alert")


time.sleep(5)
driver.quit()
