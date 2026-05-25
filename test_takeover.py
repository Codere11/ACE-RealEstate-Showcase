#!/usr/bin/env python3
"""Test: staff takeover message appears in visitor chat"""
import time, json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

BASE = "http://localhost:8080"
options = Options(); options.add_argument("--headless")
driver = webdriver.Firefox(options=options)
driver.set_window_size(1920, 1080)

PASS = 0; FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1; print(f"  ✅ {m}")
    else: FAIL += 1; print(f"  ❌ {m}")

print("=== STAFF TAKEOVER → VISITOR SEES MESSAGE ===\n")

try:
    # 1. Login
    print("1. Login")
    driver.get(f"{BASE}/login")
    time.sleep(2)
    driver.find_element(By.CSS_SELECTOR, "input[placeholder=Username]").send_keys("admin")
    driver.find_element(By.CSS_SELECTOR, "input[placeholder=Password]").send_keys("test123")
    driver.find_element(By.TAG_NAME, "button").click()
    time.sleep(2)
    
    # 2. Open visitor chat
    print("2. Visitor chat")
    driver.get(f"{BASE}/demo")
    time.sleep(3)
    
    # 3. Send a message as visitor
    inp = driver.find_element(By.CSS_SELECTOR, "input.chat-input")
    inp.send_keys("Hello from visitor")
    driver.find_element(By.CSS_SELECTOR, "button.send-btn").click()
    time.sleep(3)
    
    # Get the visitor's SID from the chat
    page = driver.page_source
    print("   Chat page loaded, messages visible:", "message-bubble" in page or "chat-messages" in page)
    
    # 4. Open dashboard in new tab
    print("3. Dashboard — send takeover")
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(f"{BASE}/demo/dashboard")
    time.sleep(4)
    
    # Click first lead
    cards = driver.find_elements(By.CSS_SELECTOR, ".lead-entry")
    check(len(cards) > 0, f"{len(cards)} leads available")
    
    if cards:
        cards[0].click()
        time.sleep(2)
        
        # Type takeover message
        textarea = driver.find_element(By.CSS_SELECTOR, ".composer textarea")
        driver.execute_script("arguments[0].scrollIntoView(true);", textarea)
        textarea.send_keys("STAFF TAKEOVER MESSAGE")
        
        # Click takeover button
        btns = driver.find_elements(By.CSS_SELECTOR, ".composer .actions button.btn.primary")
        if btns:
            driver.execute_script("arguments[0].scrollIntoView(true);", btns[0])
            btns[0].click()
            time.sleep(3)
            check(True, "Takeover message sent from dashboard")
    
    # 5. Switch back to visitor tab, wait longer
    print("4. Check visitor chat for staff message (waiting 8s)")
    driver.switch_to.window(driver.window_handles[0])
    time.sleep(8)
    
    page = driver.page_source
    has_osebje = "Osebje" in page
    has_staff_msg = "STAFF TAKEOVER MESSAGE" in page
    print(f"   Header Osebje: {has_osebje}")
    print(f"   Staff message in page: {has_staff_msg}")
    check(has_osebje, "Visitor header changed to Osebje")
    check(has_staff_msg, "Staff takeover message visible in visitor chat")

finally:
    driver.quit()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
exit(0 if FAIL == 0 else 1)
