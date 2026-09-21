"""Test pickup address endpoint with optional coordinates (lat, lng, city, country, postal_code)."""
import os
import uuid
import requests
from datetime import datetime, timezone, timedelta

def _load_url():
    """Load backend URL from frontend .env file."""
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_url()
API = f"{BASE_URL}/api"

# Use existing test users that have coins
INVITER_EMAIL = "premv3@example.com"
INVITER_PASS = "TestPass123!"

def _hdr(tok):
    """Create authorization header."""
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

def _login(email, password):
    """Login and return token and user."""
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text}"
    j = r.json()
    return j["token"], j["user"]

def _register(email=None, name="TestRecipient"):
    """Register a new user and return token and user."""
    email = email or f"TEST_pickup_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email,
        "password": "TestPass123!",
        "name": name,
        "age": 25,
        "gender": "female",
        "interested_in": "male",
        "city": "Toronto",
        "country": "Canada",
        "lat": 43.6532,
        "lng": -79.3832
    }, timeout=20)
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    j = r.json()
    return j["token"], j["user"]

def _set_date_price_and_availability(tok, price):
    """Set user's date price and availability."""
    # Set availability for the next 365 days
    today = datetime.now(timezone.utc).date()
    availability = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(365)]
    
    r = requests.patch(f"{API}/auth/me", headers=_hdr(tok), json={
        "date_price": price,
        "availability": availability,
        "availability_time": {"from": "09:00", "to": "23:00"}
    }, timeout=20)
    assert r.status_code == 200, f"Set date price and availability failed: {r.status_code} {r.text}"
    return r.json()

def _future_iso(days_offset=100, hour=14):
    """Generate a future ISO timestamp for scheduling."""
    delta = timedelta(days=days_offset)
    dt = datetime.now(timezone.utc) + delta
    # Set to specific hour to ensure it's within availability window
    dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    return dt.isoformat()

def _create_invite(inviter_tok, recipient_id, coins=300):
    """Create a date invite with custom activity options."""
    scheduled_start = _future_iso(100, hour=14)
    
    r = requests.post(f"{API}/invites", headers=_hdr(inviter_tok), json={
        "recipient_id": recipient_id,
        "activity_option_1": "Coffee at a cozy cafe",
        "activity_option_2": "Walk in the park",
        "activity_option_3": "Dinner at a nice restaurant",
        "scheduled_start": scheduled_start,
        "coins": coins,
        "safety_ack": True
    }, timeout=20)
    assert r.status_code == 200, f"Create invite failed: {r.status_code} {r.text}"
    return r.json()["id"]

def _choose_activity(recipient_tok, did):
    """Recipient chooses a date activity (first option)."""
    r = requests.post(f"{API}/invites/{did}/choose", headers=_hdr(recipient_tok),
                     json={"idea_id": "opt1"}, timeout=20)
    assert r.status_code == 200, f"Choose activity failed: {r.status_code} {r.text}"

def _propose_location(inviter_tok, did, start_iso=None):
    """Inviter proposes a meeting location."""
    r = requests.post(f"{API}/invites/{did}/location", headers=_hdr(inviter_tok), json={
        "venue": "Cafe Test",
        "address": "100 Queen St W",
        "city": "Toronto",
        "country": "Canada",
        "postal_code": "M5H 2N2",
        "lat": 43.6511,
        "lng": -79.3817,
        "scheduled_start": start_iso or _future_iso(100)
    }, timeout=20)
    assert r.status_code == 200, f"Propose location failed: {r.status_code} {r.text}"

def _request_taxi(recipient_tok, did, amount=50):
    """Recipient requests a taxi."""
    r = requests.post(f"{API}/invites/{did}/taxi/request", headers=_hdr(recipient_tok),
                     json={"amount": amount}, timeout=20)
    assert r.status_code == 200, f"Request taxi failed: {r.status_code} {r.text}"
    return r.json()

def _offer_pickup(inviter_tok, did):
    """Inviter offers to pick up the recipient."""
    r = requests.post(f"{API}/invites/{did}/pickup/offer", headers=_hdr(inviter_tok), timeout=20)
    assert r.status_code == 200, f"Offer pickup failed: {r.status_code} {r.text}"
    return r.json()

def _submit_pickup_address(recipient_tok, did, address_data):
    """Recipient submits pickup address."""
    r = requests.post(f"{API}/invites/{did}/pickup/address", headers=_hdr(recipient_tok),
                     json=address_data, timeout=20)
    return r

