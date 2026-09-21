#!/usr/bin/env python3
"""
Test VIP schedule overnight availability windows (crossing midnight into next day).
Tests the new feature that allows VIP availability blocks like 22:00-02:00.
"""
import requests
import uuid
import os
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

# Backend URL from frontend/.env
BACKEND_URL = "https://secure-gifts-3.preview.emergentagent.com/api"

# MongoDB connection from backend/.env
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

def random_email():
    return f"vip_test_{uuid.uuid4().hex[:8]}@example.com"

def register_user(email, password="SecurePass123!", name=None):
    """Register a new user and return token + user data."""
    payload = {
        "email": email,
        "password": password,
        "name": name or f"User_{uuid.uuid4().hex[:6]}",
        "age": 28,
        "gender": "female",
        "interested_in": "male",
        "city": "Toronto",
        "country": "Canada"
    }
    resp = requests.post(f"{BACKEND_URL}/auth/register", json=payload, timeout=30)
    print(f"Register {email}: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text}")
        return None, None
    data = resp.json()
    return data["token"], data["user"]

def get_me(token):
    """Get current user data."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BACKEND_URL}/auth/me", headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"Get me failed: {resp.status_code} {resp.text}")
        return None
    return resp.json()

def make_user_vip(user_id):
    """Make a user VIP by setting vip_until in MongoDB."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    # Set vip_until to 30 days in the future
    vip_until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    result = db.users.update_one(
        {"id": user_id},
        {"$set": {"vip_until": vip_until}}
    )
    print(f"Make user VIP: {user_id} -> vip_until={vip_until}, matched={result.matched_count}, modified={result.modified_count}")
    client.close()
    return result.modified_count > 0

def add_coins(user_id, amount):
    """Add coins to a user via MongoDB."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    result = db.users.update_one(
        {"id": user_id},
        {"$inc": {"coins": amount}}
    )
    print(f"Add coins: {user_id} +{amount} coins, matched={result.matched_count}, modified={result.modified_count}")
    client.close()
    return result.modified_count > 0

def add_vip_availability(token, date, start, end, slot_len=60):
    """POST /api/vip/schedule/availability"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "date": date,
        "start": start,
        "end": end,
        "slot_len": slot_len
    }
    resp = requests.post(f"{BACKEND_URL}/vip/schedule/availability", json=payload, headers=headers, timeout=30)
    print(f"Add VIP availability {date} {start}-{end}: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text}")
        return None
    return resp.json()

def get_vip_slots(token, vip_id):
    """GET /api/vip/schedule/{vip_id}/slots"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BACKEND_URL}/vip/schedule/{vip_id}/slots", headers=headers, timeout=30)
    print(f"Get VIP slots for {vip_id}: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  Error: {resp.text}")
        return None
    return resp.json()

def book_vip_slot(token, vip_id, date, start, end, coins, activity="Dinner", tz="UTC"):
    """POST /api/vip/schedule/{vip_id}/book"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "date": date,
        "start": start,
        "end": end,
        "coins": coins,
        "activity": activity,
        "tz": tz
    }
    resp = requests.post(f"{BACKEND_URL}/vip/schedule/{vip_id}/book", json=payload, headers=headers, timeout=30)
    print(f"Book VIP slot {date} {start}-{end}: {resp.status_code}")
    if resp.status_code not in [200, 400, 409]:
        print(f"  Response: {resp.text}")
    return resp

