#!/usr/bin/env python3
"""Exact user flow: open dashboard URL → login → back to dashboard → check leads"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

BASE = "http://localhost:8080"
PASS = 0; FAIL = 0
def check(c, m):
    global PASS, FAIL
    if c: PASS += 1; print(f"  ✅ {m}")
    else: FAIL += 1; print(f"  ❌ {m}")

print("=== EXACT USER FLOW ===\n")
options = Options(); options.add_argument("--headless")
driver = webdriver.Firefox(options=options)
driver.set_window_size(1920, 1080)

try:
    # STEP 1: User opens dashboard URL directly (not logged in)
    print("1. Open /demo/dashboard (not logged in)")
    driver.get(f"{BASE}/demo/dashboard")
    time.sleep(3)
    # Should redirect to /login
    current = driver.current_url
    check("/login" in current, f"Redirected to login: {current}")

    # STEP 2: User logs in
    print("\n2. Login as admin")
    try:
        username = driver.find_element(By.CSS_SELECTOR, "input[placeholder=Username]")
        password = driver.find_element(By.CSS_SELECTOR, "input[placeholder=Password]")
        btn = driver.find_element(By.TAG_NAME, "button")
        username.send_keys("admin")
        password.send_keys("test123")
        btn.click()
        time.sleep(3)
        check(True, "Login form submitted")
    except Exception as e:
        check(False, f"Login form: {e}")
        driver.quit(); exit(1)

    # STEP 3: Login redirects to /admin. User navigates to dashboard
    print("\n3. Navigate to /demo/dashboard")
    driver.get(f"{BASE}/demo/dashboard")
    time.sleep(5)

    # STEP 4: Check for lead cards
    print("\n4. Check for leads")
    cards = driver.find_elements(By.CSS_SELECTOR, ".lead-entry")
    check(len(cards) > 0, f"{len(cards)} lead cards found")
    
    # Print first 3 cards
    for i, c in enumerate(cards[:3]):
        txt = c.text.replace('\n',' ')[:80]
        print(f"   Card {i+1}: {txt}")

    # STEP 5: Send a message from visitor
    print("\n5. Send message from /demo in new tab")
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(f"{BASE}/demo")
    time.sleep(3)
    try:
        inp = driver.find_element(By.CSS_SELECTOR, "input.chat-input")
        inp.send_keys("EXACT USER FLOW TEST")
        driver.find_element(By.CSS_SELECTOR, "button.send-btn").click()
        time.sleep(2)
        check(True, "Message sent")
    except Exception as e:
        check(False, f"Chat: {e}")

    # STEP 6: Switch back to dashboard, wait for poll
    print("\n6. Check dashboard for new lead")
    driver.switch_to.window(driver.window_handles[0])
    time.sleep(4)
    cards2 = driver.find_elements(By.CSS_SELECTOR, ".lead-entry")
    new_count = len(cards2)
    check(new_count > 0, f"{new_count} lead cards after sending message")

    # Check if any card contains our message
    found = False
    for i, c in enumerate(cards2):
        txt = c.text[:120]
        if "EXACT USER FLOW TEST" in txt or "USER FLOW" in txt:
            found = True
            print(f"   Found in card {i+1}: {txt}")
            break
        elif i < 3 or i >= len(cards2)-3:
            print(f"   Card {i+1}: {txt}")
    check(found, "New lead from chat message appears in dashboard")

finally:
    driver.quit()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
exit(0 if FAIL == 0 else 1)