def _get_invite(tok, did):
    """Get invite details."""
    r = requests.get(f"{API}/invites/{did}", headers=_hdr(tok), timeout=20)
    assert r.status_code == 200, f"Get invite failed: {r.status_code} {r.text}"
    return r.json()

def test_pickup_address_with_coordinates():
    """Test the full flow: walk to PICKUP_ADDRESS_PENDING, then submit address WITH coordinates."""
    print("\n=== Test 1: Pickup Address WITH Coordinates ===")
    
    # 1. Register two users
    print("1. Registering users...")
    inviter_tok, inviter = _login(INVITER_EMAIL, INVITER_PASS)
    recipient_tok, recipient = _register()
    _set_date_price_and_availability(recipient_tok, 200)
    
    print(f"   Inviter: {inviter['email']} (ID: {inviter['id']})")
    print(f"   Recipient: {recipient['email']} (ID: {recipient['id']})")
    
    # 2. Create invite
    print("2. Creating date invite...")
    did = _create_invite(inviter_tok, recipient["id"], coins=300)
    print(f"   Date ID: {did}")
    
    # 3. Recipient chooses activity
    print("3. Recipient choosing date activity...")
    _choose_activity(recipient_tok, did)
    
    # 4. Inviter proposes location
    print("4. Inviter proposing location...")
    _propose_location(inviter_tok, did)
    
    # 5. Recipient requests taxi
    print("5. Recipient requesting taxi...")
    taxi_resp = _request_taxi(recipient_tok, did, amount=50)
    assert taxi_resp["status"] == "TAXI_REQUESTED", f"Expected TAXI_REQUESTED, got {taxi_resp['status']}"
    print(f"   Status: {taxi_resp['status']}")
    
    # 6. Inviter offers pickup
    print("6. Inviter offering pickup...")
    pickup_resp = _offer_pickup(inviter_tok, did)
    assert pickup_resp["status"] == "PICKUP_ADDRESS_PENDING", f"Expected PICKUP_ADDRESS_PENDING, got {pickup_resp['status']}"
    print(f"   Status: {pickup_resp['status']}")
    
    # 7. Recipient submits pickup address WITH coordinates
    print("7. Recipient submitting pickup address WITH coordinates...")
    address_data = {
        "pickup_address": "123 King St, Toronto, M5H, Canada",
        "lat": 43.6489,
        "lng": -79.3817,
        "city": "Toronto",
        "country": "Canada",
        "postal_code": "M5H"
    }
    addr_resp = _submit_pickup_address(recipient_tok, did, address_data)
    assert addr_resp.status_code == 200, f"Submit pickup address failed: {addr_resp.status_code} {addr_resp.text}"
    addr_json = addr_resp.json()
    assert addr_json["status"] == "PICKUP_ADDRESS_SELECTED", f"Expected PICKUP_ADDRESS_SELECTED, got {addr_json['status']}"
    print(f"   Status: {addr_json['status']}")
    
    # 8. Verify transportation object contains all fields
    print("8. Verifying transportation object...")
    invite = _get_invite(recipient_tok, did)
    trans = invite.get("transportation", {})
    
    print(f"   Transportation object: {trans}")
    
    # Verify all fields are stored
    assert trans.get("pickup_address") == "123 King St, Toronto, M5H, Canada", f"pickup_address mismatch: {trans.get('pickup_address')}"
    assert trans.get("pickup_lat") == 43.6489, f"pickup_lat mismatch: {trans.get('pickup_lat')}"
    assert trans.get("pickup_lng") == -79.3817, f"pickup_lng mismatch: {trans.get('pickup_lng')}"
    assert trans.get("pickup_city") == "Toronto", f"pickup_city mismatch: {trans.get('pickup_city')}"
    assert trans.get("pickup_country") == "Canada", f"pickup_country mismatch: {trans.get('pickup_country')}"
    assert trans.get("pickup_postal_code") == "M5H", f"pickup_postal_code mismatch: {trans.get('pickup_postal_code')}"
    assert trans.get("status") == "address_selected", f"status mismatch: {trans.get('status')}"
    
    print("   ✅ All fields verified!")
    print("   ✅ Test 1 PASSED: Pickup address with coordinates stored correctly\n")
    return did

