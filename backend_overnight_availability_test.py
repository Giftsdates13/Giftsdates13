#!/usr/bin/env python3
"""
Test overnight availability windows (time windows that pass midnight into the next day).
Focus: availability_time with from > to (e.g. 22:00-02:00).
"""
import requests
import uuid
from datetime import datetime, timedelta

# Backend URL from frontend/.env
BACKEND_URL = "https://secure-gifts-3.preview.emergentagent.com/api"

def register_user(email, password, name, age=25, gender="female", interested_in="male"):
    """Register a new user and return token + user data."""
    payload = {
        "email": email,
        "password": password,
        "name": name,
        "age": age,
        "gender": gender,
        "interested_in": interested_in,
        "city": "Toronto",
        "country": "Canada"
    }
    resp = requests.post(f"{BACKEND_URL}/auth/register", json=payload)
    print(f"Register {email}: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text}")
        return None, None
    data = resp.json()
    return data.get("token"), data.get("user")

def get_me(token):
    """Get current user data."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BACKEND_URL}/auth/me", headers=headers)
    if resp.status_code == 200:
        return resp.json()
    return None

def update_profile(token, updates):
    """Update user profile."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.patch(f"{BACKEND_URL}/auth/me", json=updates, headers=headers)
    print(f"Update profile: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text}")
    return resp

def get_profile_availability(token, user_id):
    """Get availability for a user."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BACKEND_URL}/profiles/{user_id}/availability", headers=headers)
    print(f"Get availability: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text}")
    return resp

def get_dates(token):
    """Get user's dates."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BACKEND_URL}/dates", headers=headers)
    return resp

