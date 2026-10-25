import os
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5500/app.html"

VOTER_ID = os.getenv("VOTER_ID", "101")
VOTER_PASSWORD = os.getenv("VOTER_PASSWORD", "pass101")
ADMIN_ID = os.getenv("ADMIN_ID", "999")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin999")


class VotingAppSeleniumTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = webdriver.Chrome()
        cls.wait = WebDriverWait(cls.driver, 20)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def setUp(self):
        self.driver.get(BASE_URL)
        self.wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR,
                 "#landing button[onclick=\"showScreen('voterLogin')\"]")
            )
        )

    # TC01: Voter login with valid credentials
    def test_01_voter_login_valid_credentials(self):
        self.driver.find_element(
            By.CSS_SELECTOR,
            "#landing button[onclick=\"showScreen('voterLogin')\"]"
        ).click()

        self.wait.until(
            EC.visibility_of_element_located((By.ID, "voterIdInput"))
        )

        self.driver.find_element(By.ID, "voterIdInput").send_keys(VOTER_ID)
        self.driver.find_element(By.ID, "voterPwInput").send_keys(VOTER_PASSWORD)

        self.driver.find_element(
            By.CSS_SELECTOR, "#voterLogin button[type='submit']"
        ).click()

        self.wait.until(
            lambda d: "active" in
            d.find_element(By.ID, "voterStatus").get_attribute("class")
        )

        self.assertIn(
            "VOTER " + VOTER_ID,
            self.driver.find_element(By.ID, "statusVoterLabel").text
        )

    # TC02: Voter login with invalid credentials
    def test_02_voter_login_invalid_credentials(self):
        self.driver.find_element(
            By.CSS_SELECTOR,
            "#landing button[onclick=\"showScreen('voterLogin')\"]"
        ).click()

        self.driver.find_element(By.ID, "voterIdInput").send_keys("99999999")
        self.driver.find_element(By.ID, "voterPwInput").send_keys("wrongpassword")

        self.driver.find_element(
            By.CSS_SELECTOR, "#voterLogin button[type='submit']"
        ).click()

        error = self.wait.until(
            EC.visibility_of_element_located((By.ID, "voterError"))
        )

        self.assertTrue(error.text.strip())

    # TC03: Admin login with valid credentials
    def test_03_admin_login_valid_credentials(self):
        self.driver.find_element(
            By.CSS_SELECTOR,
            "#landing button[onclick=\"showScreen('adminLogin')\"]"
        ).click()

        self.wait.until(
            EC.visibility_of_element_located((By.ID, "adminIdInput"))
        )

        self.driver.find_element(By.ID, "adminIdInput").send_keys(ADMIN_ID)
        self.driver.find_element(By.ID, "adminPwInput").send_keys(ADMIN_PASSWORD)

        self.driver.find_element(
            By.CSS_SELECTOR, "#adminLogin button[type='submit']"
        ).click()

        self.wait.until(
            lambda d: "active" in
            d.find_element(By.ID, "admin").get_attribute("class")
        )

        self.wait.until(
            lambda d: d.find_element(By.ID, "statConstituency").text
            not in ("", "—")
        )

        self.assertTrue(
            self.driver.find_element(By.ID, "areaTable").is_displayed()
        )

    # TC04: Check whether Election Assistant responds
    def test_04_election_assistant_responds(self):
        self.driver.find_element(
            By.CSS_SELECTOR,
            "#landing button[onclick=\"showScreen('voterLogin')\"]"
        ).click()

        self.driver.find_element(By.ID, "voterIdInput").send_keys(VOTER_ID)
        self.driver.find_element(By.ID, "voterPwInput").send_keys(VOTER_PASSWORD)

        self.driver.find_element(
            By.CSS_SELECTOR, "#voterLogin button[type='submit']"
        ).click()

        self.wait.until(
            lambda d: "active" in
            d.find_element(By.ID, "voterStatus").get_attribute("class")
        )

        self.wait.until(
            EC.element_to_be_clickable((By.ID, "botFab"))
        ).click()

        self.wait.until(
            lambda d: "open" in
            d.find_element(By.ID, "botOverlay").get_attribute("class")
        )

        previous_count = len(
            self.driver.find_elements(
                By.CSS_SELECTOR, "#botMessages .bot-msg.assistant"
            )
        )

        self.driver.find_element(By.ID, "botInput").send_keys(
            "What is my voter ID?"
        )
        self.driver.find_element(By.ID, "botSend").click()

        self.wait.until(
            lambda d: len(d.find_elements(
                By.CSS_SELECTOR, "#botMessages .bot-msg.assistant"
            )) > previous_count
        )

        replies = self.driver.find_elements(
            By.CSS_SELECTOR, "#botMessages .bot-msg.assistant"
        )
        answer = replies[-1].text.strip()

        self.assertTrue(answer)
        self.assertNotIn(
            "Could not connect to the Election Assistant", answer
        )
        self.assertNotIn("Could not get a response.", answer)

    # TC05: Check Areas Requiring Attention
    def test_05_areas_requiring_attention(self):
        self.driver.find_element(
            By.CSS_SELECTOR,
            "#landing button[onclick=\"showScreen('adminLogin')\"]"
        ).click()

        self.driver.find_element(By.ID, "adminIdInput").send_keys(ADMIN_ID)
        self.driver.find_element(By.ID, "adminPwInput").send_keys(ADMIN_PASSWORD)

        self.driver.find_element(
            By.CSS_SELECTOR, "#adminLogin button[type='submit']"
        ).click()

        self.wait.until(
            lambda d: "active" in
            d.find_element(By.ID, "admin").get_attribute("class")
        )

        heading = self.wait.until(
            EC.visibility_of_element_located((
                By.XPATH,
                "//*[@id='admin']//*[contains(text(), 'Areas Requiring Attention')]"
            ))
        )

        self.assertTrue(heading.is_displayed())

        self.wait.until(
            lambda d: len(
                d.find_elements(By.CSS_SELECTOR, "#areaTable tbody tr")
            ) > 0
        )

        rows = self.driver.find_elements(
            By.CSS_SELECTOR, "#areaTable tbody tr"
        )

        self.assertGreater(len(rows), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)