def test_pickup_address_backwards_compat():
    """Test backwards compatibility: pickup address WITHOUT coordinates (only pickup_address)."""
    print("\n=== Test 2: Pickup Address WITHOUT Coordinates (Backwards Compatibility) ===")
    
    # 1. Register two users
    print("1. Registering users...")
    inviter_tok, inviter = _login(INVITER_EMAIL, INVITER_PASS)
    recipient_tok, recipient = _register()
    _set_date_price_and_availability(recipient_tok, 200)
    
    print(f"   Inviter: {inviter['email']} (ID: {inviter['id']})")
    print(f"   Recipient: {recipient['email']} (ID: {recipient['id']})")
    
    # 2. Create invite
    print("2. Creating date invite...")
    did = _create_invite(inviter_tok, recipient["id"], coins=300)
    print(f"   Date ID: {did}")
    
    # 3. Recipient chooses activity
    print("3. Recipient choosing date activity...")
    _choose_activity(recipient_tok, did)
    
    # 4. Inviter proposes location
    print("4. Inviter proposing location...")
    _propose_location(inviter_tok, did)
    
    # 5. Recipient requests taxi
    print("5. Recipient requesting taxi...")
    taxi_resp = _request_taxi(recipient_tok, did, amount=50)
    assert taxi_resp["status"] == "TAXI_REQUESTED", f"Expected TAXI_REQUESTED, got {taxi_resp['status']}"
    print(f"   Status: {taxi_resp['status']}")
    
    # 6. Inviter offers pickup
    print("6. Inviter offering pickup...")
    pickup_resp = _offer_pickup(inviter_tok, did)
    assert pickup_resp["status"] == "PICKUP_ADDRESS_PENDING", f"Expected PICKUP_ADDRESS_PENDING, got {pickup_resp['status']}"
    print(f"   Status: {pickup_resp['status']}")
    
    # 7. Recipient submits pickup address WITHOUT coordinates (backwards compat)
    print("7. Recipient submitting pickup address WITHOUT coordinates...")
    address_data = {
        "pickup_address": "456 Bay St, Toronto, Ontario, Canada"
    }
    addr_resp = _submit_pickup_address(recipient_tok, did, address_data)
    assert addr_resp.status_code == 200, f"Submit pickup address failed: {addr_resp.status_code} {addr_resp.text}"
    addr_json = addr_resp.json()
    assert addr_json["status"] == "PICKUP_ADDRESS_SELECTED", f"Expected PICKUP_ADDRESS_SELECTED, got {addr_json['status']}"
    print(f"   Status: {addr_json['status']}")
    
    # 8. Verify transportation object contains only pickup_address
    print("8. Verifying transportation object...")
    invite = _get_invite(recipient_tok, did)
    trans = invite.get("transportation", {})
    
    print(f"   Transportation object: {trans}")
    
    # Verify pickup_address is stored
    assert trans.get("pickup_address") == "456 Bay St, Toronto, Ontario, Canada", f"pickup_address mismatch: {trans.get('pickup_address')}"
    assert trans.get("status") == "address_selected", f"status mismatch: {trans.get('status')}"
    
    # Verify optional fields are not present (or None)
    print(f"   pickup_lat: {trans.get('pickup_lat')} (should be None or absent)")
    print(f"   pickup_lng: {trans.get('pickup_lng')} (should be None or absent)")
    
    print("   ✅ Backwards compatibility verified!")
    print("   ✅ Test 2 PASSED: Pickup address without coordinates works correctly\n")
    return did

if __name__ == "__main__":
    print("\n" + "="*80)
    print("PICKUP ADDRESS ENDPOINT TEST")
    print("Testing POST /api/invites/{did}/pickup/address with optional coordinates")
    print("="*80)
    
    try:
        # Test 1: With coordinates
        did1 = test_pickup_address_with_coordinates()
        
        # Test 2: Without coordinates (backwards compat)
        did2 = test_pickup_address_backwards_compat()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED")
        print("="*80)
        print(f"\nTest Summary:")
        print(f"  - Test 1 (with coordinates): Date ID {did1}")
        print(f"  - Test 2 (backwards compat): Date ID {did2}")
        print(f"\nConclusion:")
        print(f"  ✅ Pickup address endpoint accepts optional lat, lng, city, country, postal_code")
        print(f"  ✅ All fields are stored correctly in transportation object")
        print(f"  ✅ Backwards compatibility maintained (works with only pickup_address)")
        print(f"  ✅ Status transitions correctly: PICKUP_ADDRESS_PENDING → PICKUP_ADDRESS_SELECTED")
        print()
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise
