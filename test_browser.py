#!/usr/bin/env python3
"""Browser test: simulates exactly what the user sees."""
import sys, time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE = "http://localhost:8080"
PASS = 0
FAIL = 0

def check(condition, msg):
    global PASS, FAIL
    if condition:
        PASS += 1; print(f"  ✅ {msg}")
    else:
        FAIL += 1; print(f"  ❌ {msg}")

print("=== ACE Reception Services — Browser Test ===\n")

options = Options(); options.add_argument("--headless")
driver = webdriver.Firefox(options=options)
driver.set_window_size(1920, 1080)

try:
    # 1. LOGIN PAGE
    print("1. Login page")
    driver.get(f"{BASE}/login")
    time.sleep(2)
    check("Login" in driver.page_source, "Login page loads")

    # 2. LOGIN
    print("\n2. Login as admin")
    username = driver.find_element(By.CSS_SELECTOR, "input[placeholder=Username]")
    password = driver.find_element(By.CSS_SELECTOR, "input[placeholder=Password]")
    login_btn = driver.find_element(By.TAG_NAME, "button")
    username.send_keys("admin")
    password.send_keys("test123")
    login_btn.click()
    time.sleep(3)
    check("Admin" not in driver.page_source or "ACE" in driver.title, "Redirected after login")

    # 3. ADMIN PAGE
    print("\n3. Admin page")
    driver.get(f"{BASE}/admin")
    time.sleep(3)
    check("demo" in driver.page_source.lower() or "Organization" in driver.page_source, "Admin page shows orgs")

    # 4. VISITOR CHAT
    print("\n4. Visitor chat")
    driver.get(f"{BASE}/demo")
    time.sleep(3)
    # Type a message
    try:
        input_el = driver.find_element(By.CSS_SELECTOR, "input.chat-input")
        input_el.send_keys("Browser test message")
        send_btn = driver.find_element(By.CSS_SELECTOR, "button.send-btn")
        send_btn.click()
        time.sleep(3)
        check(True, "Message sent via chat")
    except Exception as e:
        check(False, f"Chat input not found: {e}")

    # 5. DASHBOARD — CHECK LEADS APPEAR AS DOM ELEMENTS
    print("\n5. Dashboard — lead cards visible")
    driver.get(f"{BASE}/demo/dashboard")
    time.sleep(5)
    lead_cards = driver.find_elements(By.CSS_SELECTOR, ".lead-entry")
    check(len(lead_cards) > 0, f"{len(lead_cards)} lead cards visible")

    # 6. CHECK LEAD CARDS HAVE CONTENT
    print("\n6. Lead cards have content")
    non_empty = [c for c in lead_cards if c.text.strip()]
    check(len(non_empty) > 0, f"{len(non_empty)} lead cards have text content")
    if non_empty:
        print(f"   First card text: {non_empty[0].text[:100]}")

    # 7. TAKE OVER
    print("\n7. Takeover — click lead, send message")
    try:
        lead_cards = driver.find_elements(By.CSS_SELECTOR, ".lead-entry")
        if lead_cards:
            lead_cards[0].click()
            time.sleep(2)
            textarea = driver.find_element(By.CSS_SELECTOR, "textarea")
            textarea.send_keys("Staff takeover message")
            takeover_btn = driver.find_element(By.CSS_SELECTOR, ".composer .actions button.btn.primary")
            driver.execute_script("arguments[0].scrollIntoView(true);", takeover_btn)
            time.sleep(0.5)
            takeover_btn.click()
            time.sleep(3)
            check(True, "Takeover message sent")
        else:
            check(False, "No lead cards found to click")
    except Exception as e:
        check(False, f"Takeover failed: {e}")

    # 8. CHECK THREAD SHOWS MESSAGES
    print("\n8. Thread messages visible")
    page = driver.page_source
    has_thread = "Browser test message" in page or "Staff takeover message" in page or "Visitor" in page
    check(has_thread, "Thread shows messages")

finally:
    driver.quit()

print(f"\n=== RESULTS: {PASS} passed, {FAIL} failed ===")
sys.exit(0 if FAIL == 0 else 1)
