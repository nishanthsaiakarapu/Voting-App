from selenium import webdriver

driver = webdriver.Chrome()

try:
    driver.get("https://www.google.com")
    print("Page title:", driver.title)

    assert "Google" in driver.title
    print("TEST PASSED")

finally:
    driver.quit()