def book_date(token, target_id, scheduled_at, local_time, coins, venue, city, activities):
    """Book a date."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "target_id": target_id,
        "venue": venue,
        "city": city,
        "scheduled_at": scheduled_at,
        "local_time": local_time,
        "coins": coins,
        "activities": activities,
        "address": "123 Main St",
        "country": "Canada",
        "postal_code": "M5H"
    }
    resp = requests.post(f"{BACKEND_URL}/dates/book", json=payload, headers=headers)
    print(f"Book date: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text}")
    return resp

def main():
    print("=" * 80)
    print("OVERNIGHT AVAILABILITY FEATURE TEST")
    print("=" * 80)
    
    # Step 1: Register two users
    print("\n[STEP 1] Register two users (userA, userB)")
    email_a = f"userA_{uuid.uuid4().hex[:8]}@example.com"
    email_b = f"userB_{uuid.uuid4().hex[:8]}@example.com"
    
    token_a, user_a = register_user(email_a, "SecurePass123!", "Alice", age=28, gender="female", interested_in="male")
    token_b, user_b = register_user(email_b, "SecurePass123!", "Bob", age=30, gender="male", interested_in="female")
    
    if not token_a or not token_b:
        print("❌ FAILED: Could not register users")
        return
    
    user_a_id = user_a["id"]
    user_b_id = user_b["id"]
    print(f"✅ UserA: {email_a} (ID: {user_a_id})")
    print(f"✅ UserB: {email_b} (ID: {user_b_id})")
    
    # Step 2: Set overnight availability for userA (22:00-02:00)
    print("\n[STEP 2] Set userA availability_time to {from:'22:00', to:'02:00'} (overnight)")
    future_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    print(f"  Available date: {future_date}")
    
    resp = update_profile(token_a, {
        "availability_time": {"from": "22:00", "to": "02:00"},
        "availability": [future_date]
    })
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200 OK, got {resp.status_code}")
        print(f"  Response: {resp.text}")
        return
    
    profile_a = resp.json()
    saved_time = profile_a.get("availability_time")
    saved_days = profile_a.get("availability")
    
    print(f"✅ PASSED: Overnight window accepted (200 OK)")
    print(f"  Saved availability_time: {saved_time}")
    print(f"  Saved availability: {saved_days}")
    
    if saved_time != {"from": "22:00", "to": "02:00"}:
        print(f"❌ FAILED: availability_time not saved correctly")
        return
    
    if future_date not in saved_days:
        print(f"❌ FAILED: future date not in availability")
        return
    
    # Step 3: Test equal from==to (should be rejected)
    print("\n[STEP 3] Test equal from==to (should be rejected as invalid)")
    resp = update_profile(token_a, {
        "availability_time": {"from": "18:00", "to": "18:00"}
    })
    
    if resp.status_code != 400:
        print(f"❌ FAILED: Expected 400 Bad Request, got {resp.status_code}")
        return
    
    error_text = resp.text
    print(f"✅ PASSED: Equal from==to rejected (400 Bad Request)")
    print(f"  Error: {error_text}")
    
    if "Invalid time window" not in error_text:
        print(f"⚠️  WARNING: Expected 'Invalid time window' in error message")
    
    # Restore overnight window
    print("\n  Restoring overnight window (22:00-02:00)")
    resp = update_profile(token_a, {
        "availability_time": {"from": "22:00", "to": "02:00"}
    })
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not restore overnight window")
        return
    
    # Step 4: Get availability as userB
    print("\n[STEP 4] GET /api/profiles/{userA_id}/availability as userB")
    resp = get_profile_availability(token_b, user_a_id)
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200 OK, got {resp.status_code}")
        return
    
    avail_data = resp.json()
    time_window = avail_data.get("time_window")
    available_days = avail_data.get("available_days")
    
    print(f"✅ PASSED: Availability endpoint works (200 OK)")
    print(f"  time_window: {time_window}")
    print(f"  available_days: {available_days}")
    
    if time_window != {"from": "22:00", "to": "02:00"}:
        print(f"❌ FAILED: time_window not correct")
        return
    
    if future_date not in available_days:
        print(f"❌ FAILED: future date not in available_days")
        return
    
    # Step 5: Ensure userB has enough coins
    print("\n[STEP 5] Check userB coins (need at least 150 for booking)")
    user_b_data = get_me(token_b)
    coins_b = user_b_data.get("coins", 0) + user_b_data.get("withdrawable", 0)
    print(f"  UserB coins: {coins_b}")
    
    if coins_b < 150:
        print(f"  UserB has insufficient coins ({coins_b} < 150)")
        print(f"  Adding 500 coins to userB for testing...")
        import subprocess
        result = subprocess.run(["python3", "/app/add_coins.py", user_b_id, "500"], capture_output=True, text=True)
        print(f"  {result.stdout.strip()}")
        
        # Refresh user data
        user_b_data = get_me(token_b)
        coins_b = user_b_data.get("coins", 0) + user_b_data.get("withdrawable", 0)
        print(f"  Updated UserB coins: {coins_b}")
        
        if coins_b < 150:
            print(f"❌ FAILED: Could not add coins to userB")
            return
    
    # Step 6: Book a date at 23:00 (should succeed)
    print("\n[STEP 6] POST /api/dates/book from userB to userA at local_time='23:00'")
    scheduled_at = f"{future_date}T22:00:00"
    activities = ["Romantic dinner at rooftop restaurant", "Stargazing at observatory", "Late night jazz club"]
    
    resp = book_date(token_b, user_a_id, scheduled_at, "23:00", 150, "The Rooftop", "Toronto", activities)
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200 OK, got {resp.status_code}")
        print(f"  Response: {resp.text}")
        return
    
    booking_response = resp.json()
    booking_id = booking_response.get("booking_id")
    status = booking_response.get("status")
    
    print(f"✅ PASSED: Booking created (200 OK)")
    print(f"  Booking ID: {booking_id}")
    print(f"  Status: {status}")
    
    if status != "escrow":
        print(f"❌ FAILED: Expected status 'escrow', got '{status}'")
        return
    
    # Fetch the booking details to verify slot_from and slot_to
    print(f"  Fetching booking details...")
    dates_resp = get_dates(token_b)
    if dates_resp.status_code != 200:
        print(f"❌ FAILED: Could not fetch dates")
        return
    
    dates_data = dates_resp.json()
    outgoing = dates_data.get("outgoing", [])
    
    # Find our booking
    booking_data = None
    for b in outgoing:
        if b.get("id") == booking_id:
            booking_data = b
            break
    
    if not booking_data:
        print(f"❌ FAILED: Could not find booking {booking_id} in outgoing dates")
        return
    
    slot_from = booking_data.get("slot_from")
    slot_to = booking_data.get("slot_to")
    
    print(f"  slot_from: {slot_from}")
    print(f"  slot_to: {slot_to}")
    
    if slot_from != "23:00":
        print(f"❌ FAILED: Expected slot_from '23:00', got '{slot_from}'")
        return
    
    if slot_to != "01:30":
        print(f"❌ FAILED: Expected slot_to '01:30' (next day), got '{slot_to}'")
        return
    
    # Step 7: NEGATIVE TEST - Book at 01:00 (should fail - not enough time)
    print("\n[STEP 7] NEGATIVE TEST: Book at local_time='01:00' (should fail - insufficient time)")
    resp = book_date(token_b, user_a_id, scheduled_at, "01:00", 150, "The Rooftop", "Toronto", activities)
    
    if resp.status_code != 400:
        print(f"❌ FAILED: Expected 400 Bad Request, got {resp.status_code}")
        return
    
    error_text = resp.text
    print(f"✅ PASSED: Booking rejected (400 Bad Request)")
    print(f"  Error: {error_text}")
    
    if "TIME_UNAVAILABLE" not in error_text:
        print(f"⚠️  WARNING: Expected 'TIME_UNAVAILABLE' in error message")
    
    # Step 8: REGRESSION TEST - Normal same-day window still works
    print("\n[STEP 8] REGRESSION TEST: Normal same-day window (18:00-23:00) still works")
    future_date_2 = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
    
    # Update userA to normal window
    resp = update_profile(token_a, {
        "availability_time": {"from": "18:00", "to": "23:00"},
        "availability": [future_date_2]
    })
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Could not set normal window")
        return
    
    print(f"  Set normal window 18:00-23:00 for {future_date_2}")
    
    # Book at 18:00
    scheduled_at_2 = f"{future_date_2}T18:00:00"
    resp = book_date(token_b, user_a_id, scheduled_at_2, "18:00", 150, "The Bistro", "Toronto", activities)
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200 OK, got {resp.status_code}")
        print(f"  Response: {resp.text}")
        return
    
    booking_response_2 = resp.json()
    booking_id_2 = booking_response_2.get("booking_id")
    
    # Fetch the booking details
    dates_resp_2 = get_dates(token_b)
    if dates_resp_2.status_code != 200:
        print(f"❌ FAILED: Could not fetch dates")
        return
    
    dates_data_2 = dates_resp_2.json()
    outgoing_2 = dates_data_2.get("outgoing", [])
    
    # Find our booking
    booking_data_2 = None
    for b in outgoing_2:
        if b.get("id") == booking_id_2:
            booking_data_2 = b
            break
    
    if not booking_data_2:
        print(f"❌ FAILED: Could not find booking {booking_id_2} in outgoing dates")
        return
    
    slot_from_2 = booking_data_2.get("slot_from")
    slot_to_2 = booking_data_2.get("slot_to")
    
    print(f"✅ PASSED: Normal window booking works (200 OK)")
    print(f"  slot_from: {slot_from_2}")
    print(f"  slot_to: {slot_to_2}")
    
    if slot_from_2 != "18:00":
        print(f"❌ FAILED: Expected slot_from '18:00', got '{slot_from_2}'")
        return
    
    if slot_to_2 != "20:30":
        print(f"❌ FAILED: Expected slot_to '20:30', got '{slot_to_2}'")
        return
    
    print("\n" + "=" * 80)
    print("ALL TESTS PASSED ✅")
    print("=" * 80)
    print("\nSummary:")
    print("  ✅ Overnight window (22:00-02:00) accepted by PUT /api/profile")
    print("  ✅ Equal from==to (18:00-18:00) rejected as invalid")
    print("  ✅ GET /api/profiles/{id}/availability returns correct time_window")
    print("  ✅ Booking at 23:00 succeeds with slot_to='01:30' (next day)")
    print("  ✅ Booking at 01:00 rejected (TIME_UNAVAILABLE - insufficient time)")
    print("  ✅ Normal same-day window (18:00-23:00) still works")

if __name__ == "__main__":
    main()