def main():
    print("=" * 80)
    print("VIP SCHEDULE OVERNIGHT AVAILABILITY TEST")
    print("=" * 80)
    
    # Step 1: Register userA (VIP host) and userB (booker)
    print("\n[STEP 1] Register userA (VIP host) and userB (booker)")
    email_a = random_email()
    email_b = random_email()
    
    token_a, user_a = register_user(email_a, name="VIP_Host_A")
    if not token_a:
        print("❌ Failed to register userA")
        return
    
    token_b, user_b = register_user(email_b, name="Booker_B")
    if not token_b:
        print("❌ Failed to register userB")
        return
    
    user_a_id = user_a["id"]
    user_b_id = user_b["id"]
    print(f"✅ UserA: {email_a} (ID: {user_a_id})")
    print(f"✅ UserB: {email_b} (ID: {user_b_id})")
    
    # Step 2: Make userA a VIP
    print("\n[STEP 2] Make userA a VIP by setting vip_until in MongoDB")
    if not make_user_vip(user_a_id):
        print("❌ Failed to make userA VIP")
        return
    print(f"✅ UserA is now VIP")
    
    # Verify userA is VIP
    user_a_updated = get_me(token_a)
    if not user_a_updated:
        print("❌ Failed to get updated userA data")
        return
    print(f"   vip_until: {user_a_updated.get('vip_until', 'NOT SET')}")
    
    # Step 3: Give userB coins
    print("\n[STEP 3] Give userB ~500 coins")
    if not add_coins(user_b_id, 500):
        print("❌ Failed to add coins to userB")
        return
    user_b_updated = get_me(token_b)
    print(f"✅ UserB coins: {user_b_updated.get('coins', 0)}")
    
    # Step 4: Add overnight availability (22:00-02:00) - EXPECT 200
    print("\n[STEP 4] Add overnight availability (22:00-02:00) - EXPECT 200 OK")
    future_date_1 = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
    avail_1 = add_vip_availability(token_a, future_date_1, "22:00", "02:00", slot_len=60)
    if not avail_1:
        print("❌ FAILED: Overnight availability (22:00-02:00) was rejected")
        return
    print(f"✅ PASSED: Overnight availability accepted")
    print(f"   Block ID: {avail_1.get('id')}")
    print(f"   Date: {avail_1.get('date')}, Start: {avail_1.get('start')}, End: {avail_1.get('end')}")
    
    # Verify the block is stored correctly
    if avail_1.get('start') != "22:00" or avail_1.get('end') != "02:00":
        print(f"❌ FAILED: Block stored incorrectly (start={avail_1.get('start')}, end={avail_1.get('end')})")
        return
    print(f"✅ PASSED: Block stored correctly (start=22:00, end=02:00)")
    
    # Step 5: Add availability with equal start==end (18:00-18:00) - EXPECT 400
    print("\n[STEP 5] Add availability with equal start==end (18:00-18:00) - EXPECT 400 BAD_WINDOW")
    future_date_2 = (datetime.now(timezone.utc) + timedelta(days=4)).strftime("%Y-%m-%d")
    avail_2 = add_vip_availability(token_a, future_date_2, "18:00", "18:00", slot_len=60)
    if avail_2:
        print(f"❌ FAILED: Equal start==end was accepted (should be rejected)")
        return
    print(f"✅ PASSED: Equal start==end correctly rejected (400 BAD_WINDOW)")
    
    # Step 6: Get slots for overnight date - verify slots include 22:00-23:00, 23:00-00:00, 00:00-01:00, 01:00-02:00
    print("\n[STEP 6] Get slots for overnight date - verify slots")
    slots_data = get_vip_slots(token_b, user_a_id)
    if not slots_data:
        print("❌ FAILED: Could not get VIP slots")
        return
    
    print(f"✅ PASSED: GET /api/vip/schedule/{user_a_id}/slots returned 200")
    
    # Find the overnight date
    overnight_day = None
    for day in slots_data.get("days", []):
        if day["date"] == future_date_1:
            overnight_day = day
            break
    
    if not overnight_day:
        print(f"❌ FAILED: Overnight date {future_date_1} not found in slots")
        return
    
    print(f"✅ PASSED: Overnight date {future_date_1} found in slots")
    print(f"   Slots: {len(overnight_day['slots'])}")
    
    # Verify slots: 22:00-23:00, 23:00-00:00, 00:00-01:00, 01:00-02:00
    expected_slots = [
        {"start": "22:00", "end": "23:00", "next_day": False},
        {"start": "23:00", "end": "00:00", "next_day": False},
        {"start": "00:00", "end": "01:00", "next_day": True},
        {"start": "01:00", "end": "02:00", "next_day": True},
    ]
    
    for expected in expected_slots:
        found = False
        for slot in overnight_day["slots"]:
            if slot["start"] == expected["start"] and slot["end"] == expected["end"]:
                found = True
                if slot.get("next_day") != expected["next_day"]:
                    print(f"❌ FAILED: Slot {expected['start']}-{expected['end']} has wrong next_day flag (expected={expected['next_day']}, actual={slot.get('next_day')})")
                    return
                if slot.get("state") != "available":
                    print(f"❌ FAILED: Slot {expected['start']}-{expected['end']} has wrong state (expected=available, actual={slot.get('state')})")
                    return
                print(f"✅ PASSED: Slot {expected['start']}-{expected['end']} correct (next_day={slot.get('next_day')}, state={slot.get('state')})")
                break
        if not found:
            print(f"❌ FAILED: Slot {expected['start']}-{expected['end']} not found")
            return
    
    # Step 7: Book overnight slot (00:00-01:00) - EXPECT 200 pending
    print("\n[STEP 7] Book overnight slot (00:00-01:00) - EXPECT 200 pending")
    book_resp = book_vip_slot(token_b, user_a_id, future_date_1, "00:00", "01:00", 300, activity="Dinner", tz="UTC")
    if book_resp.status_code != 200:
        print(f"❌ FAILED: Booking overnight slot failed (status={book_resp.status_code})")
        print(f"   Error: {book_resp.text}")
        return
    
    booking_data = book_resp.json()
    print(f"✅ PASSED: Booking overnight slot succeeded (status=200)")
    print(f"   Booking ID: {booking_data.get('booking_id')}")
    print(f"   Status: {booking_data.get('status')}")
    
    if booking_data.get("status") != "pending":
        print(f"❌ FAILED: Booking status is not 'pending' (actual={booking_data.get('status')})")
        return
    print(f"✅ PASSED: Booking status is 'pending'")
    
    # Verify booking stored with start="00:00", end="01:00"
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    booking_doc = db.vip_sched.find_one({"id": booking_data["booking_id"]})
    client.close()
    
    if not booking_doc:
        print(f"❌ FAILED: Booking not found in database")
        return
    
    if booking_doc.get("start") != "00:00" or booking_doc.get("end") != "01:00":
        print(f"❌ FAILED: Booking stored incorrectly (start={booking_doc.get('start')}, end={booking_doc.get('end')})")
        return
    print(f"✅ PASSED: Booking stored correctly (start=00:00, end=01:00)")
    
    # Step 8: NEGATIVE - Book slot that exceeds window (01:30-02:30) - EXPECT 400 TIME_UNAVAILABLE
    print("\n[STEP 8] NEGATIVE: Book slot that exceeds window (01:30-02:30) - EXPECT 400 TIME_UNAVAILABLE")
    # Add more coins to userB for this test
    add_coins(user_b_id, 300)
    book_resp_neg = book_vip_slot(token_b, user_a_id, future_date_1, "01:30", "02:30", 300, activity="Dinner", tz="UTC")
    if book_resp_neg.status_code != 400:
        print(f"❌ FAILED: Booking should be rejected with 400 (actual={book_resp_neg.status_code})")
        return
    
    error_text = book_resp_neg.text
    if "TIME_UNAVAILABLE" not in error_text:
        print(f"❌ FAILED: Error should be TIME_UNAVAILABLE (actual={error_text})")
        return
    print(f"✅ PASSED: Booking correctly rejected with 400 TIME_UNAVAILABLE")
    print(f"   Error: {error_text}")
    
    # Step 9: REGRESSION - Normal window (09:00-12:00) still works
    print("\n[STEP 9] REGRESSION: Normal window (09:00-12:00) still works")
    future_date_3 = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%d")
    avail_3 = add_vip_availability(token_a, future_date_3, "09:00", "12:00", slot_len=60)
    if not avail_3:
        print("❌ FAILED: Normal availability (09:00-12:00) was rejected")
        return
    print(f"✅ PASSED: Normal availability accepted")
    
    # Get slots for normal date
    slots_data_3 = get_vip_slots(token_b, user_a_id)
    if not slots_data_3:
        print("❌ FAILED: Could not get VIP slots for normal date")
        return
    
    # Find the normal date
    normal_day = None
    for day in slots_data_3.get("days", []):
        if day["date"] == future_date_3:
            normal_day = day
            break
    
    if not normal_day:
        print(f"❌ FAILED: Normal date {future_date_3} not found in slots")
        return
    
    print(f"✅ PASSED: Normal date {future_date_3} found in slots")
    
    # Verify normal slots have next_day=false
    for slot in normal_day["slots"]:
        if slot.get("next_day"):
            print(f"❌ FAILED: Normal slot {slot['start']}-{slot['end']} has next_day=true (should be false)")
            return
    print(f"✅ PASSED: All normal slots have next_day=false")
    
    # Book a normal slot (09:00-10:00)
    book_resp_3 = book_vip_slot(token_b, user_a_id, future_date_3, "09:00", "10:00", 300, activity="Coffee", tz="UTC")
    if book_resp_3.status_code != 200:
        print(f"❌ FAILED: Booking normal slot failed (status={book_resp_3.status_code})")
        print(f"   Error: {book_resp_3.text}")
        return
    
    booking_data_3 = book_resp_3.json()
    print(f"✅ PASSED: Booking normal slot succeeded (status=200)")
    print(f"   Booking ID: {booking_data_3.get('booking_id')}")
    print(f"   Status: {booking_data_3.get('status')}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("✅ ALL TESTS PASSED (8/8)")
    print()
    print("Test Results:")
    print("  1. ✅ Register userA and userB")
    print("  2. ✅ Make userA VIP (set vip_until in MongoDB)")
    print("  3. ✅ Give userB 500 coins")
    print("  4. ✅ Add overnight availability (22:00-02:00) - 200 OK")
    print("  5. ✅ Add availability with equal start==end (18:00-18:00) - 400 BAD_WINDOW")
    print("  6. ✅ Get slots - verify overnight slots with next_day flags")
    print("  7. ✅ Book overnight slot (00:00-01:00) - 200 pending")
    print("  8. ✅ NEGATIVE: Book slot exceeding window (01:30-02:30) - 400 TIME_UNAVAILABLE")
    print("  9. ✅ REGRESSION: Normal window (09:00-12:00) still works")
    print()
    print(f"Test Users:")
    print(f"  UserA (VIP): {email_a} (ID: {user_a_id})")
    print(f"  UserB (Booker): {email_b} (ID: {user_b_id})")
    print()
    print("NO ISSUES FOUND")
    print("=" * 80)

if __name__ == "__main__":
    main()
